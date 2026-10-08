"""Fixed-state fixture/allocation contracts; all commands and providers are offline."""
from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from social_sim.continuity.action_projection import FEASIBLE, RAW, project_actions, projected_prompt
from social_sim.continuity.benchmark import seed_demo
from social_sim.continuity.context import decision_prompt, observe
from social_sim.continuity.engine import ContinuityWorld
from social_sim.continuity.models import canonical_json, digest
from social_sim.continuity.q6_1 import project_state
from social_sim.continuity.q6_2_panel_fixtures import (
    CONDITIONS,
    FAMILIES,
    SCENARIO_IDS,
    STOP_MAPPING,
    SINGLE_TIMEOUT_V2,
    allocate_cells,
    build_world,
    freeze_scenarios,
    fairness_fingerprint,
    load_protocol,
    protocol_version,
    validate_protocol,
    world_fingerprint,
)
from social_sim.continuity.validation import validate_world


@pytest.fixture(scope="module")
def protocol():
    return load_protocol(Path(__file__).resolve().parents[1])


@pytest.fixture(scope="module")
def frozen(protocol):
    return freeze_scenarios(protocol)


def finish(world, request):
    while commitment := world.store.commitment(1):
        assert commitment["status"] == "ACTIVE"
        target = world.minute + min(15, commitment["remaining_min"])
        assert world.advance(f"{request}:t{target}", target)["accepted"]
    return world.store.get_commitment(request)["status"]


def test_twelve_meaningful_frozen_states_and_no_prompt_text(protocol, frozen):
    assert tuple(row["scenario_id"] for row in frozen) == SCENARIO_IDS
    assert Counter(row["family"] for row in frozen) == dict.fromkeys(FAMILIES, 2)
    assert len({row["state_hash"] for row in frozen}) == 12
    assert frozen == freeze_scenarios(protocol)
    for row in frozen:
        assert row["invariants"] == "PASS"
        assert row["candidate_count"] > 0
        assert row["candidate_count"] == len(row["executable_options"])
        assert row["candidate_hash"] == digest(row["executable_options"])
        assert set(row["prompt_hashes"]) == set(CONDITIONS)
        assert row["prompt_chars"][FEASIBLE] > row["prompt_chars"][RAW]
        assert max(row["prompt_chars"].values()) <= protocol["max_prompt_chars"]
        assert not {"system", "user", "prompt", "completion"} & row.keys()
        assert row["recipe"] and row["source"]


def test_seeded_shuffle_has_48_adjacent_cells_24_pairs_and_reversed_repeats(protocol, frozen):
    cells = allocate_cells(protocol, frozen)
    assert cells == allocate_cells(protocol, frozen)
    assert len(cells) == 48
    assert len({row["cell_id"] for row in cells}) == 48
    assert len({row["pair_id"] for row in cells}) == 24
    assert [row["order"] for row in cells] == list(range(1, 49))
    assert [row["cell_id"] for row in cells] == [f"c{value:03d}" for value in range(1, 49)]
    assert Counter(row["condition"] for row in cells) == {RAW: 24, FEASIBLE: 24}
    for left, right in zip(cells[::2], cells[1::2], strict=True):
        assert left["pair_id"] == right["pair_id"]
        assert left["scenario_id"] == right["scenario_id"]
        assert left["repeat"] == right["repeat"]
        assert left["order"] + 1 == right["order"]
        assert [left["within_pair_order"], right["within_pair_order"]] == [1, 2]
        expected = [RAW, FEASIBLE] if left["repeat"] == 1 else [FEASIBLE, RAW]
        assert [left["condition"], right["condition"]] == expected
    assert Counter((row["scenario_id"], row["repeat"]) for row in cells) == {
        (scenario, repeat): 2 for scenario in SCENARIO_IDS for repeat in (1, 2)
    }
    alternate = copy.deepcopy(protocol)
    alternate["seed"] += 1
    assert allocate_cells(alternate, frozen) != cells


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_ab_independent_worlds_have_identical_snapshots_and_audit_inputs(
        tmp_path, protocol, frozen, scenario_id):
    left = tmp_path / "a.sqlite3"
    right = tmp_path / "b.sqlite3"
    with build_world(left, scenario_id, protocol) as a, build_world(right, scenario_id, protocol) as b:
        assert a.store.snapshot() == b.store.snapshot()
        a_row, b_row = world_fingerprint(a, protocol), world_fingerprint(b, protocol)
        assert a_row == b_row
        expected = next(row for row in frozen if row["scenario_id"] == scenario_id)
        for key in ("state_hash", "initial_projected_state", "observation_hash", "object_candidates", "candidate_hash",
                    "prompt_hashes", "prompt_chars"):
            assert a_row[key] == expected[key]
        assert a.store.commitment(1) is None and b.store.commitment(1) is None
        assert validate_world(a)["invariants"] == validate_world(b)["invariants"] == "PASS"
        before_b = b.store.snapshot()
        proposal = project_actions(a)["executable_options"][0]
        assert a.start("isolated", 1, **proposal)["accepted"]
        assert finish(a, "isolated") == "COMPLETED"
        assert b.store.snapshot() == before_b
        assert a.store.snapshot() != b.store.snapshot()


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_frozen_projection_matches_original_rules_and_actual_execution(protocol, scenario_id):
    with build_world(":memory:", scenario_id, protocol) as world:
        before_state, before_events = world.store.snapshot(), world.store.events()
        changes = world.store.db.total_changes
        projection = project_actions(world)
        for assessment in projection["assessments"]:
            with ContinuityWorld(":memory:") as oracle:
                world.store.db.backup(oracle.store.db)
                result = oracle.start("oracle", 1, assessment["activity"], assessment["target"])
                completed = result["accepted"] and finish(oracle, "oracle") == "COMPLETED"
                assert completed == assessment["executable_now"], (scenario_id, assessment, result)
                assert result["accepted"] == assessment["start_allowed"]
                validate_world(oracle)
        assert world.store.snapshot() == before_state
        assert world.store.events() == before_events
        assert world.store.db.total_changes == changes
        assert world.store.db.execute("SELECT count(*) FROM decision_attempts").fetchone()[0] == 0


