"""M2 持久断点、控制状态和崩溃回滚；只用本轮新建的 SQLite 世界。"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from social_sim.continuity import ContinuityWorld, ObjectDefinition, initial_actor, validate_world
from social_sim.continuity.benchmark import seed_demo


def seed_remote(world):
    item = ObjectDefinition(
        "game_a", "M2异地合成游戏", "GAME", ("playable", "purchasable"),
        price_cents=3000, duration_min=45, seller="office",
    )
    world.seed([initial_actor(1, 10000)], [(item, 2)])


def purchases(world):
    return [event for event in world.store.events() if event["kind"] == "PURCHASED"]


def test_configuration_is_opt_in_persistent_and_cannot_silently_change(tmp_path):
    path = tmp_path / "enabled.sqlite"
    with ContinuityWorld(path, acquire_enabled=True) as world:
        seed_remote(world)
        assert world.acquire_enabled
        configuration = world.activity_configuration
        assert "M2_ACQUIRE_V1" in str(configuration)
    with ContinuityWorld(path) as world:
        assert world.acquire_enabled and world.activity_configuration == configuration
        assert world.start("acquire", 1, "ACQUIRE", "game_a")["accepted"]
    with pytest.raises(ValueError, match="(?i)acquire|configuration|migration"):
        ContinuityWorld(path, acquire_enabled=False)
    disabled_path = tmp_path / "disabled.sqlite"
    with ContinuityWorld(disabled_path) as world:
        seed_demo(world)
        assert not world.acquire_enabled
    with pytest.raises(ValueError, match="(?i)acquire|configuration|migration"):
        ContinuityWorld(disabled_path, acquire_enabled=True)


@pytest.mark.parametrize("flag", [0, 1, "true", {}, []])
def test_configuration_rejects_non_boolean_opt_in(tmp_path, flag):
    with pytest.raises((ValueError, TypeError)):
        ContinuityWorld(tmp_path / "invalid.sqlite", acquire_enabled=flag)


@pytest.mark.parametrize("boundary", ["before_departure", "mid_travel", "arrived_before_purchase"])
def test_restart_resumes_each_durable_boundary_without_repeating_travel(tmp_path, boundary):
    path = tmp_path / "boundaries.sqlite"
    with ContinuityWorld(path, acquire_enabled=True) as world:
        seed_remote(world)
        assert world.start("acquire", 1, "ACQUIRE", "game_a")["accepted"]
        if boundary == "mid_travel":
            assert world.advance("midway", 7)["accepted"]
        elif boundary == "arrived_before_purchase":
            assert world.advance("arrival", 15)["accepted"]
        before = world.store.snapshot()
        events = world.store.events()
        expected_phase = "BUY" if boundary == "arrived_before_purchase" else "MOVE"
        assert world.store.get_commitment("acquire")["phase"] == expected_phase
        assert world.store.link(1, "game_a")["quantity"] == 0
    with ContinuityWorld(path) as restored:
        assert restored.store.snapshot() == before and restored.store.events() == events
        assert restored.start("acquire", 1, "ACQUIRE", "game_a")["replayed"]
        assert restored.store.snapshot() == before
        if restored.minute < 15:
            assert restored.advance("arrival", 15)["accepted"]
        assert restored.store.get_commitment("acquire")["phase"] == "BUY"
        assert restored.advance("settle", 15)["accepted"]
        assert restored.store.get_commitment("acquire")["status"] == "COMPLETED"
        assert restored.store.get_commitment("acquire")["elapsed_min"] == 15
        assert restored.minute == 15 and restored.store.actor(1)["location"] == "office"
        assert restored.store.actor(1)["money_cents"] == 7000
        assert restored.store.link(1, "game_a")["quantity"] == 1
        assert restored.store.object("game_a")["stock"] == 1
        assert len(purchases(restored)) == 1
        assert sum(event["kind"] == "MOVED" for event in restored.store.events()) == 1
        validate_world(restored)


def test_restart_after_purchase_and_completed_queries_never_purchase_again(tmp_path):
    path = tmp_path / "completed.sqlite"
    with ContinuityWorld(path, acquire_enabled=True) as world:
        seed_remote(world)
        world.start("acquire", 1, "ACQUIRE", "game_a")
        world.advance("arrival", 15)
        world.advance("settle", 15)
        before = world.store.snapshot()
        events = world.store.events()
    for _ in range(2):
        with ContinuityWorld(path) as restored:
            assert restored.store.get_commitment("acquire")["status"] == "COMPLETED"
            assert restored.store.link(1, "game_a")["quantity"] == 1
            assert restored.store.commitment(1) is None
            assert restored.start("acquire", 1, "ACQUIRE", "game_a")["replayed"]
            assert restored.advance("settle", 15)["replayed"]
            assert restored.store.snapshot() == before and restored.store.events() == events
            assert len(purchases(restored)) == 1
            validate_world(restored)


def test_restart_after_failed_purchase_keeps_failure_and_travel(tmp_path):
    path = tmp_path / "failed.sqlite"
    with ContinuityWorld(path, acquire_enabled=True) as world:
        seed_remote(world)
        world.start("acquire", 1, "ACQUIRE", "game_a")
        world.advance("midway", 7)
        world.set_available("off", "game_a", False)
        world.advance("arrival", 15)
        world.advance("settle", 15)
        before = world.store.snapshot()
        events = world.store.events()
    with ContinuityWorld(path) as restored:
        assert restored.store.snapshot() == before and restored.store.events() == events
        commitment = restored.store.get_commitment("acquire")
        assert commitment["status"] == "FAILED"
        assert commitment["failure_reason"] == "OBJECT_UNAVAILABLE"
        assert restored.start("acquire", 1, "ACQUIRE", "game_a")["replayed"]
        assert restored.advance("settle", 15)["replayed"]
        assert restored.store.snapshot() == before and restored.store.events() == events
        assert restored.store.actor(1)["money_cents"] == 10000
        assert restored.store.actor(1)["location"] == "office" and restored.minute == 15
        assert restored.store.link(1, "game_a")["quantity"] == 0
        assert not purchases(restored)
        validate_world(restored)


@pytest.mark.parametrize("phase", ["MOVE", "BUY"])
def test_paused_acquire_survives_restart_then_resumes_original_phase(tmp_path, phase):
    path = tmp_path / "paused.sqlite"
    with ContinuityWorld(path, acquire_enabled=True) as world:
        seed_remote(world)
        world.start("acquire", 1, "ACQUIRE", "game_a")
        if phase == "BUY":
            world.advance("arrival", 15)
        else:
            world.advance("midway", 7)
        assert world.control("pause", 1, "PAUSE")["accepted"]
        assert world.advance("paused-time", world.minute + 5)["accepted"]
        before = world.store.snapshot()
        assert world.store.link(1, "game_a")["quantity"] == 0
    with ContinuityWorld(path) as restored:
        assert restored.store.snapshot() == before
        commitment = restored.store.commitment(1)
        assert commitment["phase"] == phase and commitment["status"] == "PAUSED"
        assert restored.start("other", 1, "PLAY", "game_a")["reason"] == "ACTIVITY_IN_PROGRESS"
        assert not purchases(restored)
        assert restored.control("resume", 1, "RESUME")["accepted"]
        if phase == "MOVE":
            remaining = restored.store.commitment(1)["remaining_min"]
            assert restored.advance("arrival", restored.minute + remaining)["accepted"]
        assert restored.advance("settle", restored.minute)["accepted"]
        assert restored.store.get_commitment("acquire")["status"] == "COMPLETED"
        assert restored.store.get_commitment("acquire")["elapsed_min"] == 15
        assert restored.store.link(1, "game_a")["quantity"] == 1
        assert len(purchases(restored)) == 1
        validate_world(restored)


@pytest.mark.parametrize("phase", ["MOVE", "BUY"])
def test_cancelled_acquire_does_not_buy_after_restart_or_clock_advance(tmp_path, phase):
    path = tmp_path / "cancelled.sqlite"
    with ContinuityWorld(path, acquire_enabled=True) as world:
        seed_remote(world)
        world.start("acquire", 1, "ACQUIRE", "game_a")
        if phase == "BUY":
            world.advance("arrival", 15)
        assert world.control("cancel", 1, "CANCEL")["accepted"]
    with ContinuityWorld(path) as restored:
        assert restored.store.get_commitment("acquire")["status"] == "CANCELLED"
        assert restored.advance("later", 30)["accepted"]
        assert restored.store.link(1, "game_a")["quantity"] == 0
        assert restored.store.object("game_a")["stock"] == 2
        assert restored.store.actor(1)["money_cents"] == 10000
        assert restored.store.actor(1)["location"] == ("office" if phase == "BUY" else "home")
        assert not purchases(restored)
        assert restored.control("resume", 1, "RESUME")["reason"] == "NO_COMMITMENT"
        validate_world(restored)


def test_process_exit_inside_purchase_rolls_back_trade_but_keeps_prior_travel(tmp_path):
    path = tmp_path / "crash.sqlite"
    with ContinuityWorld(path, acquire_enabled=True) as world:
        seed_remote(world)
        world.start("acquire", 1, "ACQUIRE", "game_a")
        world.advance("arrival", 15)
        before = world.store.snapshot()
        events = world.store.events()
    code = """
