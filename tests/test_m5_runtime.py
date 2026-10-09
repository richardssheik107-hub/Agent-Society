"""M5 runtime uses real world effects and prelimited requests, without network."""
from __future__ import annotations

import asyncio
import json

import pytest

from social_sim.continuity.models import ObjectDefinition, initial_actor
from social_sim.decision.client import DecisionReply
from social_sim.longrun.config import LongRunConfig
from social_sim.longrun.runner import LongRunRunner
from social_sim.longrun.session import LongRunSession, SessionError


class SequenceClient:
    mode = "offline"
    provider_request_count = 0

    def __init__(self, proposals):
        self.proposals = iter(proposals)
        self.call_count = 0

    async def complete(self, system, user):
        self.call_count += 1
        return DecisionReply(next(self.proposals))


def proposal(activity, target=None):
    return json.dumps({"activity": activity, "target": target})


def remote_fixture(world, config):
    world.seed([initial_actor(1, 10000)], [
        (ObjectDefinition("game_a", "合成游戏", "GAME", ("purchasable", "playable"),
                          price_cents=3000, duration_min=45, seller="office"), 2),
        (ObjectDefinition("series_a", "合成剧集", "SERIES", ("watchable",),
                          duration_min=45, episodes=100, seller="home"), 1),
        (ObjectDefinition("food_meal", "合成饭", "FOOD", ("purchasable", "edible"),
                          price_cents=500, duration_min=30, satiety_milli=700,
                          calories_kcal=500), 200),
    ])


def create(tmp_path, name="test", config=None):
    return LongRunSession.create(tmp_path, name, config or LongRunConfig(sim_days=1),
                                 {"execution_commit": "0" * 40}, seed_world=remote_fixture)


def test_acquire_then_play_and_work_persist_actual_effects(tmp_path):
    config = LongRunConfig(sim_days=1, max_decisions=3)
    with create(tmp_path, config=config) as session:
        client = SequenceClient([proposal("ACQUIRE", "game_a"), proposal("PLAY", "game_a"),
                                 proposal("WORK")])
        result = asyncio.run(LongRunRunner(session, client).run())
        assert result["stop_reason"] == "REQUEST_BUDGET_REACHED"
        assert client.call_count == result["decisions"] == 3
        assert session.world.minute == 330
        actor = session.world.store.actor(1)
        assert actor["work_minutes"] == 270 and actor["money_cents"] == 9700
        assert session.world.store.link(1, "game_a")["quantity"] == 1
        assert session.world.store.link(1, "game_a")["play_minutes"] == 45
        assert session.world.store.object("game_a")["stock"] == 1
        events = session.world.store.events()
        assert sum(e["kind"] == "PURCHASED" for e in events) == 1
        assert len(session.export_data()["steps"]) > client.call_count
        assert result["provider_requests_reserved"] == 0


def test_accepted_activity_continues_after_decision_budget_is_full(tmp_path):
    with create(tmp_path, config=LongRunConfig(sim_days=1, max_decisions=1)) as session:
        client = SequenceClient([proposal("SLEEP")])
        result = asyncio.run(LongRunRunner(session, client).run())
        assert result["stop_reason"] == "REQUEST_BUDGET_REACHED"
        assert session.world.minute == 360
        assert session.world.store.commitment(1) is None
        assert session.world.store.get_commitment("m5:test:000001")["status"] == "COMPLETED"
        assert client.call_count == 1


def test_meal_travels_buys_and_eats_without_extra_model_calls(tmp_path):
    with create(tmp_path, config=LongRunConfig(sim_days=1, max_decisions=1)) as session:
        client = SequenceClient([proposal("MEAL", "food_meal")])
        asyncio.run(LongRunRunner(session, client).run())
        assert session.world.minute == 45 and client.call_count == 1
        actor = session.world.store.actor(1)
        assert actor["money_cents"] == 9500 and actor["calories_kcal"] == 500
        assert actor["hunger_milli"] == 145
        assert session.world.store.link(1, "food_meal")["quantity"] == 0
        assert session.world.store.object("food_meal")["stock"] == 199


def test_midnight_checkpoint_preserves_sleep_and_horizon_activity(tmp_path):
    with create(tmp_path) as session:
        session.world.start("prelude", 1, "LEISURE")
        session.world.advance("prelude-clock", 1425)
        client = SequenceClient([proposal("SLEEP")])
        result = asyncio.run(LongRunRunner(session, client).run())
        assert result["state"] == "COMPLETED"
        assert result["stop_reason"] == "SIMULATION_HORIZON_REACHED"
        assert session.world.minute == 1440
        c = session.world.store.commitment(1)
        assert c["activity"] == "SLEEP" and c["status"] == "ACTIVE"
        assert c["remaining_min"] == 345 and c["elapsed_min"] == 15
        checkpoint = session.export_data()["checkpoints"][-1]
        assert checkpoint["minute"] == checkpoint["state"]["minute"] == 1440
        assert next(c for c in checkpoint["state"]["commitments"]
                    if c["activity"] == "SLEEP")["status"] == "ACTIVE"