def test_ownership_changes_play_only_via_real_purchase(protocol):
    with build_world(":memory:", "s01", protocol) as unowned, build_world(
            ":memory:", "s02", protocol) as owned:
        assert unowned.store.link(1, "game_a")["quantity"] == 0
        assert not unowned.preview_activity(1, "PLAY", "game_a")["executable_now"]
        assert owned.store.link(1, "game_a")["quantity"] == 1
        assert owned.preview_activity(1, "PLAY", "game_a")["executable_now"]
        assert owned.store.actor(1)["money_cents"] == 297000
        assert owned.store.object("game_a")["stock"] == 99
        assert any(event["kind"] == "PURCHASED" for event in owned.store.events())


def test_legally_generated_post_meal_245_is_still_feasible(protocol):
    with build_world(":memory:", "s03", protocol) as hungry, build_world(
            ":memory:", "s04", protocol) as eaten:
        assert hungry.minute == 15 and hungry.store.actor(1)["hunger_milli"] == 815
        assert eaten.minute == 45 and eaten.store.actor(1)["hunger_milli"] == 245
        assert eaten.store.actor(1)["calories_kcal"] == 650
        assert eaten.preview_activity(1, "MEAL", "food_meal")["executable_now"]
        assert {"activity": "MEAL", "target": "food_meal"} in project_actions(eaten)[
            "executable_options"]
        assert eaten.start("second-meal", 1, "MEAL", "food_meal")["accepted"]
        assert finish(eaten, "second-meal") == "COMPLETED"
        assert eaten.store.actor(1)["hunger_milli"] == 0
        validate_world(eaten)


def test_media_partial_cancel_and_full_completion_are_truthful(protocol):
    with build_world(":memory:", "s05", protocol) as partial, build_world(
            ":memory:", "s06", protocol) as completed:
        link = partial.store.link(1, "series_a")
        assert link["watched"] == [] and link["offsets"] == {"1": 10}
        assert partial.store.commitment(1) is None
        assert partial.store.get_commitment("fixture:01")["status"] == "CANCELLED"
        assert partial.next_episode(1, "series_a") == 1
        assert partial.preview_activity(1, "WATCH", "series_a")["resolved_episode"] == 1
        assert partial.start("resume-content", 1, "WATCH", "series_a")["accepted"]
        assert partial.store.commitment(1)["remaining_min"] == 20
        assert finish(partial, "resume-content") == "COMPLETED"
        assert partial.next_episode(1, "series_a") == 2
        assert completed.minute == 3600
        assert completed.store.link(1, "series_a")["watched"] == list(range(1, 121))
        assert completed.next_episode(1, "series_a") is None
        assert completed.preview_activity(1, "WATCH", "series_a")["reason"] == "SERIES_COMPLETED"
        assert completed.store.commitment(1) is None
        assert project_actions(completed)["candidate_count"] > 0
        validate_world(partial)
        validate_world(completed)


