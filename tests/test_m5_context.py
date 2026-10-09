import json
from dataclasses import replace

import pytest

from social_sim.continuity.engine import ContinuityWorld
from social_sim.continuity.m2_acquire import m2_decision_prompt
from social_sim.longrun.config import LongRunConfig
from social_sim.longrun.context import ContextBudgetExceeded, build_context
from social_sim.longrun.policy import seed_world


def finish(world, name, activity="LEISURE", target=None):
    assert world.start(name, 1, activity, target)["accepted"]
    index = 0
    while c := world.store.commitment(1):
        index += 1
        assert world.advance(name + f":{index}", world.minute + c["remaining_min"])["accepted"]


def test_context_extends_frozen_m2_and_preserves_current_facts():
    config = LongRunConfig(goal_mode="GOAL_CONDITIONED", goals=("合法获得游戏并之后使用。",))
    with ContinuityWorld(":memory:", acquire_enabled=True) as world:
        seed_world(world, config)
        old_system, _ = m2_decision_prompt(world)
        system, user, metrics = build_context(world, config)
        assert system.startswith(old_system)
        data = json.loads(user)
        assert data["observation"]["actor"] == world.store.actor(1)
        assert data["m5"]["goals"]["source"] == "EXPLICIT_EXPERIMENT_CONFIGURATION"
        assert data["m5"]["goals"]["declared"] == list(config.goals)
        assert metrics["actual_input_tokens"] is None
        assert metrics["token_upper_bound"] == len(system.encode()) + len(user.encode()) + 32
        assert metrics["provider_wire_tokens_known"] is False


def test_recent_history_is_committed_and_old_history_stays_bounded():
    config = LongRunConfig()
    with ContinuityWorld(":memory:", acquire_enabled=True) as world:
        seed_world(world, config)
        lengths = []
        for i in range(120):
            finish(world, f"leisure:{i:04d}")
            if i in {5, 20, 60, 119}:
                _, user, metrics = build_context(world, config)
                lengths.append(metrics["prompt_chars"])
                data = json.loads(user)["m5"]
                assert len(data["recent_committed_activities"]) == 5
                assert {c["id"] for c in data["recent_committed_activities"]} == {
                    f"leisure:{j:04d}" for j in range(i - 4, i + 1)}
                assert data["older_committed_activity_totals"]["LEISURE"]["COMPLETED"]["activities"] == i - 4
        assert max(lengths) - min(lengths) < 100
        assert max(lengths) < config.max_context_chars


def test_ownership_survives_unavailable_catalog_and_budget_never_truncates():
    config = LongRunConfig()
    with ContinuityWorld(":memory:", acquire_enabled=True) as world:
        seed_world(world, config)
        finish(world, "own", "ACQUIRE", "game_a")
        world.set_available("off", "game_a", False)
        _, user, _ = build_context(world, config)
        assert json.loads(user)["m5"]["all_owned_objects"][0]["quantity"] == 1
        before = world.store.snapshot()
        with pytest.raises((ContextBudgetExceeded, ValueError)):
            build_context(world, replace(config, max_context_chars=128))
        with pytest.raises(ContextBudgetExceeded):
            build_context(world, replace(config, max_context_tokens=128))
        assert world.store.snapshot() == before


def test_opt_out_world_uses_existing_legacy_contract():
    config = LongRunConfig(acquire_enabled=False)
    with ContinuityWorld(":memory:") as world:
        seed_world(world, config)
        _, user, _ = build_context(world, config)
        assert not world.acquire_enabled
        assert all(p["activity"] != "ACQUIRE" for p in json.loads(user).get("startable_options", []))
