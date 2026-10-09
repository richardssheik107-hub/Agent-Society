"""M1.5 synthetic outcome cases, never evidence of real-model benefit.

Only the independent audit API is imported.  These fixtures do not reconstruct
the real session, import the model runner, inspect credentials or call a client.
"""
from __future__ import annotations

import ast
import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from social_sim.continuity.q6_2_outcome_audit import (
    build_human_review_packet,
    build_outcome_audit,
    cell_delta,
    paired_effects,
    render_report,
)


FAMILIES = (
    "OWNERSHIP", "POST_MEAL_NEED", "MEDIA_PROGRESS", "ACTIVITY_LOCATION",
    "MEAL_PAYMENT", "MEAL_SUPPLY",
)
PAIR_SCENARIOS = (
    (10, 1), (3, 2), (7, 2), (10, 2), (8, 2), (9, 2),
    (11, 2), (1, 1), (11, 1), (12, 1), (9, 1), (2, 2),
    (6, 2), (6, 1), (7, 1), (12, 2), (4, 1), (2, 1),
    (5, 1), (3, 1), (4, 2), (8, 1), (1, 2), (5, 2),
)
SCALAR_DELTAS = (
    "hunger_relief", "energy_change", "money_delta", "money_spent",
    "money_income", "minutes_elapsed", "work_minutes_change",
)
REPO = Path(__file__).resolve().parents[1]
CLI = REPO / "scripts" / "audit_q6_2_outcomes.py"


def state(**changes: object) -> dict:
    result = {
        "minute": 100, "money_cents": 10000, "hunger_milli": 800,
        "energy_milli": 600, "location": "home", "work_minutes": 0,
        "inventory": {"food_bread": 1, "food_meal": 0, "game_a": 0, "series_a": 0},
        "media_progress": {"series_a": {
            "watched": [], "offsets": {}, "view_counts": {},
            "next_episode": 1, "total_episodes": 10,
        }},
        "play_minutes": {"game_a": 0},
    }
    result.update(changes)
    return result


def row(condition: str = "A_RAW", *, pair: str = "p001", scenario: str = "s01",
        repeat: int = 1, family: str = "OWNERSHIP", **changes: object) -> dict:
    before = state()
    result = {
        "cell_id": "c001" if condition == "A_RAW" else "c002",
        "pair_id": pair, "scenario_id": scenario, "family": family,
        "repeat": repeat, "condition": condition,
        "status": "DECISION_ACCEPTED", "proposal_activity": "TRAVEL",
        "proposal_target": "restaurant", "strict_json_valid": True,
        "catalog_valid": True, "rule_checked": True, "start_accepted": True,
        "activity_completed": True, "effects_observed": True,
        "provider_model": "glm-5.3", "http_response_observed": True,
        "client_call_attempted": True, "invariants_valid": True,
        "before_state": before,
        "after_state": state(minute=115, hunger_milli=815, energy_milli=585,
                             location="restaurant"),
        "simulation_minutes": 15, "latency_seconds": 0.125,
        "input_tokens": 100, "output_tokens": 5, "reasoning_tokens": 2,
        "prompt_chars": 200,
    }
    result.update(changes)
    return result


def timeout(condition: str, **changes: object) -> dict:
    return row(
        condition, status="PROVIDER_TIMEOUT", effects_observed=False,
        proposal_activity=None, proposal_target=None, strict_json_valid=None,
        catalog_valid=None, rule_checked=None, start_accepted=None,
        activity_completed=None, http_response_observed=False,
        provider_model=None, input_tokens=None, output_tokens=None,
        reasoning_tokens=None, latency_seconds=60.01, **changes,
    )


def meal(condition: str = "B_FEASIBLE", **changes: object) -> dict:
    options = {
        "proposal_activity": "MEAL", "proposal_target": "food_meal",
        "after_state": state(minute=135, money_cents=8800, hunger_milli=230,
                             energy_milli=670, location="restaurant"),
        "simulation_minutes": 35,
    }
    options.update(changes)
    return row(condition, **options)


