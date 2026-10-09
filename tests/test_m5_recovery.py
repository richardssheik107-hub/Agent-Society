"""Recover each durable boundary; read-only export and locks preserve evidence."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from social_sim.longrun.config import LongRunConfig
from social_sim.longrun.runner import LongRunRunner
from social_sim.longrun.session import LongRunSession, SessionError
from test_m5_runtime import SequenceClient, create, proposal


class InjectedCrash(BaseException):
    pass


def interrupt_at(stage):
    def fault(actual, data):
        if actual == stage:
            raise InjectedCrash(stage)
    return fault


@pytest.mark.parametrize("stage", ["REQUEST_REGISTERED", "RESPONSE_OBSERVED"])
def test_unknown_request_is_never_resent_even_if_response_metadata_exists(tmp_path, stage):
    with create(tmp_path) as session:
        client = SequenceClient([proposal("SLEEP")])
        with pytest.raises(InjectedCrash):
            asyncio.run(LongRunRunner(session, client, fault_hook=interrupt_at(stage)).run())
        assert session.request("m5:test:000001")["status"] == "UNKNOWN"
        before = session.world.store.snapshot()
    with LongRunSession.open(tmp_path / "test", resume=True) as restored:
        client = SequenceClient([])
        result = asyncio.run(LongRunRunner(restored, client).run())
        assert result["state"] == "RECOVERY_REQUIRED"
        assert result["stop_reason"] == "UNCERTAIN_REQUEST_STATE"
        assert client.call_count == 0 and result["decisions"] == 1
        assert restored.world.store.snapshot() == before


@pytest.mark.parametrize("stage", ["PROPOSAL_PARSED", "WORLD_EFFECT_COMMITTED",
                                   "WORLD_COMMITTED", "FINALIZED"])
def test_parsed_or_committed_intent_recovers_without_another_client_call(tmp_path, stage):
    config = LongRunConfig(sim_days=1, max_decisions=1)
    with create(tmp_path, config=config) as session:
        with pytest.raises(InjectedCrash):
            asyncio.run(LongRunRunner(session, SequenceClient([proposal("ACQUIRE", "game_a")]),
                                     fault_hook=interrupt_at(stage)).run())
    with LongRunSession.open(tmp_path / "test", resume=True) as restored:
        client = SequenceClient([])
        result = asyncio.run(LongRunRunner(restored, client).run())
        assert result["stop_reason"] == "REQUEST_BUDGET_REACHED"
        assert client.call_count == 0
        assert restored.world.minute == 15
        assert restored.world.store.actor(1)["money_cents"] == 7000
        assert restored.world.store.link(1, "game_a")["quantity"] == 1
        assert restored.world.store.object("game_a")["stock"] == 1
        assert sum(e["kind"] == "PURCHASED" for e in restored.world.store.events()) == 1
        assert restored.request("m5:test:000001")["phase"] == "FINALIZED"


@pytest.mark.parametrize("stage", ["MICRO_STEP_REGISTERED", "MICRO_WORLD_COMMITTED",
                                   "MICRO_STEP_COMMITTED"])
def test_watch_restart_continues_original_offset_and_never_redecides(tmp_path, stage):
    config = LongRunConfig(sim_days=1, max_decisions=1)
    with create(tmp_path, config=config) as session:
        with pytest.raises(InjectedCrash):
            asyncio.run(LongRunRunner(session, SequenceClient([proposal("WATCH", "series_a")]),
                                     fault_hook=interrupt_at(stage)).run())
    with LongRunSession.open(tmp_path / "test", resume=True) as restored:
        client = SequenceClient([])
        result = asyncio.run(LongRunRunner(restored, client).run())
        assert client.call_count == 0 and result["decisions"] == 1
        link = restored.world.store.link(1, "series_a")
        assert restored.world.minute == 45
        assert link["offsets"] == {"1": 45}
        assert link["watched"] == [1] and link["view_counts"] == {"1": 1}
        assert result["micro_steps"] == 3


def test_arrival_before_purchase_is_durable_and_purchase_never_repeats(tmp_path):
    with create(tmp_path, config=LongRunConfig(sim_days=1, max_decisions=1)) as session:
        result = asyncio.run(LongRunRunner(session, SequenceClient([proposal("ACQUIRE", "game_a")])).run(max_steps=1))
        assert result["state"] == "PAUSED" and session.world.minute == 15
        assert session.world.store.commitment(1)["phase"] == "BUY"
        assert session.world.store.link(1, "game_a")["quantity"] == 0
    for _ in range(2):
        with LongRunSession.open(tmp_path / "test", resume=True) as restored:
            client = SequenceClient([])
            asyncio.run(LongRunRunner(restored, client).run())
            assert client.call_count == 0
            assert restored.world.store.actor(1)["money_cents"] == 7000
            assert sum(e["kind"] == "PURCHASED" for e in restored.world.store.events()) == 1


def test_stock_competition_after_arrival_fails_without_refunding_time(tmp_path):
    with create(tmp_path, config=LongRunConfig(sim_days=1, max_decisions=1)) as session:
        asyncio.run(LongRunRunner(session, SequenceClient([proposal("ACQUIRE", "game_a")])).run(max_steps=1))
        session.world.set_available("competition", "game_a", False)
    with LongRunSession.open(tmp_path / "test", resume=True) as restored:
        result = asyncio.run(LongRunRunner(restored, SequenceClient([])).run())
        assert result["stop_reason"] == "COMMITMENT_FAILED"
        assert restored.world.minute == 15
        assert restored.world.store.actor(1)["money_cents"] == 10000
        assert restored.world.store.link(1, "game_a")["quantity"] == 0


def test_completed_export_is_strictly_readonly_and_does_not_construct_world(tmp_path, monkeypatch):
    with create(tmp_path, config=LongRunConfig(sim_days=1, max_decisions=1)) as session:
        asyncio.run(LongRunRunner(session, SequenceClient([proposal("SLEEP")])).run())
    path = tmp_path / "test/world.sqlite3"
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    import social_sim.longrun.session as module
    monkeypatch.setattr(module, "ContinuityWorld", lambda *a, **k: pytest.fail("writable world opened"))
    exported = LongRunSession.export_only(tmp_path / "test")
    assert exported["world"]["minute"] == 360
    assert exported["requests"][0]["input_tokens"] is None
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    assert exported["session"]["resume_count"] == 0


def test_live_export_can_read_locked_session_but_second_writer_cannot(tmp_path):
    with create(tmp_path) as session:
        assert LongRunSession.export_only(session.dir)["world"]["minute"] == 0
        with pytest.raises(SessionError, match="SESSION_ALREADY_RUNNING"):
            LongRunSession.open(session.dir, resume=True)
    assert (tmp_path / "test/.session.lock").exists()
    with LongRunSession.open(tmp_path / "test", resume=True):
        pass


def test_lock_blocks_another_process_and_is_released_without_deleting_file(tmp_path):
    with create(tmp_path) as session:
        code = """
