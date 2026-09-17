"""A2.0 profile isolation, deterministic rules, segments, and metrics."""

from __future__ import annotations

from datetime import timedelta
import json

import pytest

from social_sim.actions import proposal_to_intent
from social_sim.daily.calibrated import aggregate, interleaved_schedule, segment_world
from social_sim.daily.calibrated import CalibratedSegmentBenchmark, episode_metrics
from social_sim.daily.profiles import load_experiment_profiles, quantize_duration_to_tick
from social_sim.daily.runner import neutral_day_initial_world
from social_sim.daily.time import advance_daily_tick
from social_sim.daily.validation import validate_daily_trajectory
from social_sim.decision import ActionType, DecisionProposal
from social_sim.decision.parser import DecisionParser
from social_sim.decision.client import FakeDecisionClient
from social_sim.evaluation.models import world_snapshot
from social_sim.execution import ActionExecutor
from social_sim.rules import RuleEngine


@pytest.fixture
def profiles():
    return load_experiment_profiles()


@pytest.mark.parametrize(("raw", "expected"), [(80, 75), (25, 30), (30, 30), (270, 270), (22, 15), (23, 30)])
def test_half_up_quantization(raw, expected):
    assert quantize_duration_to_tick(raw) == expected


def test_profiles_frozen_and_action_gated(profiles):
    g0, g1, g2 = profiles
    assert len({p.profile_hash for p in profiles}) == 3
    assert g0.duration_overrides == {"SLEEP": 360, "WORK": 90, "LEISURE": 60}
    assert g1.duration_overrides == {"SLEEP": 360, "WORK": 270, "LEISURE": 75}
    assert g2.duration_overrides["PERSONAL_CARE"] == g2.duration_overrides["CHORES"] == 30
    assert g0.available_actions == g1.available_actions
    assert ActionType.PERSONAL_CARE not in g0.available_actions
    assert ActionType.CHORES not in g1.available_actions
    assert g2.available_actions[-2:] == (ActionType.PERSONAL_CARE, ActionType.CHORES)


@pytest.mark.parametrize("action", [ActionType.PERSONAL_CARE, ActionType.CHORES])
def test_experimental_actions_no_side_effects_and_home_only(profiles, action):
    g0, g1, g2 = profiles
    intent = proposal_to_intent(1, DecisionProposal(action))
    world = neutral_day_initial_world()
    default = ActionExecutor().execute(world, intent, event_id="1")
    assert not default.allowed and default.new_world == world
    for profile in (g0, g1):
        engine = RuleEngine(duration_overrides={ActionType(k): v for k, v in profile.duration_overrides.items()})
        assert not ActionExecutor(engine).execute(world, intent, event_id="1").allowed
    engine = RuleEngine(
        duration_overrides={ActionType(k): v for k, v in g2.duration_overrides.items()},
        experimental_actions_enabled=True,
    )
    outcome = ActionExecutor(engine).execute(world, intent, event_id="1")
    assert outcome.allowed and outcome.events[0].event_type.value == action.value + "_STARTED"
    before = world.get_person(1)
    after = outcome.new_world.get_person(1)
    assert after.activity == action.value
    assert after.activity_end_time == (world.time + timedelta(minutes=30)).isoformat()
    assert (after.location, after.money, after.hunger, after.energy, after.inventory) == (
        before.location, before.money, before.hunger, before.energy, before.inventory,
    )
    midpoint, completions = advance_daily_tick(outcome.new_world)
    assert not completions and midpoint.get_person(1).activity == action.value
    finished, completions = advance_daily_tick(midpoint)
    assert completions == ((1, action),) and finished.get_person(1).activity is None
    assert finished.get_person(1).money == before.money
    assert finished.get_person(1).inventory == before.inventory
    for location in ("office", "restaurant"):
        rejected = ActionExecutor(engine).execute(segment_world("WORK" if location == "office" else "MIDDAY").__class__(
            time=world.time, people={1: before.__class__(1, location, 100.0, 0.3, energy=0.8)},
            locations=world.locations, venues=world.venues,
        ), intent, event_id="2")
        assert not rejected.allowed and rejected.reason_code == "NOT_AT_ACTIVITY_LOCATION"


def test_parser_profile_validation(profiles):
    parser = DecisionParser()
    for action in (ActionType.PERSONAL_CARE, ActionType.CHORES):
        raw = '{"action":"' + action.value + '","target":null}'
        assert parser.evaluate(raw, available_actions=profiles[2].available_actions).strict_valid
        result = parser.evaluate(raw, available_actions=profiles[0].available_actions)
        assert result.failure_type == "ACTION_NOT_AVAILABLE_FOR_PROFILE"


def test_work_duration_injected_not_default(profiles):
    world = segment_world("WORK")
    intent = proposal_to_intent(1, DecisionProposal(ActionType.WORK))
    for profile, expected in zip(profiles, (90, 270, 270)):
        rules = RuleEngine(duration_overrides={ActionType(k): v for k, v in profile.duration_overrides.items()})
        outcome = ActionExecutor(rules).execute(world, intent, event_id="work")
        assert outcome.allowed
        assert outcome.new_world.get_person(1).activity_end_time == (
            world.time + timedelta(minutes=expected)
        ).isoformat()
    assert ActionExecutor().execute(world, intent, event_id="default").new_world.get_person(1).activity_end_time == (
        world.time + timedelta(minutes=90)
    ).isoformat()


def test_segment_initial_states_and_interleaving(profiles):
    schedule = interleaved_schedule(profiles)
    assert len(schedule) == 24 and len({tuple((r["repeat"], r["segment"], r["profile"])) for r in schedule}) == 24
    assert [r["profile"] for r in schedule[:3]] == [p.name for p in profiles]
    for name in ("MORNING", "WORK", "MIDDAY", "EVENING"):
        assert world_snapshot(segment_world(name)) == world_snapshot(segment_world(name))
        person = segment_world(name).get_person(1)
        assert person.activity is None and person.inventory == {}


def test_mechanical_counterfactual_from_profiles(profiles):
    blocks = {"SLEEP": 360, "WORK": 480, "LEISURE": 240}
    completions = [sum(minutes // profile.duration_overrides[action] for action, minutes in blocks.items())
                   for profile in profiles[:2]]
    assert completions == [10, 5]
    assert [value + 1 for value in completions] == [11, 6]


def test_empty_aggregate_excludes_partial():
    result = aggregate([])
    assert result["complete_segments"] == 0 and result["avg_decision_count"] is None


@pytest.mark.asyncio
async def test_segment_context_only_action_list_changes(profiles, tmp_path):
    contexts = []
    for index, profile in enumerate(profiles, 1):
        result = await CalibratedSegmentBenchmark(
            FakeDecisionClient('{"action":"LEISURE","target":null}'), tmp_path,
        ).run(index, "MORNING", profile)
        assert result.day_completed and len(result.ticks) == 12
        assert validate_daily_trajectory(result)
        assert result.ticks[0].world_before == world_snapshot(segment_world("MORNING"))
        contexts.append(json.loads(result.trajectory.steps[0].context))
        metrics = episode_metrics(result, segment="MORNING", repeat=1)
        assert metrics["behavior_metrics_valid"] and metrics["observed_minutes"] == 180
        assert result.trajectory.steps[0].prompt_hash is not None
    assert contexts[0] == contexts[1]
    assert {key: value for key, value in contexts[2].items() if key != "a"} == {
        key: value for key, value in contexts[1].items() if key != "a"
    }