def test_invalid_json_never_persists_raw_text_or_replaces_intent(tmp_path):
    sentinel = "SENSITIVE_SENTINEL_DO_NOT_PERSIST"
    with create(tmp_path, config=LongRunConfig(sim_days=1, max_consecutive_errors=1)) as session:
        client = SequenceClient([sentinel])
        result = asyncio.run(LongRunRunner(session, client).run())
        assert result["stop_reason"] == "INVALID_MODEL_OUTPUT"
        assert session.world.minute == 0 and not session.world.store.commitment(1)
        assert not session.db.execute("SELECT id FROM commands").fetchall()
        assert session.request("m5:test:000001")["phase"] == "FINALIZED"
    assert sentinel.encode() not in (tmp_path / "test/world.sqlite3").read_bytes()


def test_rejected_work_is_not_changed_into_wait_or_travel(tmp_path):
    with create(tmp_path, config=LongRunConfig(sim_days=1, max_consecutive_errors=1)) as session:
        result = asyncio.run(LongRunRunner(session, SequenceClient([proposal("WORK")])).run())
        assert result["stop_reason"] == "RULE_REJECTED"
        assert session.world.minute == 0
        assert session.world.store.actor(1)["location"] == "home"
        assert [e["kind"] for e in session.world.store.events()] == ["WORLD_CREATED", "ACTION_REJECTED"]


def test_repeated_invalid_proposals_stop_no_progress_without_clock_jump(tmp_path):
    config = LongRunConfig(sim_days=1, max_no_progress=3, max_consecutive_errors=10)
    with create(tmp_path, config=config) as session:
        client = SequenceClient(["invalid"] * 3)
        result = asyncio.run(LongRunRunner(session, client).run())
        assert result["stop_reason"] == "NO_SIMULATION_PROGRESS"
        assert client.call_count == 3 and session.world.minute == 0


def test_micro_step_limit_is_per_activity_and_preserves_progress(tmp_path):
    config = LongRunConfig(sim_days=1, max_micro_steps=2)
    with create(tmp_path, config=config) as session:
        result = asyncio.run(LongRunRunner(session, SequenceClient([proposal("SLEEP")])).run())
        assert result["stop_reason"] == "MICRO_STEP_BUDGET_REACHED"
        assert session.world.minute == 30
        assert session.world.store.commitment(1)["remaining_min"] == 330


def test_context_budget_stops_before_registering_a_request(tmp_path):
    with create(tmp_path, config=LongRunConfig(sim_days=1, max_context_chars=128)) as session:
        client = SequenceClient([])
        result = asyncio.run(LongRunRunner(session, client).run())
        assert result["stop_reason"] == "CONTEXT_BUDGET_EXCEEDED"
        assert result["decisions"] == client.call_count == 0


def test_confirmed_money_corruption_stops_before_client(tmp_path):
    with create(tmp_path) as session:
        actor = session.world.store.actor(1)
        actor["money_cents"] += 1
        session.world.store.put_actor(actor)
        client = SequenceClient([])
        result = asyncio.run(LongRunRunner(session, client).run())
        assert result["stop_reason"] == "INVARIANT_FAILED"
        assert client.call_count == 0


def test_runtime_requires_explicit_matching_client_mode(tmp_path):
    class UnmarkedClient:
        async def complete(self, *args):
            raise AssertionError("must not be called")
    with create(tmp_path) as session, pytest.raises(SessionError, match="CLIENT_MODE_MISMATCH"):
        LongRunRunner(session, UnmarkedClient())