def panel() -> list[dict]:
    """Forty-eight synthetic allocations, including two asymmetric timeouts."""
    result = []
    valid_a = valid_b = 0
    for index, (scenario, repeat) in enumerate(PAIR_SCENARIOS, 1):
        metadata = {
            "pair": f"p{index:03d}", "scenario": f"s{scenario:02d}",
            "family": FAMILIES[(scenario - 1) // 2], "repeat": repeat,
        }
        for condition in ("A_RAW", "B_FEASIBLE"):
            if (index == 14 and condition == "A_RAW") or (
                index == 21 and condition == "B_FEASIBLE"
            ):
                item = timeout(condition, **metadata)
            elif condition == "A_RAW":
                valid_a += 1
                item = meal(condition, **metadata) if valid_a <= 5 else row(condition, **metadata)
            else:
                valid_b += 1
                item = meal(condition, **metadata)
                if valid_b <= 4:
                    item.update({
                        "proposal_target": "food_bread", "simulation_minutes": 10,
                        "after_state": state(
                            minute=110, money_cents=9700, hunger_milli=500,
                            energy_milli=630,
                            inventory={"food_bread": 0, "food_meal": 0,
                                       "game_a": 0, "series_a": 0},
                        ),
                    })
            item["cell_id"] = f"c{len(result) + 1:03d}"
            result.append(item)
    return result


def serialized(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


@pytest.mark.parametrize(
    ("hunger_after", "expected"), [(230, 570), (800, 0), (815, -15)],
    ids=("net-relief", "no-net-change", "increased-hunger-not-clipped"),
)
def test_hunger_relief_preserves_direction(hunger_after, expected):
    source = row(after_state=state(hunger_milli=hunger_after))
    delta = cell_delta(source)
    assert delta["hunger_before"] == 800
    assert delta["hunger_after"] == hunger_after
    assert delta["hunger_relief"] == expected


@pytest.mark.parametrize(("energy_after", "expected"), [(670, 70), (600, 0), (585, -15)])
def test_energy_change_is_after_minus_before(energy_after, expected):
    assert cell_delta(row(after_state=state(energy_milli=energy_after)))["energy_change"] == expected


@pytest.mark.parametrize(
    ("money_after", "delta", "spent", "income"),
    [(8800, -1200, 1200, 0), (10000, 0, 0, 0), (10500, 500, 0, 500)],
)
def test_money_net_sign_and_separate_spending_income(money_after, delta, spent, income):
    result = cell_delta(row(after_state=state(money_cents=money_after)))
    assert result["money_delta"] == delta
    assert result["money_spent"] == spent
    assert result["money_income"] == income


def test_simulation_minutes_and_api_seconds_do_not_get_added():
    result = cell_delta(row(latency_seconds=1.25))
    assert result["minutes_elapsed"] == 15
    assert result["simulation_minutes"] == 15
    assert result["latency_seconds"] == 1.25
    assert result["minutes_elapsed"] != 16.25


def test_travel_completion_is_not_meal_completion_or_hunger_relief():
    travel, eating = cell_delta(row()), cell_delta(meal())
    assert travel["proposal_activity"] == "TRAVEL"
    assert eating["proposal_activity"] == "MEAL"
    assert travel["activity_completed"] is True
    assert eating["activity_completed"] is True
    assert travel["hunger_relief"] == -15
    assert eating["hunger_relief"] == 570
    assert travel["minutes_elapsed"] == 15
    assert eating["minutes_elapsed"] == 35


def test_location_change_keeps_both_endpoints():
    result = cell_delta(row())
    assert result["location_before"] == "home"
    assert result["location_after"] == "restaurant"
    assert result["location_changed"] is True
    assert cell_delta(row(after_state=state()))["location_changed"] is False


def test_timeout_equal_database_snapshots_are_not_zero_observed_effects():
    source = timeout("A_RAW", after_state=state())
    result = cell_delta(source)
    assert result["effects_observed"] is False
    assert result["after_state"] is None
    for field in SCALAR_DELTAS:
        assert result[field] is None, field
    assert result["hunger_after"] is None
    assert result["location_after"] is None
    assert result["location_changed"] is None
    for field in ("inventory", "media", "play", "work"):
        assert result[field]["status"] == "UNKNOWN", field


@pytest.mark.parametrize("field", ["hunger_milli", "energy_milli", "money_cents", "minute"])
def test_missing_scalar_does_not_become_zero(field):
    before = state()
    before.pop(field)
    names = {
        "hunger_milli": "hunger_relief", "energy_milli": "energy_change",
        "money_cents": "money_delta", "minute": "minutes_elapsed",
    }
    result = cell_delta(row(before_state=before))
    assert result[names[field]] is None


@pytest.mark.parametrize("value", [True, False, float("nan"), float("inf"), "800", -1, 1001])
def test_invalid_hunger_values_are_unknown_not_coerced(value):
    assert cell_delta(row(before_state=state(hunger_milli=value)))["hunger_relief"] is None


def test_inventory_net_change_is_not_proof_of_gross_consumption():
    unchanged = cell_delta(meal())
    assert unchanged["inventory"]["status"] == "OBSERVED"
    assert all(value == 0 for value in unchanged["inventory"]["delta"].values())
    assert "consumed_quantity" not in unchanged["inventory"]
    assert "gross_consumption" not in unchanged["inventory"]
    bread = cell_delta(meal(after_state=state(
        inventory={"food_bread": 0, "food_meal": 0, "game_a": 1, "series_a": 0},
    )))
    assert bread["inventory"]["delta"]["food_bread"] == -1
    assert bread["inventory"]["delta"]["game_a"] == 1


def test_missing_inventory_is_unknown_not_empty_or_passed():
    before = state()
    before.pop("inventory")
    result = cell_delta(row(before_state=before))
    assert result["inventory"]["status"] == "UNKNOWN"
    assert result["inventory"]["delta"] is None


def test_partial_inventory_retains_known_delta_without_imputing_missing_object():
    before = state(inventory={"food_bread": 1})
    after = state(inventory={"food_bread": 0, "game_a": 1})
    result = cell_delta(row(before_state=before, after_state=after))
    assert result["inventory"]["status"] == "UNKNOWN"
    assert result["inventory"]["delta"]["food_bread"] == -1
    assert result["inventory"]["delta"]["game_a"] is None
    assert "series_a" not in result["inventory"]["delta"]


def test_unselected_watch_and_play_are_not_exercised_even_with_known_progress():
    result = cell_delta(meal())
    assert result["media"]["status"] == "NOT_EXERCISED"
    assert result["play"]["status"] == "NOT_EXERCISED"
    assert result["media"]["before"] is not None
    assert result["media"]["after"] is not None
    assert result["play"]["before"] is not None
    assert result["play"]["after"] is not None
    assert result["work"]["status"] == "NOT_EXERCISED"


@pytest.mark.parametrize(("activity", "source_key", "result_key"), [
    ("WATCH", "media_progress", "media"), ("PLAY", "play_minutes", "play"),
])
def test_exercised_capability_with_unobserved_values_is_unknown(activity, source_key, result_key):
    before = state()
    before.pop(source_key)
    result = cell_delta(row(proposal_activity=activity, before_state=before))
    assert result[result_key]["status"] == "UNKNOWN"


def test_play_duration_change_is_object_specific():
    result = cell_delta(row(
        proposal_activity="PLAY", proposal_target="game_a",
        after_state=state(play_minutes={"game_a": 30}),
    ))
    assert result["play"]["status"] == "OBSERVED"
    assert result["play"]["delta"]["game_a"] == 30


def test_watch_reports_verified_episode_and_offset_change():
    before, after = state(), state()
    before["media_progress"]["series_a"]["offsets"] = {"1": 0}
    after["media_progress"]["series_a"].update({
        "watched": [1], "offsets": {"1": 30}, "view_counts": {"1": 1}, "next_episode": 2,
    })
    result = cell_delta(row(
        proposal_activity="WATCH", proposal_target="series_a",
        before_state=before, after_state=after,
    ))
    assert result["media"]["status"] == "OBSERVED"
    assert result["media"]["newly_watched"] == [1]
    assert result["media"]["offset_changes"]["1"] == 30


def test_watch_partial_offset_values_do_not_claim_fully_observed_media_effect():
    before, after = state(), state()
    before["media_progress"]["series_a"]["offsets"] = {"1": 0}
    after["media_progress"]["series_a"].update({"watched": [1], "offsets": {"1": None}})
    result = cell_delta(row(
        proposal_activity="WATCH", proposal_target="series_a",
        before_state=before, after_state=after,
    ))
    assert result["media"]["status"] == "UNKNOWN"
    assert result["media"]["newly_watched"] == [1]
    assert result["media"]["offset_changes"]["1"] is None


def test_pair_initial_state_mismatch_is_rejected_without_comparing_unequal_people():
    with pytest.raises(ValueError):
        paired_effects([row(), meal(before_state=state(hunger_milli=700))])


def test_verified_work_minutes_are_distinct_from_an_event_name():
    before, after = state(), state()
    before.pop("work_minutes")
    after.pop("work_minutes")
    unknown = cell_delta(row(
        proposal_activity="WORK", proposal_target=None, before_state=before,
        after_state=after, domain_facts={"event_type": "WORK_COMPLETED"},
    ))
    assert unknown["work"]["status"] == "UNKNOWN"
    assert unknown["work_minutes_change"] is None
    known = cell_delta(row(
        proposal_activity="WORK", proposal_target=None,
        domain_facts={"work_minutes_before": 10, "work_minutes_after": 70},
    ))
    assert known["work"]["status"] == "OBSERVED"
    assert known["work_minutes_change"] == 60


def test_complete_pair_deltas_use_b_minus_a_not_reverse():
    result = paired_effects([row(), meal()])
    pair = result["pairs"][0]
    assert pair["complete"] is True
    assert pair["B_minus_A"]["hunger_relief"] == 585
    assert pair["B_minus_A"]["energy_change"] == 85
    assert pair["B_minus_A"]["money_delta"] == -1200
    assert pair["B_minus_A"]["minutes_elapsed"] == 20


@pytest.mark.parametrize("field", ["scenario_id", "repeat", "family"])
def test_pair_must_match_scenario_repeat_and_family(field):
    b = meal()
    b[field] = {"scenario_id": "s02", "repeat": 2, "family": "MEDIA_PROGRESS"}[field]
    with pytest.raises(ValueError):
        paired_effects([row(), b])


def test_duplicate_condition_in_one_pair_is_rejected():
    with pytest.raises(ValueError):
        paired_effects([row(), row(cell_id="c003"), meal()])


def test_missing_allocated_condition_is_rejected_not_invented():
    with pytest.raises(ValueError):
        paired_effects([row()])


def test_synthetic_48_cells_24_pairs_and_22_complete_pairs_are_all_retained():
    rows = panel()
    audit = build_outcome_audit(rows)
    assert len(rows) == len(audit["cells"]) == 48
    assert len(audit["paired_effects"]["pairs"]) == 24
    assert sum(pair["complete"] for pair in audit["paired_effects"]["pairs"]) == 22
    indexed = {pair["pair_id"]: pair for pair in audit["paired_effects"]["pairs"]}
    assert indexed["p014"]["A"]["status"] == "PROVIDER_TIMEOUT"
    assert indexed["p021"]["B"]["status"] == "PROVIDER_TIMEOUT"
    assert indexed["p014"]["A"]["hunger_relief"] is None
    assert indexed["p021"]["B"]["hunger_relief"] is None
    assert all(value is None for value in indexed["p014"]["B_minus_A"].values())
    assert all(value is None for value in indexed["p021"]["B_minus_A"].values())


def test_all_six_family_denominators_preserve_incomplete_pairs():
    effects = paired_effects(panel())
    assert set(effects["by_family"]) == set(FAMILIES)
    for family in FAMILIES:
        stats = effects["by_family"][family]["B_minus_A"]["hunger_relief"]
        expected_known = 3 if family in {"POST_MEAL_NEED", "MEDIA_PROGRESS"} else 4
        assert stats["known"] == expected_known
        assert stats["eligible"] == 4
        assert stats["missing"] == 4 - expected_known
    assert effects["aggregates"]["B_minus_A"]["hunger_relief"]["coverage"] == {
        "numerator": 22, "denominator": 24, "value": 22 / 24,
    }


def test_missing_metric_with_observed_other_effects_preserves_metric_specific_coverage():
    b = meal()
    b["after_state"].pop("hunger_milli")
    effects = paired_effects([row(), b])
    assert effects["pairs"][0]["complete"] is True
    hunger = effects["aggregates"]["B_minus_A"]["hunger_relief"]
    energy = effects["aggregates"]["B_minus_A"]["energy_change"]
    assert hunger["known"] == 0 and hunger["mean"] is None
    assert energy["known"] == 1 and energy["mean"] == 85


def test_paired_stats_include_mean_median_range_signs_and_coverage():
    rows = [row(pair="p001"), meal(pair="p001")]
    rows += [row(pair="p002", cell_id="c003"), row("B_FEASIBLE", pair="p002", cell_id="c004")]
    rows += [row(pair="p003", cell_id="c005"), timeout("B_FEASIBLE", pair="p003", cell_id="c006")]
    result = paired_effects(rows)
    stats = result["aggregates"]["B_minus_A"]["hunger_relief"]
    assert stats["mean"] == 292.5
    assert stats["median"] == 292.5
    assert stats["min"] == 0
    assert stats["max"] == 585
    assert stats["positive"] == 1
    assert stats["negative"] == 0
    assert stats["zero"] == 1
    assert stats["known"] == 2
    assert stats["missing"] == 1
    assert stats["eligible"] == 3
    assert stats["coverage"] == {"numerator": 2, "denominator": 3, "value": 2 / 3}


def test_negative_paired_effect_is_not_lost_by_positive_need_interpretation():
    stats = paired_effects([meal("A_RAW"), row("B_FEASIBLE")])["aggregates"]["B_minus_A"]["hunger_relief"]
    assert stats["mean"] == -585
    assert stats["negative"] == 1
    assert stats["positive"] == 0


def test_no_complete_denominator_yields_null_not_zero():
    result = paired_effects([timeout("A_RAW"), timeout("B_FEASIBLE")])
    for stats in result["aggregates"]["B_minus_A"].values():
        assert stats["mean"] is None
        assert stats["median"] is None
        assert stats["min"] is None
        assert stats["max"] is None
        assert stats["known"] == 0
    empty = paired_effects([])
    for stats in empty["aggregates"]["B_minus_A"].values():
        assert stats["coverage"]["value"] is None


def test_report_contains_all_twenty_four_pairs_and_timeout_caveats():
    report = render_report(build_outcome_audit(panel()))
    for index in range(1, 25):
        assert f"p{index:03d}" in report
    for family in FAMILIES:
        assert family in report
    assert "PROVIDER_TIMEOUT" in report
    assert "TRAVEL" in report and "MEAL" in report
    assert "EXPLORATORY_POST_HOC" in report
    assert "NO_CLEAR_DIFFERENCE" in report
    assert "UNRESOLVED" in report
    assert "NOT_TESTED" in report
    assert "INSUFFICIENT_EVIDENCE" in report


def test_exploratory_markers_do_not_overwrite_historical_conclusion_or_invent_weights():
    audit = build_outcome_audit(panel())
    payload = serialized(audit)
    assert "EXPLORATORY_POST_HOC" in payload
    assert "NO_CLEAR_DIFFERENCE" in payload
    assert "UNRESOLVED" in payload
    assert "HUMAN_REVIEW_COMPLETED" in payload and '"NO"' in payload
    assert "NEW_REAL_PROVIDER_REQUESTS" in payload
    for forbidden in ("human_likeness_score", "global_utility_score", "weighted_score"):
        assert forbidden not in payload
    assert "OBSERVED_IMPROVEMENT" not in payload


def test_paired_costs_use_complete_backend_matched_pairs_only():
    a, b = row(input_tokens=100, latency_seconds=1), meal(input_tokens=150, latency_seconds=3)
    timeout_a, usable_b = timeout("A_RAW", pair="p002", cell_id="c003"), meal(
        pair="p002", cell_id="c004", input_tokens=9999, latency_seconds=100,
    )
    costs = build_outcome_audit([a, b, timeout_a, usable_b])["costs"]
    assert costs["input_tokens"]["A_mean"] == 100
    assert costs["input_tokens"]["B_mean"] == 150
    assert costs["input_tokens"]["B_minus_A_mean"] == 50
    assert costs["input_tokens"]["increase_percent"] == 50
    assert costs["input_tokens"]["known_pairs"] == 1
    assert costs["input_tokens"]["planned_pairs"] == 2
    assert costs["latency_seconds"]["B_minus_A_mean"] == 2


def test_zero_baseline_cost_denominator_does_not_create_percentage():
    costs = build_outcome_audit([
        row(input_tokens=0), meal(input_tokens=10),
    ])["costs"]["input_tokens"]
    assert costs["A_mean"] == 0
    assert costs["B_minus_A_mean"] == 10
    assert costs["increase_percent"] is None


def test_audit_inputs_are_not_mutated():
    rows = panel()
    original = copy.deepcopy(rows)
    build_outcome_audit(rows)
    build_human_review_packet(rows)
    assert rows == original


def test_arbitrary_untrusted_model_text_and_credentials_are_not_exported():
    sentinel = "DO_NOT_EXPORT_RAW_SECRET_COMPLETION_73f9"
    a, b = row(), meal()
    for source in (a, b):
        source.update({
            "raw_completion": sentinel, "hidden_reasoning": sentinel,
            "Authorization": sentinel, "api_key": sentinel,
            "provider_error_body": sentinel,
        })
        source["before_state"]["untrusted_prompt"] = sentinel
    audit = build_outcome_audit([a, b])
    packet, key = build_human_review_packet([a, b])
    assert sentinel not in serialized(audit)
    assert sentinel not in render_report(audit)
    assert sentinel not in packet
    assert sentinel not in serialized(key)


@pytest.mark.parametrize("field", ["start_accepted", "activity_completed"])
def test_boolean_result_fields_cannot_smuggle_raw_provider_text(field):
    sentinel = "DO_NOT_EXPORT_RAW_MODEL_STATUS_219c"
    source = row(**{field: sentinel})
    delta = cell_delta(source)
    assert delta[field] is None
    assert sentinel not in serialized(delta)


def test_human_review_packet_is_paired_blind_and_unscored():
    rows = panel()
    packet, private_key = build_human_review_packet(rows, seed=20261008)
    assert isinstance(packet, str)
    assert private_key
    assert "A_RAW" not in packet
    assert "B_FEASIBLE" not in packet
    for source in rows:
        assert source["cell_id"] not in packet
    for label in ("行为合理", "不合理", "信息不足", "理由", "不确定性"):
        assert label in packet
    assert "HUMAN_REVIEW_COMPLETED=NO" in packet.replace(" ", "")
    assert "A_RAW" in serialized(private_key)
    assert "B_FEASIBLE" in serialized(private_key)
    assert "TRAVEL" in packet and "MEAL" in packet
    assert "reviewer_score" not in serialized(private_key)


def test_blind_packet_randomization_is_reproducible_but_not_fixed_by_condition():
    rows = panel()
    first = build_human_review_packet(rows, seed=20261008)
    assert first == build_human_review_packet(rows, seed=20261008)
    assert first != build_human_review_packet(rows, seed=20261009)


def test_new_cli_does_not_offer_provider_permission():
    result = subprocess.run(
        [sys.executable, str(CLI), "--help"], cwd=REPO,
        check=False, capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "--source-session" in result.stdout
    assert "--output" in result.stdout
    assert "--verify-integrity" in result.stdout
    assert "--allow-provider" not in result.stdout


def test_missing_source_fails_without_credentials_or_network(tmp_path):
    sentinel = "NEVER_PRINT_OR_USE_TEST_CREDENTIAL_4cc8"
    environment = os.environ.copy()
    environment.update({
        "CONTINUITY_API_KEY": sentinel,
        "CONTINUITY_BASE_URL": "http://127.0.0.1:1/no-real-service",
        "CONTINUITY_MODEL": sentinel,
    })
    output = tmp_path / "new-audit"
    result = subprocess.run(
        [sys.executable, str(CLI), "--source-session", str(tmp_path / "missing-source"),
         "--output", str(output), "--verify-integrity"],
        cwd=REPO, env=environment, check=False, capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert sentinel not in result.stdout + result.stderr
    assert not output.exists()


def test_no_allow_provider_argument_is_accepted(tmp_path):
    result = subprocess.run(
        [sys.executable, str(CLI), "--source-session", str(tmp_path / "missing-source"),
         "--output", str(tmp_path / "output"), "--allow-provider"],
        cwd=REPO, check=False, capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "unrecognized arguments: --allow-provider" in result.stderr


def test_existing_output_directory_is_never_overwritten(tmp_path):
    output = tmp_path / "existing-output"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("preserved-user-file", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(CLI), "--source-session", str(tmp_path / "missing-source"),
         "--output", str(output), "--verify-integrity"],
        cwd=REPO, check=False, capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert marker.read_text(encoding="utf-8") == "preserved-user-file"
    assert list(output.iterdir()) == [marker]


def test_new_analysis_entrypoints_do_not_import_execution_or_client_modules():
    sources = [CLI, REPO / "src/social_sim/continuity/q6_2_outcome_audit.py"]
    for path in sources:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        for module in imported:
            assert "decision" not in module
            assert "client" not in module
            assert "q6_1" not in module
            assert not module.endswith("q6_2_panel")
            assert not module.endswith("q6_2_panel_fixtures")
        assert "load_provider_config(" not in source
        assert "os.environ[" not in source
        assert "getenv(" not in source
