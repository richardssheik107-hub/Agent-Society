import asyncio

from social_sim.continuity.engine import ContinuityWorld
from social_sim.continuity.m2_acquire import parse_m2_proposal
from social_sim.longrun.config import LongRunConfig
from social_sim.longrun.evaluation import check_invariants
from social_sim.longrun.policy import FakeLongRunPolicy, seed_world


def test_policy_changes_with_current_needs_and_preserves_fixture_on_resume(tmp_path):
    config = LongRunConfig()
    path = tmp_path / "world.db"
    with ContinuityWorld(path, acquire_enabled=True) as world:
        seed_world(world, config)
        policy = FakeLongRunPolicy(world, config)
        assert policy.choose() == {"activity": "MEAL", "target": "food_meal"}
        world.start("meal", 1, "MEAL", "food_meal")
        world.advance("move", 15)
        world.advance("eat", 45)
        next_proposal = policy.choose()
        assert next_proposal == {"activity": "ACQUIRE", "target": "game_a"}
        before = world.store.snapshot()
    with ContinuityWorld(path) as world:
        seed_world(world, config)
        assert world.store.snapshot() == before
        assert FakeLongRunPolicy(world, config).choose() == next_proposal


def test_synthetic_state_based_policy_reaches_seven_days_and_real_coverage():
    async def execute():
        config = LongRunConfig()
        with ContinuityWorld(":memory:", acquire_enabled=True) as world:
            seed_world(world, config)
            client = FakeLongRunPolicy(world, config)
            decisions = 0
            while world.minute < 10080:
                c = world.store.commitment(1)
                if c:
                    result = world.advance(f"tick:{world.minute}:{decisions}",
                                           min(10080, world.minute + c["remaining_min"]))
                    assert result["accepted"]
                else:
                    decisions += 1
                    proposal = parse_m2_proposal((await client.complete("", "")).raw_text)
                    result = world.start(f"decision:{decisions}", 1, proposal["activity"], proposal["target"])
                    assert result["accepted"]
                    assert result["commitment_status"] != "FAILED"
                assert decisions < 1000
            assert world.minute == 10080
            assert client.provider_request_count == 0
            assert check_invariants(world)["L1"] == "PASS"
            state, events = world.store.snapshot(), world.store.events()
            completed = {c["activity"] for c in state["commitments"] if c["status"] == "COMPLETED"}
            assert {"MEAL", "SLEEP", "WORK", "TRAVEL", "LEISURE", "ACQUIRE", "PLAY", "WATCH"} <= completed
            assert world.store.link(1, "game_a")["quantity"] == 1
            assert world.store.link(1, "game_a")["play_minutes"] >= 45
            assert world.store.link(1, "series_a")["watched"]
            bought = next(e for e in events if e["kind"] == "PURCHASED" and e["payload"]["object_id"] == "game_a")
            played = next(c for c in state["commitments"] if c["activity"] == "PLAY")
            assert played["started_minute"] >= bought["minute"]
            assert any(c["activity"] == "SLEEP" and c["started_minute"] // 1440 !=
                       (c["started_minute"] + c["elapsed_min"]) // 1440 for c in state["commitments"])
    asyncio.run(execute())