def test_real_budget_is_reserved_before_client_and_survives_reopening(tmp_path):
    config = LongRunConfig(mode="real", sim_days=1, max_decisions=5, max_provider_requests=1)
    auth = {"approved": True, "session_id": "mock", "max_provider_requests": 1,
            "protocol_hash": config.protocol_hash, "execution_commit": "0" * 40,
            "authorization_type": "EXPLICIT_USER_SESSION_AUTHORIZATION", "resume": False,
            "acceptance": {"execution_commit": "0" * 40, "result": "PASS"},
            "request_policy": {"retry": False, "fallback": False}}
    class MockReal(SequenceClient):
        mode = "real"
        async def complete(self, system, user):
            self.call_count += 1
            self.provider_request_count += 1
            return DecisionReply(proposal("SLEEP"), provider_request_count=1)
    with LongRunSession.create(tmp_path, "mock", config, {
            "execution_commit": "0" * 40, "execution_authorization": auth},
            seed_world=remote_fixture) as session:
        client = MockReal([])
        result = asyncio.run(LongRunRunner(session, client).run())
        assert result["provider_requests_reserved"] == client.call_count == 1
        assert result["stop_reason"] == "REQUEST_BUDGET_REACHED"
        assert session.request("m5:mock:000001")["input_tokens"] is None
    with LongRunSession.open(tmp_path / "mock", resume=True) as restored:
        client = MockReal([])
        result = asyncio.run(LongRunRunner(restored, client).run())
        assert client.call_count == 0 and result["provider_requests_reserved"] == 1


def test_wall_timeout_retains_unknown_intent_and_does_not_retry(tmp_path):
    class Slow(SequenceClient):
        async def complete(self, system, user):
            self.call_count += 1
            await asyncio.sleep(1)
            return DecisionReply(proposal("SLEEP"))
    config = LongRunConfig(sim_days=1, max_wall_seconds=0.1, request_timeout_seconds=0.5)
    with create(tmp_path, config=config) as session:
        client = Slow([])
        result = asyncio.run(LongRunRunner(session, client).run())
        assert result["stop_reason"] == "WALL_CLOCK_LIMIT"
        assert session.request("m5:test:000001")["phase"] == "REQUEST_REGISTERED"
        assert session.request("m5:test:000001")["status"] == "UNKNOWN"
        assert client.call_count == 1


def test_wall_budget_is_cumulative_across_reopening(tmp_path):
    config = LongRunConfig(sim_days=1, max_wall_seconds=5)
    with create(tmp_path, config=config) as session:
        saved = session.load()
        saved["wall_seconds"] = 5
        session.save(saved)
    with LongRunSession.open(tmp_path / "test", resume=True) as restored:
        client = SequenceClient([])
        result = asyncio.run(LongRunRunner(restored, client).run())
        assert result["stop_reason"] == "WALL_CLOCK_LIMIT"
        assert client.call_count == 0


@pytest.mark.parametrize("budget", [0, 1])
def test_real_session_without_execution_authorization_fails_before_world_creation(tmp_path, budget):
    config = LongRunConfig(mode="real", max_provider_requests=budget)
    with pytest.raises(SessionError, match="REAL_EXECUTION_NOT_AUTHORIZED"):
        LongRunSession.create(tmp_path, "unauthorized", config, {"execution_commit": "0" * 40})
    assert list(tmp_path.iterdir()) == []


def test_provider_timeout_has_own_reason_and_retains_unknown(tmp_path):
    class Slow(SequenceClient):
        async def complete(self, system, user):
            self.call_count += 1
            await asyncio.sleep(1)
    config = LongRunConfig(sim_days=1, max_wall_seconds=5, request_timeout_seconds=0.01)
    with create(tmp_path, config=config) as session:
        client = Slow([])
        result = asyncio.run(LongRunRunner(session, client).run())
        assert result["stop_reason"] == "PROVIDER_TIMEOUT" and client.call_count == 1
        assert session.request("m5:test:000001")["request_send_status"] == "UNKNOWN"


def test_daily_report_exists_at_midnight_before_run_is_finished(tmp_path):
    with create(tmp_path, config=LongRunConfig(sim_days=2)) as session:
        session.world.start("prelude", 1, "LEISURE")
        session.world.advance("prelude-clock", 1425)
        result = asyncio.run(LongRunRunner(session, SequenceClient([proposal("SLEEP")])).run(max_steps=1))
        assert result["state"] == "PAUSED" and session.world.minute == 1440
        assert session.world.store.commitment(1)["remaining_min"] == 345
        report = json.loads((session.dir / "daily/day001.json").read_text(encoding="utf-8"))
        assert report["day"] == 1
        assert (session.dir / "daily/day001.md").is_file()


def test_returned_wall_seconds_include_finally_charge(tmp_path):
    class IncrementingClock:
        def __init__(self):
            self.value = 0
        def __call__(self):
            self.value += 0.001
            return self.value
    with create(tmp_path) as session:
        result = asyncio.run(LongRunRunner(session, SequenceClient([proposal("SLEEP")]),
                                           clock=IncrementingClock()).run(max_steps=1))
        assert result["wall_seconds"] == session.load()["wall_seconds"]
        assert result["wall_seconds"] > 0
        assert session.load()["wall_last_epoch"] is None