def test_location_uses_original_work_and_home_conditions(protocol):
    with build_world(":memory:", "s07", protocol) as home, build_world(
            ":memory:", "s08", protocol) as office:
        assert home.store.actor(1)["location"] == "home"
        assert office.store.actor(1)["location"] == "office"
        assert not home.preview_activity(1, "WORK")["executable_now"]
        assert office.preview_activity(1, "WORK")["executable_now"]
        for activity in ("SLEEP", "PERSONAL_CARE", "CHORES"):
            assert home.preview_activity(1, activity)["executable_now"]
            assert office.preview_activity(1, activity)["reason"] == "NOT_AT_ACTIVITY_LOCATION"


@pytest.mark.parametrize("good_id,bad_id,reason", [
    ("s09", "s10", "INSUFFICIENT_FUNDS"),
    ("s11", "s12", "OUT_OF_STOCK"),
])
def test_purchase_limits_preserve_legitimate_partial_travel_effects(protocol, good_id, bad_id, reason):
    with build_world(":memory:", good_id, protocol) as good, build_world(
            ":memory:", bad_id, protocol) as bad:
        assert good.store.link(1, "food_meal")["quantity"] == 0
        assert bad.store.link(1, "food_meal")["quantity"] == 0
        assert good.preview_activity(1, "MEAL", "food_meal")["executable_now"]
        check = bad.preview_activity(1, "MEAL", "food_meal")
        assert check["start_allowed"] and not check["executable_now"]
        assert check["blocked_stage"] == "PURCHASE" and check["reason"] == reason
        money, stock = bad.store.actor(1)["money_cents"], bad.store.object("food_meal")["stock"]
        assert bad.start("meal", 1, "MEAL", "food_meal")["accepted"]
        assert finish(bad, "meal") == "FAILED"
        assert bad.minute == 15 and bad.store.actor(1)["location"] == "restaurant"
        assert bad.store.get_commitment("meal")["failure_reason"] == reason
        assert bad.store.actor(1)["money_cents"] == money
        assert bad.store.object("food_meal")["stock"] == stock
        assert bad.store.link(1, "food_meal")["quantity"] == 0
        validate_world(bad)


def test_catalog_and_old_raw_prompt_are_not_changed(protocol):
    with ContinuityWorld(":memory:") as baseline, build_world(":memory:", "s01", protocol) as panel:
        seed_demo(baseline)
        assert baseline.store.snapshot() == panel.store.snapshot()
        assert decision_prompt(baseline, 1) == projected_prompt(panel, mode=RAW)
        expected = baseline.store.snapshot()["objects"]
        for scenario_id in SCENARIO_IDS:
            with build_world(":memory:", scenario_id, protocol) as world:
                actual = world.store.snapshot()["objects"]
                assert [{key: value for key, value in obj.items() if key != "stock"}
                        for obj in actual] == [
                            {key: value for key, value in obj.items() if key != "stock"}
                            for obj in expected]
                assert world.parameters == baseline.parameters


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_intervention_and_metadata_do_not_leak_into_raw_prompt(protocol, scenario_id):
    altered = copy.deepcopy(protocol)
    for scenario in altered["scenarios"]:
        scenario["description"] = "SECRET_METADATA_EXPECTED_ANSWER_SENTINEL"
        scenario["source"] = "AUDIT_FAMILY_LABEL_SENTINEL"
    with build_world(":memory:", scenario_id, protocol) as original, build_world(
            ":memory:", scenario_id, altered) as annotated:
        for mode in CONDITIONS:
            system, user = projected_prompt(original, mode=mode)
            assert (system, user) == projected_prompt(annotated, mode=mode)
            assert not any(label in system + user for label in (
                "SECRET_METADATA", "AUDIT_FAMILY_LABEL", scenario_id, *FAMILIES))
        a_system, a_user = projected_prompt(original, mode=RAW)
        b_system, b_user = projected_prompt(original, mode=FEASIBLE)
        assert (a_system, a_user) == decision_prompt(original, 1)
        added = json.loads(b_user)
        options = added.pop("executable_options")
        assert added == json.loads(a_user)
        assert options == project_actions(original)["executable_options"]
        assert b_system == a_system + (
            " Choose one activity/target pair from executable_options. "
            "These are rule-feasible options, not a preference ranking.")
        assert "assessments" not in b_user
        assert observe(original, 1) == observe(annotated, 1)


