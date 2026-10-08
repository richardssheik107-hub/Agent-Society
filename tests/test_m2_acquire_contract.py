"""M2 独立输入合同与旧 Q6.1/Q6.2 字节冻结；所有提案使用 fake client。"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from social_sim.continuity import ContinuityWorld, ObjectDefinition, initial_actor, validate_world
from social_sim.continuity.action_projection import FEASIBLE, RAW, project_actions, projected_prompt
from social_sim.continuity.benchmark import seed_demo
from social_sim.continuity.context import decision_prompt, parse_proposal
from social_sim.continuity.decision import ActivityDecisionRunner
from social_sim.continuity.models import RuleParameters, digest


@pytest.mark.parametrize("enabled", [False, True])
def test_legacy_prompts_projection_and_genesis_are_frozen(enabled):
    """53b1244 main 原合同固定值；启用新能力也不改变旧入口输入。"""
    with ContinuityWorld(":memory:", acquire_enabled=enabled) as world:
        seed_demo(world)
        assert world.parameters == RuleParameters()
        assert digest(decision_prompt(world, 1)) == (
            "07beed9c986016949b96e8b4d27de3862f66e7e229cc353805e89066f4dd6749")
        assert digest(projected_prompt(world, mode=RAW)) == (
            "07beed9c986016949b96e8b4d27de3862f66e7e229cc353805e89066f4dd6749")
        assert digest(projected_prompt(world, mode=FEASIBLE)) == (
            "b5df53946fa6d310490830f0be52182064e23ab07e0b384bb47043e9f0ab201c")
        assert digest(project_actions(world)) == (
            "28b29f8f972e156392213eeceb67197c7f14d2036eb38d0a692fac42f244f273")
        assert digest(world.store.snapshot()) == (
            "b51280a21758ab18749da2324e97ea1b3c8f1c2d68c64847f2f85a07b778aca1")
        assert digest(world.store.events()) == (
            "bbfc7574c025a652eafb42d6ffc25d142403e6b73cc56094f48f98cabe0c4b28")
        assert all(option["activity"] != "ACQUIRE" for option in project_actions(world)[
            "executable_options"])


def test_old_parser_and_decision_runner_do_not_opt_in_implicitly(tmp_path):
    with pytest.raises(ValueError, match="UNSUPPORTED_ACTIVITY"):
        parse_proposal('{"activity":"ACQUIRE","target":"game_a"}')

    class Fake:
        async def complete(self, _system, _user):
            return SimpleNamespace(raw_text='{"activity":"ACQUIRE","target":"game_a"}')

    with ContinuityWorld(tmp_path / "legacy.sqlite", acquire_enabled=True) as world:
        seed_demo(world)
        before = world.store.snapshot()
        result = asyncio.run(ActivityDecisionRunner(world, Fake()).decide("old-runner"))
        assert result["status"] == "INVALID_MODEL_OUTPUT"
        assert world.store.snapshot() == before
        assert world.store.link(1, "game_a")["quantity"] == 0


def test_m2_parser_accepts_acquire_without_expanding_old_parser():
    from social_sim.continuity.m2_acquire import parse_m2_proposal

    proposal = '{"activity":"ACQUIRE","target":"game_a"}'
    assert parse_m2_proposal(proposal) == {"activity": "ACQUIRE", "target": "game_a"}
    assert parse_m2_proposal('{"activity":"PLAY","target":"game_a"}') == {
        "activity": "PLAY", "target": "game_a"}
    with pytest.raises(ValueError, match="UNSUPPORTED_ACTIVITY"):
        parse_proposal(proposal)


@pytest.mark.parametrize("raw", [
    '{"activity":"ACQUIRE","activity":"PLAY","target":"game_a"}',
    '{"activity":"ACQUIRE","target":null}',
    '{"activity":"ACQUIRE","target":1}',
    '{"activity":"ACQUIRE","target":""}',
    '{"activity":"ACQUIRE","target":"game_a","quantity":1}',
    '{"activity":"ACQUIRE","target":"game_a","ownership":true}',
    '{"activity":"BUY","target":"game_a"}',
    '{"activity":"SLEEP","target":"game_a"}',
    '{"activity":"ACQUIRE"}',
    '[]',
    'not json',
])
def test_m2_parser_rejects_state_generation_and_malformed_intents(raw):
    from social_sim.continuity.m2_acquire import parse_m2_proposal

    with pytest.raises((ValueError, TypeError)):
        parse_m2_proposal(raw)


def test_m2_projection_shares_rules_and_is_strictly_sql_read_only():
    from social_sim.continuity.m2_acquire import m2_decision_prompt, project_m2_actions

    with ContinuityWorld(":memory:", acquire_enabled=True) as world:
        seed_demo(world)
        before = world.store.snapshot()
        events = world.store.events()
        changes = world.store.db.total_changes
        statements = []
        world.store.db.set_trace_callback(statements.append)
        try:
            first = project_m2_actions(world)
            second = project_m2_actions(world)
            m2_decision_prompt(world)
            assert first == second
        finally:
            world.store.db.set_trace_callback(None)
        assert first["schema"] == "M2_ACTION_PROJECTION_V1"
        assert {"activity": "ACQUIRE", "target": "game_a"} in first["startable_options"]
        assert {"activity": "PLAY", "target": "game_a"} not in first["startable_options"]
        assert first["startable_options"] == sorted(
            first["startable_options"], key=lambda option: (option["activity"], option["target"] or ""))
        assert world.store.db.total_changes == changes
        assert world.store.snapshot() == before and world.store.events() == events
        assert not any(statement.lstrip().upper().startswith((
            "INSERT", "UPDATE", "DELETE", "REPLACE")) for statement in statements)
        assert world.store.db.execute("SELECT count(*) FROM commands").fetchone()[0] == 0
        assert world.store.db.execute("SELECT count(*) FROM decision_attempts").fetchone()[0] == 0


def test_m2_remote_candidate_is_startable_without_promising_future_stock():
    from social_sim.continuity.m2_acquire import project_m2_actions

    with ContinuityWorld(":memory:", acquire_enabled=True) as world:
        game = ObjectDefinition(
            "game_a", "M2异地合成游戏", "GAME", ("playable", "purchasable"),
            price_cents=3000, seller="office",
        )
        world.seed([initial_actor(1, 10000), initial_actor(2, 10000, "office")], [(game, 1)])
        projection = project_m2_actions(world)
        option = {"activity": "ACQUIRE", "target": "game_a"}
        assert option in projection["startable_options"]
        assessment = next(check for check in projection["assessments"]
                          if check["activity"] == "ACQUIRE" and check["target"] == "game_a")
        assert assessment["start_allowed"] and not assessment["executable_now"]
        assert assessment["purchase_feasible_at_snapshot"]
        assert assessment["reason"] == "REQUIRES_TRAVEL"
        assert world.act("competing-purchase", 2, "BUY", "game_a")["accepted"]
        assert option not in project_m2_actions(world)["startable_options"]
        assert not world.start("later", 1, "ACQUIRE", "game_a")["accepted"]
        assert world.store.link(1, "game_a")["quantity"] == 0
        validate_world(world)


@pytest.mark.parametrize("variant", ["poor", "stock_zero", "owned", "unavailable", "busy"])
def test_m2_projection_excludes_shared_rule_failures(variant):
    from social_sim.continuity.m2_acquire import project_m2_actions

    with ContinuityWorld(":memory:", acquire_enabled=True) as world:
        if variant in ("poor", "stock_zero"):
            game = ObjectDefinition(
                "game_a", "M2合成游戏", "GAME", ("playable", "purchasable"),
                price_cents=3000, seller="home",
            )
            world.seed([initial_actor(1, 0 if variant == "poor" else 10000)], [
                (game, 0 if variant == "stock_zero" else 1)])
        else:
            seed_demo(world)
            if variant == "owned":
                assert world.act("buy", 1, "BUY", "game_a")["accepted"]
            elif variant == "unavailable":
                assert world.set_available("off", "game_a", False)["accepted"]
            else:
                assert world.start("busy", 1, "WATCH", "series_a")["accepted"]
        assert {"activity": "ACQUIRE", "target": "game_a"} not in project_m2_actions(world)[
            "startable_options"]
        validate_world(world)


def test_m2_input_tools_require_an_explicitly_enabled_world():
    from social_sim.continuity.m2_acquire import (
        M2DecisionRunner, ScriptedM2Client, m2_decision_prompt, project_m2_actions,
    )

    with ContinuityWorld(":memory:") as world:
        seed_demo(world)
        for operation in (project_m2_actions, m2_decision_prompt):
            with pytest.raises(ValueError, match="ACQUIRE_DISABLED"):
                operation(world)
        with pytest.raises(ValueError, match="ACQUIRE_DISABLED"):
            M2DecisionRunner(world, ScriptedM2Client([]))


def test_m2_does_not_accept_a_provider_or_unrestricted_client():
    from social_sim.continuity.m2_acquire import M2DecisionRunner

    class UnexpectedClient:
        async def complete(self, _system, _user):
            pytest.fail("unrestricted client must never be called")

    with ContinuityWorld(":memory:", acquire_enabled=True) as world:
        seed_demo(world)
        with pytest.raises((TypeError, ValueError)):
            M2DecisionRunner(world, UnexpectedClient())


def test_scripted_proposal_acquire_restart_then_separate_play_forms_complete_loop(tmp_path):
    from social_sim.continuity.m2_acquire import (
        M2DecisionRunner, ScriptedM2Client, finish_m2_commitment, m2_decision_prompt,
    )
    from social_sim.continuity.models import SCHEMA_VERSION

    path = tmp_path / "end-to-end.sqlite"
    first_client = ScriptedM2Client(['{"activity":"ACQUIRE","target":"game_a"}'])
    with ContinuityWorld(path, acquire_enabled=True) as world:
        seed_demo(world)
        initial = world.store.actor(1)
        assert world.store.link(1, "game_a")["quantity"] == 0
        assert world.store.object("game_a")["stock"] == 100
        assert world.preview_activity(1, "PLAY", "game_a")["reason"] == "ITEM_NOT_OWNED"
        runner = M2DecisionRunner(world, first_client)
        decision = asyncio.run(runner.decide("m2:acquire"))
        assert decision["status"] == "DECISION_ACCEPTED"
        assert first_client.call_count == 1 and first_client.provider_request_count == 0
        finish_m2_commitment(world, "m2:acquire")
        assert first_client.call_count == 1
        commitment = world.store.get_commitment("m2:acquire")
        assert commitment["activity"] == "ACQUIRE" and commitment["status"] == "COMPLETED"
        assert commitment["elapsed_min"] == 0 and world.minute == 0
        assert world.store.actor(1)["money_cents"] == 297000
        assert world.store.actor(1)["version"] > initial["version"]
        assert world.store.object("game_a")["stock"] == 99
        assert world.store.link(1, "game_a")["quantity"] == 1
        assert world.store.link(1, "game_a")["play_minutes"] == 0
        assert not any(c["activity"] == "PLAY" for c in world.store.snapshot()["commitments"])
        assert world.store.meta("schema_version") == str(SCHEMA_VERSION)
        before_restart = world.store.snapshot()
        events = world.store.events()
        assert sum(event["kind"] == "PURCHASED" for event in events) == 1
        replay = asyncio.run(runner.decide("m2:acquire"))
        assert replay["status"] == "ALREADY_RECORDED" and first_client.call_count == 1
        assert world.store.snapshot() == before_restart and world.store.events() == events
        validate_world(world)
    second_client = ScriptedM2Client(['{"activity":"PLAY","target":"game_a"}'])
    with ContinuityWorld(path) as restored:
        assert restored.acquire_enabled
        assert restored.store.snapshot() == before_restart and restored.store.events() == events
        assert restored.store.get_commitment("m2:acquire")["status"] == "COMPLETED"
        assert restored.store.link(1, "game_a")["quantity"] == 1
        assert restored.preview_activity(1, "PLAY", "game_a")["executable_now"]
        feedback = json.loads(m2_decision_prompt(restored)[1])
        assert next(item for item in feedback["observation"]["objects"]
                    if item["id"] == "game_a")["qty"] == 1
        runner = M2DecisionRunner(restored, second_client)
        play = asyncio.run(runner.decide("m2:play"))
        assert play["status"] == "DECISION_ACCEPTED"
        assert restored.store.get_commitment("m2:play")["activity"] == "PLAY"
        finish_m2_commitment(restored, "m2:play")
        assert second_client.call_count == 1 and second_client.provider_request_count == 0
        assert restored.store.get_commitment("m2:play")["status"] == "COMPLETED"
        assert restored.store.get_commitment("m2:play")["elapsed_min"] == 45
        assert restored.minute == 45
        assert restored.store.actor(1)["money_cents"] == 297000
        assert restored.store.object("game_a")["stock"] == 99
        assert restored.store.link(1, "game_a")["quantity"] == 1
        assert restored.store.link(1, "game_a")["play_minutes"] == 45
        assert restored.store.actor(1)["version"] > before_restart["actors"][0]["version"]
        assert sum(event["kind"] == "PURCHASED" for event in restored.store.events()) == 1
        assert sum(event["kind"] == "COMMITMENT_STARTED" for event in restored.store.events()) == 2
        assert sum(event["kind"] == "COMMITMENT_COMPLETED" for event in restored.store.events()) == 2
        before_replay = restored.store.snapshot()
        assert asyncio.run(runner.decide("m2:play"))["status"] == "ALREADY_RECORDED"
        assert second_client.call_count == 1 and restored.store.snapshot() == before_replay
        validate_world(restored)


def test_invalid_scripted_proposal_is_recorded_without_state_and_not_retried():
    from social_sim.continuity.m2_acquire import M2DecisionRunner, ScriptedM2Client

    with ContinuityWorld(":memory:", acquire_enabled=True) as world:
        seed_demo(world)
        before = world.store.snapshot()
        client = ScriptedM2Client(['{"activity":"ACQUIRE","target":"game_a","quantity":2}'])
        runner = M2DecisionRunner(world, client)
        assert asyncio.run(runner.decide("bad"))["status"] == "INVALID_MODEL_OUTPUT"
        assert world.store.snapshot() == before
        assert asyncio.run(runner.decide("bad"))["status"] == "ALREADY_ATTEMPTED"
        assert client.call_count == 1 and client.provider_request_count == 0


def test_outside_catalog_proposal_has_no_hidden_buy_or_fallback():
    from social_sim.continuity.m2_acquire import M2DecisionRunner, ScriptedM2Client

    with ContinuityWorld(":memory:", acquire_enabled=True) as world:
        seed_demo(world)
        before = world.store.snapshot()
        client = ScriptedM2Client(['{"activity":"ACQUIRE","target":"invented-game"}'])
        result = asyncio.run(M2DecisionRunner(world, client).decide("outside"))
        assert result["status"] == "OUTSIDE_CATALOG"
        assert world.store.snapshot() == before and world.store.commitment(1) is None
        assert not any(event["kind"] == "PURCHASED" for event in world.store.events())
        assert client.call_count == 1 and client.provider_request_count == 0


def test_paused_zero_time_purchase_is_not_advanced_by_finishing_helper():
    from social_sim.continuity.m2_acquire import finish_m2_commitment

    with ContinuityWorld(":memory:", acquire_enabled=True) as world:
        item = ObjectDefinition(
            "game_a", "M2异地游戏", "GAME", ("playable", "purchasable"),
            price_cents=3000, seller="office",
        )
        world.seed([initial_actor(1, 10000)], [(item, 1)])
        world.start("acquire", 1, "ACQUIRE", "game_a")
        world.advance("arrival", 15)
        world.control("pause", 1, "PAUSE")
        before = world.store.snapshot()
        events = world.store.events()
        finish_m2_commitment(world, "acquire")
        assert world.store.snapshot() == before and world.store.events() == events
        assert world.store.get_commitment("acquire")["status"] == "PAUSED"
        assert world.store.link(1, "game_a")["quantity"] == 0


def test_one_remote_alias_proposal_drives_all_micro_steps_without_more_client_calls():
    from social_sim.continuity.m2_acquire import (
        M2DecisionRunner, ScriptedM2Client, finish_m2_commitment,
    )

    with ContinuityWorld(":memory:", acquire_enabled=True) as world:
        item = ObjectDefinition(
            "game_a", "M2异地游戏", "GAME", ("playable", "purchasable"),
            price_cents=3000, seller="office", aliases=("m2-game-alias",),
        )
        world.seed([initial_actor(1, 10000)], [(item, 1)])
        client = ScriptedM2Client(['{"activity":"ACQUIRE","target":"M2-GAME-ALIAS"}'])
        runner = M2DecisionRunner(world, client)
        assert asyncio.run(runner.decide("acquire"))["status"] == "DECISION_ACCEPTED"
        assert world.store.get_commitment("acquire")["target"] == "game_a"
        assert asyncio.run(runner.decide("while-travelling"))["status"] == "COMMITMENT_PRESENT"
        final = finish_m2_commitment(world, "acquire")
        assert final["commitment_status"] == "COMPLETED"
        assert final["elapsed_simulation_minutes"] == 15
        assert [phase["commitment"]["phase"] for phase in final["phases"]][:2] == ["MOVE", "BUY"]
        assert client.call_count == 1 and client.provider_request_count == 0
        assert world.store.actor(1)["money_cents"] == 7000
        assert world.store.link(1, "game_a")["quantity"] == 1
        validate_world(world)


def test_scripted_decision_budget_survives_restart_and_is_shared_by_runners(tmp_path):
    from social_sim.continuity.m2_acquire import M2DecisionRunner, ScriptedM2Client

    path = tmp_path / "fake-budget.sqlite"
    with ContinuityWorld(path, acquire_enabled=True) as world:
        seed_demo(world)
        client = ScriptedM2Client(['{"activity":"ACQUIRE","target":"game_a"}'])
        assert asyncio.run(M2DecisionRunner(world, client, max_calls=1).decide("acquire"))[
            "status"] == "DECISION_ACCEPTED"
        assert client.call_count == 1
    with ContinuityWorld(path) as restored:
        client = ScriptedM2Client(['{"activity":"PLAY","target":"game_a"}'])
        before = restored.store.snapshot()
        result = asyncio.run(M2DecisionRunner(restored, client, max_calls=1).decide("play"))
        assert result["status"] == "REQUEST_BUDGET_EXHAUSTED"
        assert client.call_count == 0 and client.provider_request_count == 0
        assert restored.store.snapshot() == before


def test_m2_candidate_limit_and_prompt_budget_fail_closed():
    from social_sim.continuity.m2_acquire import m2_decision_prompt, project_m2_actions

    with ContinuityWorld(":memory:", acquire_enabled=True) as world:
        seed_demo(world)
        limited = project_m2_actions(world, limit=1)
        object_targets = {check["target"] for check in limited["assessments"]
                          if check["activity"] in {"ACQUIRE", "MEAL", "WATCH", "PLAY"}}
        assert object_targets == {"food_bread"}
        assert {"activity": "ACQUIRE", "target": "game_a"} not in limited["startable_options"]
        for limit in (0, 11, True):
            with pytest.raises(ValueError):
                project_m2_actions(world, limit=limit)
        with pytest.raises(ValueError, match="budget"):
            m2_decision_prompt(world, max_chars=1)


def test_scripted_invalid_output_never_persists_raw_text():
    from social_sim.continuity.m2_acquire import M2DecisionRunner, ScriptedM2Client

    with ContinuityWorld(":memory:", acquire_enabled=True) as world:
        seed_demo(world)
        raw = '{"activity":"ACQUIRE","target":"game_a","raw":"SECRET_SYNTHETIC_SENTINEL"}'
        client = ScriptedM2Client([raw])
        assert asyncio.run(M2DecisionRunner(world, client).decide("invalid"))[
            "status"] == "INVALID_MODEL_OUTPUT"
        rows = world.store.db.execute("SELECT data FROM decision_attempts").fetchall()
        assert len(rows) == 1 and "SECRET_SYNTHETIC_SENTINEL" not in rows[0][0]
        assert "raw_text" not in rows[0][0]
        assert client.provider_request_count == 0


@pytest.mark.parametrize("first_proposal", [
    '{"activity":"ACQUIRE","target":"game_a"}', 'invalid synthetic proposal',
])
def test_decision_request_id_cannot_be_replayed_for_another_actor(first_proposal):
    from social_sim.continuity.m2_acquire import M2DecisionRunner, ScriptedM2Client

    with ContinuityWorld(":memory:", acquire_enabled=True) as world:
        seed_demo(world, actors=2)
        first_client = ScriptedM2Client([first_proposal])
        asyncio.run(M2DecisionRunner(world, first_client, actor_id=1).decide("same"))
        before = world.store.snapshot()
        events = world.store.events()
        recorded = world.store.db.execute(
            "SELECT data FROM decision_attempts WHERE id='same'").fetchone()[0]
        assert json.loads(recorded)["actor_id"] == 1
        other_client = ScriptedM2Client(['{"activity":"ACQUIRE","target":"game_a"}'])
        result = asyncio.run(M2DecisionRunner(world, other_client, actor_id=2).decide("same"))
        assert result["status"] == "REQUEST_ID_REUSE"
        assert other_client.call_count == 0 and result["fake_calls"] == 0
        assert world.store.link(2, "game_a")["quantity"] == 0
        assert world.store.snapshot() == before and world.store.events() == events
        assert world.store.db.execute(
            "SELECT data FROM decision_attempts WHERE id='same'").fetchone()[0] == recorded
        validate_world(world)


@pytest.mark.parametrize("prior_command", ["BUY", "REJECTED_PLAY"])
def test_unrelated_primitive_or_rejected_command_cannot_be_a_decision_replay(prior_command):
    from social_sim.continuity.m2_acquire import M2DecisionRunner, ScriptedM2Client

    with ContinuityWorld(":memory:", acquire_enabled=True) as world:
        seed_demo(world)
        if prior_command == "BUY":
            assert world.act("same", 1, "BUY", "game_a")["accepted"]
        else:
            assert not world.start("same", 1, "PLAY", "game_a")["accepted"]
        before = world.store.snapshot()
        events = world.store.events()
        client = ScriptedM2Client(['{"activity":"ACQUIRE","target":"game_a"}'])
        result = asyncio.run(M2DecisionRunner(world, client).decide("same"))
        assert result["status"] == "REQUEST_ID_REUSE"
        assert client.call_count == 0 and result["fake_calls"] == 0
        assert world.store.snapshot() == before and world.store.events() == events
        assert world.store.db.execute("SELECT count(*) FROM decision_attempts").fetchone()[0] == 0
        validate_world(world)


@pytest.mark.parametrize("competing_actor", [1, 2])
def test_competing_command_cannot_replace_a_rejected_decision_on_replay(monkeypatch, competing_actor):
    from social_sim.continuity.m2_acquire import M2DecisionRunner, ScriptedM2Client

    with ContinuityWorld(":memory:", acquire_enabled=True) as world:
        seed_demo(world, actors=2)
        client = ScriptedM2Client(['{"activity":"ACQUIRE","target":"game_a"}'])

        async def competing_fake(_system, _user):
            client.call_count += 1
            activity, target = ("WATCH", "series_a") if competing_actor == 1 else (
                "ACQUIRE", "game_a")
            assert world.start("same", competing_actor, activity, target)["accepted"]
            return '{"activity":"ACQUIRE","target":"game_a"}'

        monkeypatch.setattr(client, "complete", competing_fake)
        runner = M2DecisionRunner(world, client, actor_id=1)
        rejected = asyncio.run(runner.decide("same"))
        assert rejected["result"]["reason"] == "REQUEST_ID_REUSE"
        assert not rejected["result"]["accepted"]
        before = world.store.snapshot()
        events = world.store.events()
        replay = asyncio.run(runner.decide("same"))
        assert replay["status"] == "REQUEST_ID_REUSE" and replay["fake_calls"] == 0
        assert client.call_count == 1 and world.store.link(1, "game_a")["quantity"] == 0
        assert world.store.snapshot() == before and world.store.events() == events
        validate_world(world)


@pytest.mark.parametrize("competing_actor", [1, 2])
def test_interrupted_attempt_does_not_infer_ownership_of_competing_command(competing_actor):
    from social_sim.continuity.m2_acquire import M2_VERSION, M2DecisionRunner, ScriptedM2Client

    with ContinuityWorld(":memory:", acquire_enabled=True) as world:
        seed_demo(world, actors=2)
        with world.store.transaction():
            world.store.db.execute("INSERT INTO decision_attempts VALUES(?,?,?)", (
                "interrupted", "M2_REQUEST_STARTED", json.dumps({
                    "schema": M2_VERSION, "actor_id": 1})))
        assert world.start("interrupted", competing_actor, "ACQUIRE", "game_a")["accepted"]
        before = world.store.snapshot()
        events = world.store.events()
        client = ScriptedM2Client(['{"activity":"ACQUIRE","target":"game_a"}'])
        result = asyncio.run(M2DecisionRunner(world, client, actor_id=1).decide("interrupted"))
        assert result["status"] == "ALREADY_ATTEMPTED" and result["fake_calls"] == 0
        assert "result" not in result
        assert client.call_count == 0 and world.store.snapshot() == before
        assert world.store.events() == events
        validate_world(world)