import sys
from social_sim.longrun.session import LongRunSession,SessionError
try:
    LongRunSession.open(sys.argv[1],resume=True)
except SessionError as e:
    print(str(e));sys.exit(23)
"""
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        outcome = subprocess.run([sys.executable, "-c", code, str(session.dir)], env=env,
                                 capture_output=True, text=True, timeout=10, check=False)
        assert outcome.returncode == 23 and "SESSION_ALREADY_RUNNING" in outcome.stdout
    assert (tmp_path / "test/.session.lock").is_file()


def test_unique_identity_and_explicit_resume_are_required(tmp_path):
    with create(tmp_path):
        pass
    with pytest.raises(FileExistsError):
        create(tmp_path)
    with pytest.raises(SessionError, match="EXPLICIT_RESUME_REQUIRED"):
        LongRunSession.open(tmp_path / "test")


@pytest.mark.parametrize("identity", ["../escape", "a/b", ".", "..", "", "x" * 65])
def test_invalid_session_identity_cannot_create_paths(tmp_path, identity):
    with pytest.raises(ValueError, match="INVALID_SESSION_ID"):
        create(tmp_path, name=identity)
    assert list(tmp_path.iterdir()) == []


def test_same_request_id_can_never_be_registered_or_world_committed_twice(tmp_path):
    with create(tmp_path, config=LongRunConfig(sim_days=1, max_decisions=1)) as session:
        asyncio.run(LongRunRunner(session, SequenceClient([proposal("ACQUIRE", "game_a")])).run())
        before = session.world.store.snapshot()
        events = session.world.store.events()
        record = session.request("m5:test:000001")
        assert session.world.start("m5:test:000001", 1, "ACQUIRE", "game_a",
                                   expected_version=record["expected_version"])["replayed"]
        with pytest.raises(SessionError, match="REQUEST_ALREADY_FINALIZED"):
            session.record_request("m5:test:000001", "FINALIZED", {"status": "DECISION_ACCEPTED"})
        assert session.world.store.snapshot() == before and session.world.store.events() == events


def test_cancel_during_request_keeps_unknown_and_never_replays(tmp_path):
    class Cancelled(SequenceClient):
        async def complete(self, system, user):
            self.call_count += 1
            raise asyncio.CancelledError()
    with create(tmp_path) as session:
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(LongRunRunner(session, Cancelled([])).run())
        assert session.request("m5:test:000001")["status"] == "UNKNOWN"
        assert session.load()["stop_reason"] == "USER_INTERRUPTED"
    with LongRunSession.open(tmp_path / "test", resume=True) as restored:
        client = SequenceClient([])
        result = asyncio.run(LongRunRunner(restored, client).run())
        assert result["stop_reason"] == "UNCERTAIN_REQUEST_STATE" and client.call_count == 0


def test_no_response_body_or_secret_keys_can_enter_receipts(tmp_path):
    with create(tmp_path) as session:
        record = session.register_request(0, {})
        with pytest.raises(ValueError, match="UNSAFE_AUDIT_FIELD"):
            session.record_request(record["request_id"], "RESPONSE_OBSERVED",
                                   {"nested": {"raw_text": "SECRET_SENTINEL"}})
        assert "SECRET_SENTINEL" not in json.dumps(session.export_data())


@pytest.mark.parametrize("stage,activity,target", [
    ("WORLD_EFFECT_COMMITTED", "ACQUIRE", "game_a"),
    ("MICRO_WORLD_COMMITTED", "WATCH", "series_a"),
])
def test_process_exit_after_world_commit_recovers_ledger_without_duplicate_effects(tmp_path, stage, activity, target):
    with create(tmp_path, config=LongRunConfig(sim_days=1, max_decisions=1)):
        pass
    code = """