def test_existing_fixture_path_is_never_reset(tmp_path, protocol):
    path = tmp_path / "existing.sqlite3"
    with build_world(path, "s01", protocol) as world:
        state_hash = digest(world.store.snapshot())
    file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):
        build_world(path, "s02", protocol)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == file_hash
    with ContinuityWorld(path) as retained:
        assert digest(retained.store.snapshot()) == state_hash


@pytest.mark.parametrize("field,value", [
    ("budgets", {"per_cell": 2, "session": 48}),
    ("budgets", {"per_cell": True, "session": 48}),
    ("repeats", 3),
    ("repeats", 2.0),
    ("conditions", [RAW]),
    ("thinking_disabled_explicitly", True),
    ("minimal_request", False),
    ("json_repair", True),
    ("fallback_action", True),
    ("max_activity_micro_steps", 0),
    ("timeout_seconds", float("nan")),
    ("timeout_seconds", 60.001),
    ("timeout_seconds", 3600),
    ("known_commitment_failures", ["OUT_OF_STOCK", "INSUFFICIENT_FUNDS", "CATCH_ALL"]),
])
def test_invalid_dimensions_or_request_contract_fail_closed(protocol, field, value):
    altered = copy.deepcopy(protocol)
    altered[field] = value
    with pytest.raises(ValueError):
        validate_protocol(altered)


def test_oversized_prompt_fails_before_any_decision_or_provider_creation(protocol):
    altered = copy.deepcopy(protocol)
    altered["max_prompt_chars"] = 1
    with pytest.raises(ValueError, match="CONTEXT_BUDGET"):
        build_world(":memory:", "s01", altered)


def test_recipe_mutation_outside_isolated_genesis_contract_is_rejected(protocol):
    altered = copy.deepcopy(protocol)
    altered["scenarios"][0]["recipe"]["actor"]["version"] = 42
    with pytest.raises(ValueError, match="GENESIS_ACTOR"):
        build_world(":memory:", "s01", altered)
    altered = copy.deepcopy(protocol)
    altered["scenarios"][0]["recipe"]["stock"]["game_a"] = 0
    with pytest.raises(ValueError, match="GENESIS_STOCK"):
        freeze_scenarios(altered)
    altered = copy.deepcopy(protocol)
    altered["scenarios"][0]["recipe"]["steps"] = [{"op": "SQL", "query": "UPDATE actors"}]
    with pytest.raises(ValueError, match="RECIPE_OPERATION"):
        freeze_scenarios(altered)


@pytest.mark.parametrize("field,value", [
    ("schema", "Q62_FIXED_STATE_PANEL_PROTOCOL_V2"),
    ("protocol_version", "q62_fixed_state_panel_v2"),
    ("seed", True),
    ("planned_cells", 48.0),
    ("planned_pairs", True),
    ("timeout_seconds", True),
    ("max_prompt_chars", False),
    ("known_commitment_failures", tuple([
        "OUT_OF_STOCK", "INSUFFICIENT_FUNDS", "OBJECT_UNAVAILABLE", "ITEM_NOT_OWNED"])),
])
def test_schema_and_protocol_field_types_are_strict(protocol, field, value):
    altered = copy.deepcopy(protocol)
    altered[field] = value
    with pytest.raises(ValueError):
        validate_protocol(altered)


@pytest.mark.parametrize("change", ["missing", "extra", "fatal_continue", "failure_unconditional"])
def test_stop_mapping_cannot_remove_guards_or_make_fatal_errors_continue(protocol, change):
    altered = copy.deepcopy(protocol)
    if change == "missing":
        altered["stop_mapping"].pop("HTTP_ERROR")
    elif change == "extra":
        altered["stop_mapping"]["UNREVIEWED_ERROR"] = "RECORD_AND_CONTINUE_NEXT_CELL"
    elif change == "fatal_continue":
        altered["stop_mapping"]["STATE_INVARIANT_FAILED"] = "RECORD_AND_CONTINUE_NEXT_CELL"
    else:
        altered["stop_mapping"]["COMMITMENT_FAILED"] = "RECORD_AND_CONTINUE_NEXT_CELL"
    with pytest.raises(ValueError, match="STOP_MAPPING"):
        validate_protocol(altered)
    assert protocol["stop_mapping"] == STOP_MAPPING


