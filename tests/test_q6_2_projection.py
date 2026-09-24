"""Q6.2：可执行性与执行一致、投影无副作用、对照提示隔离；全部离线。"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from social_sim.continuity import ContinuityWorld, validate_world
from social_sim.continuity.action_projection import FEASIBLE, RAW, project_actions, projected_prompt
from social_sim.continuity.benchmark import seed_demo
from social_sim.continuity.context import decision_prompt
from social_sim.continuity.decision import ActivityDecisionRunner
from social_sim.continuity.models import TIMED_ACTIVITIES, digest
from social_sim.continuity.q6_2 import EXECUTION_BASE, load_source, replay


@pytest.fixture
def world():
    with ContinuityWorld(":memory:") as w:
        seed_demo(w)
        yield w


def finish(world, request_id):
    while (c := world.store.commitment(1)) and c["status"] == "ACTIVE":
        until = world.minute + min(15, c["remaining_min"])
        assert world.advance(f"{request_id}:t{until}", until)["accepted"]


def test_unowned_game_is_excluded_and_not_given_for_free(world):
    check = world.preview_activity(1, "PLAY", "game_a")
    assert not check["executable_now"]
    assert not check["start_allowed"]
    assert check["reason"] == "ITEM_NOT_OWNED"
    assert {"activity": "PLAY", "target": "game_a"} not in project_actions(world)["executable_options"]
    assert world.store.link(1, "game_a")["quantity"] == 0
    assert world.store.actor(1)["money_cents"] == 300000


def test_owned_game_becomes_feasible_and_actual_play_accumulates(world):
    assert world.act("buy", 1, "BUY", "game_a")["accepted"]
    assert world.preview_activity(1, "PLAY", "game_a")["executable_now"]
    assert world.start("play", 1, "PLAY", "game_a")["accepted"]
    finish(world, "play")
    assert world.store.link(1, "game_a")["play_minutes"] == 45
    validate_world(world)


def test_projection_is_sql_read_only_and_does_not_write_then_rollback(world):
    before = world.store.snapshot()
    events = world.store.events()
    changes = world.store.db.total_changes
    statements = []
    world.store.db.set_trace_callback(statements.append)
    try:
        one = project_actions(world)
        two = project_actions(world)
        projected_prompt(world)
        assert one == two
    finally:
        world.store.db.set_trace_callback(None)
    assert world.store.db.total_changes == changes
    assert world.store.snapshot() == before
    assert world.store.events() == events
    assert world.store.db.execute("SELECT count(*) FROM commands").fetchone()[0] == 0
    assert world.store.db.execute("SELECT count(*) FROM decision_attempts").fetchone()[0] == 0
    assert not any(s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE"))
                   for s in statements)


def test_read_snapshot_actually_rejects_writes_and_restores_flag(world):
    with pytest.raises(sqlite3.OperationalError):
        with world.store.read_snapshot():
            world.store.db.execute("UPDATE objects SET stock=0")
    assert not world.store.db.in_transaction
    assert world.store.db.execute("PRAGMA query_only").fetchone()[0] == 0
    assert world.act("buy", 1, "BUY", "game_a")["accepted"]


def test_nested_read_snapshot_preserves_existing_transaction(world):
    with world.store.transaction():
        with world.store.read_snapshot():
            with world.store.read_snapshot():
                assert world.store.db.in_transaction
                assert world.store.db.execute("PRAGMA query_only").fetchone()[0] == 1
        assert world.store.db.in_transaction
        assert world.store.db.execute("PRAGMA query_only").fetchone()[0] == 0
    assert not world.store.db.in_transaction


@pytest.mark.parametrize("reason", ["OUT_OF_STOCK", "INSUFFICIENT_FUNDS"])
def test_meal_later_purchase_failure_is_predicted_without_changing_start_semantics(world, reason):
    if reason == "OUT_OF_STOCK":
        world.store.db.execute("UPDATE objects SET stock=0 WHERE id='food_meal'")
    else:
        actor = world.store.actor(1)
        actor["money_cents"] = 0
        world.store.put_actor(actor)
    check = world.preview_activity(1, "MEAL", "food_meal")
    assert check["start_allowed"] and not check["executable_now"]
    assert check["blocked_stage"] == "PURCHASE" and check["reason"] == reason
    result = world.start("meal", 1, "MEAL", "food_meal")
    assert result["accepted"]  # 旧语义：先接纳出发，不被投影偷偷改成启动拒绝。
    finish(world, "meal")
    assert world.store.get_commitment("meal")["status"] == "FAILED"
    assert world.store.get_commitment("meal")["failure_reason"] == reason
    assert world.store.actor(1)["location"] == "restaurant"


def test_owned_food_does_not_require_new_stock_or_money(world):
    world.act("move", 1, "MOVE", "restaurant")
    world.act("buy", 1, "BUY", "food_meal")
    world.store.db.execute("UPDATE objects SET stock=0 WHERE id='food_meal'")
    actor = world.store.actor(1)
    actor["money_cents"] = 0
    world.store.put_actor(actor)
    check = world.preview_activity(1, "MEAL", "food_meal")
    assert check["executable_now"] and not check["requires_purchase"]


@pytest.mark.parametrize("hunger", [0, 245, 800, 1000])
def test_hunger_does_not_become_an_invented_meal_prohibition(world, hunger):
    actor = world.store.actor(1)
    actor["hunger_milli"] = hunger
    world.store.put_actor(actor)
    assert world.preview_activity(1, "MEAL", "food_meal")["executable_now"]
    assert {"activity": "MEAL", "target": "food_meal"} in project_actions(world)["executable_options"]


@pytest.mark.parametrize("activity,target,reason", [
    ("PLAY", "food_meal", "CAPABILITY_MISMATCH"),
    ("WATCH", "missing", "OBJECT_NOT_FOUND"),
    ("MEAL", None, "MISSING_TARGET"),
    ("TRAVEL", "nowhere", "UNKNOWN_DESTINATION"),
    ("TRAVEL", "home", "ALREADY_AT_DESTINATION"),
    ("WORK", None, "NOT_AT_ACTIVITY_LOCATION"),
    ("DANCE", None, "UNSUPPORTED_ACTIVITY"),
])
def test_preview_and_start_share_rule_rejections(world, activity, target, reason):
    check = world.preview_activity(1, activity, target)
    assert not check["executable_now"] and check["reason"] == reason
    assert world.start("test", 1, activity, target)["reason"] == reason


def test_busy_and_paused_actors_have_no_new_options(world):
    world.start("watch", 1, "WATCH", "series_a")
    assert project_actions(world)["executable_options"] == []
    world.control("pause", 1, "PAUSE")
    assert project_actions(world)["executable_options"] == []
    with pytest.raises(ValueError):
        projected_prompt(world)


def test_preview_resolves_alias_and_current_episode_not_a_fresh_episode_one(world):
    world.start("watch", 1, "WATCH", "series_a")
    finish(world, "watch")
    check = world.preview_activity(1, "WATCH", "测试剧")
    assert check["executable_now"] and check["resolved_episode"] == 2
    assert not world.preview_activity(1, "WATCH", "series_a", episode=1)["executable_now"]
    assert world.preview_activity(1, "WATCH", "series_a", episode=1, rewatch=True)["executable_now"]


def test_unavailable_object_is_rejected_even_if_owned(world):
    world.act("buy", 1, "BUY", "game_a")
    world.set_available("off", "game_a", False)
    assert world.preview_activity(1, "PLAY", "game_a")["reason"] == "OBJECT_UNAVAILABLE"


def test_projection_does_not_bypass_stale_version_guard(world):
    projection = project_actions(world)
    world.advance("tick", 1)
    r = world.start("later", 1, "WATCH", "series_a", expected_version=projection["state_version"])
    assert r["reason"] == "STALE_STATE"


def test_actual_execution_rechecks_stock_after_an_earlier_projection(world):
    world.act("move", 1, "MOVE", "restaurant")
    assert world.preview_activity(1, "MEAL", "food_meal")["executable_now"]
    world.store.db.execute("UPDATE objects SET stock=0 WHERE id='food_meal'")
    result = world.start("later", 1, "MEAL", "food_meal")
    assert result["commitment_status"] == "FAILED"
    assert world.store.actor(1)["money_cents"] == 300000


def test_a_matches_original_bytes_b_adds_only_feasible_options(world):
    assert projected_prompt(world, mode=RAW) == decision_prompt(world, 1)
    a_sys, a_user = projected_prompt(world, mode=RAW)
    b_sys, b_user = projected_prompt(world, mode=FEASIBLE)
    b_body = json.loads(b_user)
    options = b_body.pop("executable_options")
    assert b_body == json.loads(a_user)
    assert b_sys.startswith(a_sys)
    assert options == project_actions(world)["executable_options"]
    assert "assessments" not in b_user
    assert "acceptable_action_set" not in b_user
    assert not any(o["activity"] == "BUY" for o in options)


def test_invalid_modes_and_context_budget_fail_closed(world):
    with pytest.raises(ValueError):
        projected_prompt(world, mode="UNKNOWN")
    with pytest.raises(ValueError, match="BUDGET"):
        projected_prompt(world, max_chars=10)


def test_object_output_limit_bounds_candidate_pairs(world):
    p = project_actions(world, limit=1)
    assert p["object_candidates"] == 1
    assert p["pairs_checked"] == len(TIMED_ACTIVITIES) + 4 + 3
    assert len(p["executable_options"]) <= p["pairs_checked"]
    with pytest.raises(ValueError):
        project_actions(world, limit=11)


@pytest.mark.parametrize("variant", ["home", "restaurant", "office", "poor", "no_stock", "owned",
                                     "busy", "paused", "unavailable", "finished_series"])
def test_all_projected_pairs_match_actual_static_execution(world, variant):
    if variant in ("restaurant", "office"):
        world.act("location", 1, "MOVE", variant)
    elif variant == "poor":
        actor = world.store.actor(1)
        actor["money_cents"] = 0
        world.store.put_actor(actor)
    elif variant == "no_stock":
        world.store.db.execute("UPDATE objects SET stock=0")
    elif variant == "owned":
        world.act("own", 1, "BUY", "game_a")
    elif variant in ("busy", "paused"):
        world.start("busy", 1, "WATCH", "series_a")
        if variant == "paused":
            world.control("pause", 1, "PAUSE")
    elif variant == "unavailable":
        world.set_available("off", "series_a", False)
    elif variant == "finished_series":
        link = world.store.link(1, "series_a")
        link["watched"] = list(range(1, 121))
        world.store.put_link(1, "series_a", link)
    for check in project_actions(world)["assessments"]:
        # 副本执行只用于测试 oracle。生产 preview 绝不复制或执行世界。
        with ContinuityWorld(":memory:") as copy:
            world.store.db.backup(copy.store.db)
            result = copy.start("oracle", 1, check["activity"], check["target"])
            if result["accepted"]:
                finish(copy, "oracle")
                completed = copy.store.get_commitment("oracle")["status"] == "COMPLETED"
            else:
                completed = False
            assert completed == check["executable_now"], (variant, check, result)


def test_projected_prompt_is_used_in_the_actual_decision_path(world):
    prompts = []
    class Fake:
        async def complete(self, system, user):
            prompts.append(json.loads(user))
            return SimpleNamespace(raw_text='{"activity":"WATCH","target":"series_a"}')
    runner = ActivityDecisionRunner(world, Fake(), prompt_builder=projected_prompt)
    assert asyncio.run(runner.decide("one"))["status"] == "DECISION_ACCEPTED"
    finish(world, "one")
    assert asyncio.run(runner.decide("two"))["status"] == "DECISION_ACCEPTED"
    assert "executable_options" in prompts[0]
    media = next(o for o in prompts[1]["observation"]["objects"] if o["id"] == "series_a")
    assert media["next_episode"] == 2
    assert {"activity": "PLAY", "target": "game_a"} not in prompts[1]["executable_options"]


def test_model_ignoring_projection_is_still_rejected_not_silently_replaced(world):
    class Fake:
        async def complete(self, system, user):
            return SimpleNamespace(raw_text='{"activity":"PLAY","target":"game_a"}')
    runner = ActivityDecisionRunner(world, Fake(), prompt_builder=projected_prompt)
    row = asyncio.run(runner.decide("bad"))
    assert row["status"] == "RULE_REJECTED"
    assert row["result"]["reason"] == "ITEM_NOT_OWNED"
    assert world.store.commitment(1) is None
    assert world.minute == 0


def test_report_replay_is_not_claimed_to_be_original_or_new_model_evidence(tmp_path):
    result = replay(tmp_path / "report")
    assert result["result"] == "PASS"
    assert result["provider_requests"] == 0 and result["llm_calls"] == 0
    assert not result["source_artifact_verified"] and not result["live_ab_executed"]
    rows = [json.loads(s) for s in (tmp_path / "report/replay_rows.jsonl").read_text().splitlines()]
    assert [r["hunger_after"] for r in rows] == [815, 245, 0, 0]
    assert [r["choice_in_projected_options"] for r in rows] == [True, True, True, False]
    assert rows[2]["immediate_meal_repeat"]
    assert rows[3]["chosen_preview"]["reason"] == "ITEM_NOT_OWNED"
    assert rows[3]["raw_target_object_present"]
    assert rows[3]["RAW_PROPOSAL_EXECUTABLE"] is False
    assert rows[3]["PROJECTED_CANDIDATE_PRESENT"] is False
    assert rows[3]["RULE_RESULT"] == "ITEM_NOT_OWNED"
    assert result["short_horizon_state_continuity"] == "NOT_RETESTED"


def synthetic_source(tmp_path):
    # 仅构造历史产物“格式”的合成测试，不冒充真实 provider 证据。
    root = tmp_path / "synthetic-source"
    replay(root)
    rows = [json.loads(s) for s in (root / "replay_rows.jsonl").read_text().splitlines()]
    summary = {"source_commit": EXECUTION_BASE, "attempt_id": "attempt_3", "mode": "REAL_PROVIDER_PILOT"}
    (root / "summary.json").write_text(json.dumps(summary))
    (root / "decisions.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return root


def file_hashes(root):
    return {str(p.relative_to(root)): digest(p.read_bytes().hex()) for p in root.rglob("*") if p.is_file()}


def test_local_artifact_replay_verifies_fields_and_leaves_sources_untouched(tmp_path):
    source = synthetic_source(tmp_path)
    before = file_hashes(source)
    result = replay(tmp_path / "verification", source_artifact=source)
    assert result["source_artifact_verified"]
    assert file_hashes(source) == before


def test_source_state_mismatch_is_reported_not_accepted(tmp_path):
    source = synthetic_source(tmp_path)
    path = source / "decisions.jsonl"
    rows = [json.loads(s) for s in path.read_text().splitlines()]
    rows[1]["money_after"] += 1
    path.write_text("\n".join(json.dumps(r) for r in rows))
    result = replay(tmp_path / "bad", source_artifact=source)
    assert result["result"] == "SOURCE_REPLAY_MISMATCH"
    assert not result["source_artifact_verified"]
    assert result["comparison_mismatches"][0]["fields"] == ["money_after"]
    assert "money_after" in result["comparison_mismatches"][0]["expected_sha256"]
    assert "money_after" in result["comparison_mismatches"][0]["actual_sha256"]


def test_source_inventory_and_media_are_compared_at_each_step(tmp_path):
    source = synthetic_source(tmp_path)
    path = source / "decisions.jsonl"
    rows = [json.loads(s) for s in path.read_text().splitlines()]
    rows[1]["inventory_delta"] = {"food_meal": 99}
    rows[2]["media_progress_after"] = {"series_a": {"watched": [99]}}
    path.write_text("\n".join(json.dumps(r) for r in rows))
    result = replay(tmp_path / "mismatch", source_artifact=source)
    assert not result["source_artifact_verified"]
    assert [m["decision_index"] for m in result["comparison_mismatches"]] == [2, 3]
    assert result["comparison_mismatches"][0]["fields"] == ["inventory_delta"]
    assert result["comparison_mismatches"][1]["fields"] == ["media_progress_after"]


def test_raw_source_extras_are_not_copied_to_output(tmp_path):
    source = synthetic_source(tmp_path)
    path = source / "decisions.jsonl"
    rows = [json.loads(s) for s in path.read_text().splitlines()]
    for row in rows:
        row["raw_reasoning"] = "secret-marker-never-copy"
        row["api_key"] = "secret-marker-never-copy"
    path.write_text("\n".join(json.dumps(r) for r in rows))
    output = tmp_path / "safe"
    assert replay(output, source_artifact=source)["source_artifact_verified"]
    for file in output.iterdir():
        assert b"secret-marker-never-copy" not in file.read_bytes()


def test_wrong_source_commit_is_not_treated_as_same_experiment(tmp_path):
    source = synthetic_source(tmp_path)
    (source / "summary.json").write_text('{"source_commit":"not-the-baseline"}')
    with pytest.raises(ValueError, match="PROVENANCE"):
        load_source(source)


def test_no_source_or_existing_output_is_never_silently_replaced(tmp_path):
    with pytest.raises(FileNotFoundError):
        replay(tmp_path / "out", source_artifact=tmp_path / "missing")
    assert not (tmp_path / "out").exists()
    source = synthetic_source(tmp_path)
    with pytest.raises(ValueError, match="INSIDE_SOURCE"):
        replay(source / "new", source_artifact=source)
    with pytest.raises(FileExistsError):
        replay(source)


def test_cli_has_no_real_provider_flag_and_offline_execution_works(tmp_path):
    root = Path(__file__).resolve().parents[1]
    cli = root / "scripts/run_q6_2_projection_offline.py"
    denied = subprocess.run([sys.executable, str(cli), "--allow-provider"], capture_output=True, timeout=10)
    assert denied.returncode != 0
    done = subprocess.run([sys.executable, str(cli), "--output", str(tmp_path / "cli")],
                          capture_output=True, text=True, timeout=15)
    assert done.returncode == 0, done.stderr
    assert "PROVIDER_REQUESTS=0" in done.stdout
    assert "SOURCE_ARTIFACT_VERIFIED=False" in done.stdout


def test_baseline_four_steps_have_unchanged_state_and_events(world):
    expected = json.loads((Path(__file__).parent / "fixtures/q62_q61_baseline_hashes.json").read_text())
    sequence = (("TRAVEL", "restaurant"), ("MEAL", "food_meal"),
                ("MEAL", "food_meal"), ("PLAY", "game_a"))
    for index, (activity, target) in enumerate(sequence, 1):
        result = world.start(f"q6_1:{index}", 1, activity, target)
        finish(world, f"q6_1:{index}")
        baseline = expected[index - 1]
        assert result == baseline["result"]
        assert digest(world.store.snapshot()) == baseline["state_hash"]
        assert digest(world.store.events()) == baseline["events_hash"]
    validate_world(world)