import asyncio,os,sys
from social_sim.longrun.session import LongRunSession
from social_sim.longrun.runner import LongRunRunner
from test_m5_runtime import SequenceClient,proposal
def fault(stage,data):
    if stage==sys.argv[2]:os._exit(23)
with LongRunSession.open(sys.argv[1],resume=True) as session:
    asyncio.run(LongRunRunner(session,SequenceClient([proposal(sys.argv[3],sys.argv[4])]),fault_hook=fault).run())
"""
    env = os.environ.copy()
    root = Path(__file__).resolve().parents[1]
    env["PYTHONPATH"] = os.pathsep.join([str(root / "src"), str(root / "tests")])
    outcome = subprocess.run([sys.executable, "-c", code, str(tmp_path / "test"), stage, activity, target],
                             env=env, capture_output=True, text=True, timeout=10, check=False)
    assert outcome.returncode == 23, outcome.stderr
    with LongRunSession.open(tmp_path / "test", resume=True) as restored:
        client = SequenceClient([])
        result = asyncio.run(LongRunRunner(restored, client).run())
        assert client.call_count == 0 and result["decisions"] == 1
        assert restored.request("m5:test:000001")["phase"] == "FINALIZED"
        link = restored.world.store.link(1, target)
        if activity == "ACQUIRE":
            assert link["quantity"] == 1 and restored.world.store.actor(1)["money_cents"] == 7000
            assert sum(e["kind"] == "PURCHASED" for e in restored.world.store.events()) == 1
        else:
            assert link["offsets"] == {"1": 45} and link["view_counts"] == {"1": 1}
            assert result["micro_steps"] == 3


def test_cross_day_sleep_restarts_from_midnight_checkpoint_without_redecision(tmp_path):
    with create(tmp_path, config=LongRunConfig(sim_days=2, max_decisions=1)) as session:
        session.world.start("prelude", 1, "LEISURE")
        session.world.advance("prelude-clock", 1425)
        with pytest.raises(InjectedCrash):
            asyncio.run(LongRunRunner(session, SequenceClient([proposal("SLEEP")]),
                                     fault_hook=interrupt_at("CHECKPOINTED")).run())
        assert session.world.minute == 1440
        assert session.world.store.commitment(1)["remaining_min"] == 345
    with LongRunSession.open(tmp_path / "test", resume=True) as restored:
        client = SequenceClient([])
        result = asyncio.run(LongRunRunner(restored, client).run())
        assert result["stop_reason"] == "REQUEST_BUDGET_REACHED"
        assert client.call_count == 0 and restored.world.minute == 1785
        assert restored.world.store.get_commitment("m5:test:000001")["elapsed_min"] == 360
        checkpoint = restored.export_data()["checkpoints"][-1]
        assert checkpoint["minute"] == checkpoint["state"]["minute"] == 1440
        assert checkpoint["state"]["commitments"][0]["remaining_min"] == 345


def test_report_missing_after_checkpoint_hook_is_restored_before_any_world_step(tmp_path):
    config = LongRunConfig(sim_days=2, max_decisions=1)
    with create(tmp_path, config=config) as session:
        session.world.start("prelude", 1, "LEISURE")
        session.world.advance("prelude-clock", 1425)
        with pytest.raises(InjectedCrash):
            asyncio.run(LongRunRunner(session, SequenceClient([proposal("SLEEP")]),
                                     fault_hook=interrupt_at("CHECKPOINTED")).run())
        before = session.world.store.snapshot()
        events = session.world.store.events()
        assert not (session.dir / "daily/day001.json").exists()
    with LongRunSession.open(tmp_path / "test", resume=True) as restored:
        def check_restored(stage, data):
            if stage == "DAILY_REPORT_WRITTEN":
                assert restored.world.store.snapshot() == before
                assert restored.world.store.events() == events
                raise InjectedCrash("report restored before effects")
        client = SequenceClient([])
        with pytest.raises(InjectedCrash):
            asyncio.run(LongRunRunner(restored, client, fault_hook=check_restored).run())
        assert client.call_count == 0
        report = json.loads((restored.dir / "daily/day001.json").read_text(encoding="utf-8"))
        assert report["day"] == 1 and (restored.dir / "daily/day001.md").is_file()
        assert restored.world.store.snapshot() == before and restored.world.store.events() == events