def test_semantic_hash_is_canonical_json_not_sqlite_file_bytes(tmp_path, protocol):
    with build_world(tmp_path / "world.sqlite3", "s05", protocol) as world:
        audit = world_fingerprint(world, protocol)
        assert audit["state_hash"] == hashlib.sha256(
            canonical_json(world.store.snapshot()).encode()).hexdigest()
        assert audit["observation_hash"] == digest(observe(world, 1))
        assert audit["state_hash"] != hashlib.sha256(
            (tmp_path / "world.sqlite3").read_bytes()).hexdigest()


def test_frozen_initial_state_facts_match_world_and_do_not_follow_later_effects(protocol, frozen):
    retained = copy.deepcopy(frozen)
    for scenario in frozen:
        with build_world(":memory:", scenario["scenario_id"], protocol) as world:
            audit = world_fingerprint(world, protocol)
            assert scenario["initial_projected_state"] == audit["initial_projected_state"]
            assert scenario["initial_projected_state"] == project_state(world)
            assert audit["state_hash"] == scenario["state_hash"]
            assert world.advance("later", world.minute + 1)["accepted"]
            assert project_state(world) != scenario["initial_projected_state"]
            assert digest(world.store.snapshot()) != scenario["state_hash"]
    assert frozen == retained


def test_explicit_version_loader_preserves_default_v1_and_its_bytes(protocol):
    repository = Path(__file__).resolve().parents[1]
    original = repository / "config/experimental/q6_2_fixed_state_panel_v1.json"
    assert hashlib.sha256(original.read_bytes()).hexdigest() == (
        "56f3165427255840c7810ba66170ae86f2a6f763455c394c810d772939bbfbea")
    assert load_protocol() == load_protocol(repository, version="v1") == protocol
    v2 = load_protocol(repository, version="v2")
    assert protocol_version(protocol) == "v1"
    assert protocol_version(v2) == "v2"
    assert v2["max_consecutive_timeouts"] == 2
    assert v2["single_timeout"] == v2["stop_mapping"]["PROVIDER_TIMEOUT"] == SINGLE_TIMEOUT_V2
    assert protocol["stop_mapping"]["PROVIDER_TIMEOUT"] == "STOP_SESSION"
    assert "max_consecutive_timeouts" not in protocol and "single_timeout" not in protocol
    assert v2["real_provider_requests_authorized_this_delivery"] == 0
    with pytest.raises(TypeError):
        load_protocol(repository, "v2")


def test_v2_changes_only_version_and_precisely_frozen_timeout_policy(protocol):
    v2 = load_protocol(version="v2")
    comparison = copy.deepcopy(v2)
    comparison["schema"] = protocol["schema"]
    comparison["protocol_version"] = protocol["protocol_version"]
    comparison.pop("max_consecutive_timeouts")
    comparison.pop("single_timeout")
    comparison["stop_mapping"]["PROVIDER_TIMEOUT"] = "STOP_SESSION"
    assert comparison == protocol
    assert digest(v2) != digest(protocol)


def test_v1_v2_actual_state_prompt_and_48_cell_fairness_are_identical(protocol, frozen):
    v2 = load_protocol(version="v2")
    v2_frozen = freeze_scenarios(v2)
    assert v2_frozen == frozen
    v1_cells = allocate_cells(protocol, frozen)
    v2_cells = allocate_cells(v2, v2_frozen)
    assert v1_cells == v2_cells
    assert fairness_fingerprint(protocol, frozen, v1_cells) == fairness_fingerprint(
        v2, v2_frozen, v2_cells)
    assert fairness_fingerprint(v2) == fairness_fingerprint(protocol, frozen, v1_cells)
    assert digest({"protocol": protocol, "scenarios": frozen, "cells": v1_cells}) != digest(
        {"protocol": v2, "scenarios": v2_frozen, "cells": v2_cells})


@pytest.mark.parametrize("research_change", ["state", "observation", "objects", "candidates",
                                            "a_prompt", "b_prompt", "schedule"])
def test_fairness_fingerprints_detect_research_inputs_not_timeout_metadata(protocol, frozen,
                                                                          research_change):
    expected = fairness_fingerprint(protocol, frozen)
    scenarios = copy.deepcopy(frozen)
    cells = allocate_cells(protocol, frozen)
    if research_change == "schedule":
        cells[0], cells[1] = cells[1], cells[0]
    elif research_change == "objects":
        scenarios[0]["object_candidates"][0]["qty"] += 1
    elif research_change in {"a_prompt", "b_prompt"}:
        mode = RAW if research_change == "a_prompt" else FEASIBLE
        scenarios[0]["prompt_hashes"][mode] = "0" * 64
    else:
        field = {"state": "state_hash", "observation": "observation_hash",
                 "candidates": "candidate_hash"}[research_change]
        scenarios[0][field] = "0" * 64
    actual = fairness_fingerprint(protocol, scenarios, cells)
    assert actual["fairness_fingerprint"] != expected["fairness_fingerprint"]
    changed_key = "schedule_fingerprint" if research_change == "schedule" else "scenario_fingerprint"
    assert actual[changed_key] != expected[changed_key]