import os, sys
from social_sim.continuity import ContinuityWorld
world = ContinuityWorld(sys.argv[1])
original = world.store.emit
def crash(command, kind, payload):
    if kind == 'PURCHASED':
        os._exit(23)
    return original(command, kind, payload)
world.store.emit = crash
world.advance('settle', 15)
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run([sys.executable, "-B", "-c", code, str(path)], env=env,
                            capture_output=True, check=False, timeout=10)
    assert result.returncode == 23, result.stderr
    with ContinuityWorld(path) as restored:
        assert restored.store.snapshot() == before and restored.store.events() == events
        commitment = restored.store.get_commitment("acquire")
        assert commitment["phase"] == "BUY" and commitment["status"] == "ACTIVE"
        assert restored.minute == 15 and restored.store.actor(1)["location"] == "office"
        assert restored.store.actor(1)["money_cents"] == 10000
        assert restored.store.link(1, "game_a")["quantity"] == 0
        assert restored.store.object("game_a")["stock"] == 2
        assert restored.store.db.execute("SELECT 1 FROM commands WHERE id='settle'").fetchone() is None
        assert restored.advance("settle", 15)["accepted"]
        assert len(purchases(restored)) == 1
        validate_world(restored)


@pytest.mark.parametrize("field,value", [
    ("phase", "BROKEN"), ("remaining_min", -1), ("destination", "unknown-place"),
    ("target", "invented-game"),
    ("target", " game_a "),
])
def test_invalid_inflight_commitment_fails_closed_and_keeps_evidence(tmp_path, field, value):
    path = tmp_path / "invalid-recovery.sqlite"
    with ContinuityWorld(path, acquire_enabled=True) as world:
        seed_remote(world)
        world.start("acquire", 1, "ACQUIRE", "game_a")
        commitment = world.store.get_commitment("acquire")
        commitment[field] = value
        world.store.put_commitment(commitment)
        before = world.store.snapshot()
        events = world.store.events()
        with pytest.raises(ValueError, match="ACQUIRE"):
            world.advance("broken", 15)
        assert world.store.snapshot() == before and world.store.events() == events
        assert not purchases(world)
    with pytest.raises(ValueError, match="ACQUIRE"):
        ContinuityWorld(path)