@pytest.mark.parametrize("version", ["v3", "V2", "../v1", None, True, ["v1"]])
def test_version_loader_rejects_unknown_or_non_string_choices(version):
    with pytest.raises(ValueError, match="UNSUPPORTED_PANEL_PROTOCOL"):
        load_protocol(version=version)


def test_version_loader_does_not_silently_accept_wrong_file_identity(tmp_path, protocol):
    directory = tmp_path / "config/experimental"
    directory.mkdir(parents=True)
    (directory / "q6_2_fixed_state_panel_v2.json").write_text(
        canonical_json(protocol), encoding="utf-8")
    with pytest.raises(ValueError, match="FILE_VERSION_MISMATCH"):
        load_protocol(tmp_path, version="v2")


@pytest.mark.parametrize("field,value", [
    ("schema", "Q62_FIXED_STATE_PANEL_PROTOCOL_V1"),
    ("protocol_version", "q62_fixed_state_panel_v1"),
    ("max_consecutive_timeouts", 1),
    ("max_consecutive_timeouts", 3),
    ("max_consecutive_timeouts", True),
    ("max_consecutive_timeouts", 2.0),
    ("max_consecutive_timeouts", None),
    ("single_timeout", "RETRY"),
    ("single_timeout", "RECORD_AND_CONTINUE_NEXT_CELL"),
    ("single_timeout", None),
])
def test_v2_timeout_policy_and_schema_pairing_remain_strict(field, value):
    altered = load_protocol(version="v2")
    altered[field] = value
    with pytest.raises(ValueError):
        validate_protocol(altered)


@pytest.mark.parametrize("field,value", [
    ("max_consecutive_timeouts", 2), ("single_timeout", SINGLE_TIMEOUT_V2),
])
def test_v1_cannot_implicitly_receive_v2_timeout_behavior(protocol, field, value):
    altered = copy.deepcopy(protocol)
    altered[field] = value
    with pytest.raises(ValueError, match="TIMEOUT_POLICY"):
        validate_protocol(altered)


@pytest.mark.parametrize("version", ["v1", "v2"])
@pytest.mark.parametrize("status", ["PROVIDER_TIMEOUT", "HTTP_ERROR", "TRANSPORT_ERROR",
                                   "INVALID_MODEL_OUTPUT", "STATE_INVARIANT_FAILED",
                                   "EVIDENCE_INCOMPLETE", "REQUEST_BUDGET_EXHAUSTED"])
def test_both_versions_reject_arbitrary_stop_mapping_changes(version, status):
    altered = load_protocol(version=version)
    altered["stop_mapping"][status] = "UNREVIEWED_CONTINUE_OR_RETRY"
    with pytest.raises(ValueError, match="STOP_MAPPING"):
        validate_protocol(altered)


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_each_version_rejects_missing_extra_or_cross_version_timeout_mapping(version):
    protocol = load_protocol(version=version)
    for change in ("missing", "extra", "cross_version"):
        altered = copy.deepcopy(protocol)
        if change == "missing":
            altered["stop_mapping"].pop("PROVIDER_TIMEOUT")
        elif change == "extra":
            altered["stop_mapping"]["NEW_CONTINUABLE_STATUS"] = "RECORD_AND_CONTINUE_NEXT_CELL"
        else:
            altered["stop_mapping"]["PROVIDER_TIMEOUT"] = (
                SINGLE_TIMEOUT_V2 if version == "v1" else "STOP_SESSION")
        with pytest.raises(ValueError, match="STOP_MAPPING"):
            validate_protocol(altered)


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_protocol_capacity_does_not_allow_global_authorization(version):
    original = load_protocol(version=version)
    for value in (48, True, None, "0", 0.0):
        altered = copy.deepcopy(original)
        altered["real_provider_requests_authorized_this_delivery"] = value
        with pytest.raises(ValueError, match="GLOBAL_PANEL_AUTHORIZATION"):
            validate_protocol(altered)
