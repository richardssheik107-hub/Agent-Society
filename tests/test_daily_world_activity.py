"""The daily substrate is deterministic and preserves the lunch baseline."""

from datetime import datetime, timedelta, timezone

import pytest

from social_sim.actions.models import ActionIntent
from social_sim.daily.time import (
    AWAKE_ENERGY_DECREASE_PER_TICK,
    HUNGER_INCREASE_PER_TICK,
    LEISURE_DURATION_MINUTES,
    NEEDS_PARAMETER_STATUS,
    SLEEP_DURATION_MINUTES,
    SLEEP_ENERGY_INCREASE_PER_TICK,
    TICK_MINUTES,
    WORK_DURATION_MINUTES,
    advance_daily_tick,
)
from social_sim.decision.models import ActionType
from social_sim.effects.models import StartActivityEffect
from social_sim.events.models import DomainEvent, EventType
from social_sim.execution.executor import ActionExecutor
from social_sim.reducer.state_reducer import StateConflictError, StateReducer
from social_sim.rules.base import ReasonCode
from social_sim.rules.engine import RuleEngine
from social_sim.world.observation import ObservationBuilder
from social_sim.world.state import PersonWorldState, WorldState


def world_at(hour: int, minute: int = 0, location: str = "home", *, energy: float = 0.8) -> WorldState:
    return WorldState(
        time=datetime(2026, 1, 1, hour, minute, tzinfo=timezone.utc),
        people={1: PersonWorldState(1, location, 100.0, 0.3, energy=energy)},
        locations=("home", "office", "restaurant", "park"),
    )


def execute(world: WorldState, action: ActionType):
    return ActionExecutor().execute(
        world, ActionIntent(actor_id=1, action=action), event_id="event-000001"
    )


def test_legacy_world_keeps_old_observation_shape() -> None:
    legacy = WorldState(
        time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        people={1: PersonWorldState(1, "home", 100.0, 0.3)},
    )
    assert legacy.locations == ("home", "park", "restaurant")
    assert legacy.get_person(1).energy is None
    assert set(ObservationBuilder(legacy).build(1).to_dict()) == {
        "agent_id", "time", "location", "money", "hunger"
    }


def test_daily_world_observation_exposes_needs_and_activity() -> None:
    world = world_at(9)
    obs = ObservationBuilder(world).build(1)
    assert obs.energy == 0.8
    assert obs.activity is None
    assert obs.to_dict()["energy"] == 0.8
    assert obs.to_dict()["activity"] is None
    assert obs.to_dict()["activity_end_time"] is None


@pytest.mark.parametrize("energy", [-0.01, 1.01, float("nan"), True])
def test_energy_range_validation(energy) -> None:
    with pytest.raises(ValueError, match="energy"):
        PersonWorldState(1, "home", 100.0, 0.3, energy=energy)


@pytest.mark.parametrize(
    ("action", "location", "hour", "allowed", "reason"),
    [
        (ActionType.WORK, "home", 9, False, ReasonCode.NOT_AT_ACTIVITY_LOCATION),
        (ActionType.WORK, "office", 9, True, ReasonCode.ACCEPTED),
        (ActionType.WORK, "office", 17, False, ReasonCode.OUTSIDE_WORK_WINDOW),
        (ActionType.SLEEP, "home", 9, True, ReasonCode.ACCEPTED),
        (ActionType.SLEEP, "office", 9, False, ReasonCode.NOT_AT_ACTIVITY_LOCATION),
        (ActionType.LEISURE, "home", 9, True, ReasonCode.ACCEPTED),
        (ActionType.LEISURE, "park", 9, True, ReasonCode.ACCEPTED),
        (ActionType.LEISURE, "office", 9, False, ReasonCode.NOT_AT_ACTIVITY_LOCATION),
    ],
)
def test_activity_rules(action, location, hour, allowed, reason) -> None:
    result = RuleEngine().evaluate(world_at(hour, location=location), ActionIntent(1, action))
    assert result.allowed is allowed
    assert result.reason_code is reason
    assert len(result.effects) == int(allowed)


@pytest.mark.parametrize(
    ("action", "duration", "event_type"),
    [
        (ActionType.SLEEP, SLEEP_DURATION_MINUTES, EventType.SLEEP_STARTED),
        (ActionType.WORK, WORK_DURATION_MINUTES, EventType.WORK_STARTED),
        (ActionType.LEISURE, LEISURE_DURATION_MINUTES, EventType.LEISURE_STARTED),
    ],
)
def test_activity_goes_rule_effect_reducer_then_completes(action, duration, event_type) -> None:
    location = "office" if action is ActionType.WORK else "home"
    before = world_at(9, location=location)
    outcome = execute(before, action)
    assert outcome.allowed
    assert outcome.events[0].event_type is event_type
    assert isinstance(outcome.effects[0], StartActivityEffect)
    assert before.get_person(1).activity is None
    started = outcome.new_world.get_person(1)
    assert started.activity == action.value
    assert started.activity_end_time == (before.time + timedelta(minutes=duration)).isoformat()
    finished_world, completions = advance_daily_tick(outcome.new_world, duration)
    assert finished_world.time == before.time + timedelta(minutes=duration)
    assert finished_world.get_person(1).activity is None
    assert finished_world.get_person(1).activity_end_time is None
    assert completions == ((1, action),)
    completion_event = DomainEvent(
        event_id="event-000002", actor_id=1,
        event_type=EventType(f"{action.value}_COMPLETED"),
        action=action, target=None, success=True, reason_code="ACCEPTED",
    )
    assert completion_event.compact() == f"{action.value}_COMPLETED"


def test_activity_rejects_new_activity_while_one_is_active() -> None:
    active = execute(world_at(9), ActionType.LEISURE).new_world
    result = execute(active, ActionType.SLEEP)
    assert result.reason_code == ReasonCode.ACTIVITY_IN_PROGRESS.value
    assert result.new_world is active


def test_activity_effect_rechecks_world_snapshot() -> None:
    before = world_at(9, location="office")
    effect = RuleEngine().evaluate(before, ActionIntent(1, ActionType.WORK)).effects[0]
    changed = WorldState(
        time=before.time + timedelta(minutes=15), people=before.people,
        locations=before.locations,
    )
    with pytest.raises(StateConflictError, match="activity precondition"):
        StateReducer().apply(changed, (effect,))


def test_tick_needs_deterministic_and_clamped() -> None:
    before = world_at(9)
    after, completions = advance_daily_tick(before)
    assert completions == ()
    assert after.time == before.time + timedelta(minutes=TICK_MINUTES)
    assert after.get_person(1).hunger == round(0.3 + HUNGER_INCREASE_PER_TICK, 6)
    assert after.get_person(1).energy == round(0.8 - AWAKE_ENERGY_DECREASE_PER_TICK, 6)
    assert before.get_person(1).hunger == 0.3
    assert NEEDS_PARAMETER_STATUS == "UNCALIBRATED_BASELINE"
    saturated = WorldState(
        time=before.time,
        people={1: PersonWorldState(1, "home", 100, 1.0, energy=0.0)},
    )
    clamped, _ = advance_daily_tick(saturated)
    assert clamped.get_person(1).hunger == 1.0
    assert clamped.get_person(1).energy == 0.0


def test_sleep_restores_energy_and_hunger_still_rises() -> None:
    before = world_at(9, energy=0.2)
    sleeping = execute(before, ActionType.SLEEP).new_world
    next_world, completed = advance_daily_tick(sleeping)
    assert completed == ()
    assert next_world.get_person(1).energy == round(0.2 + SLEEP_ENERGY_INCREASE_PER_TICK, 6)
    assert next_world.get_person(1).hunger == round(0.3 + HUNGER_INCREASE_PER_TICK, 6)


def test_multiple_ticks_match_single_large_advance() -> None:
    before = execute(world_at(9), ActionType.LEISURE).new_world
    long_world, long_completed = advance_daily_tick(before, 75)
    short_world = before
    short_completed = ()
    for _ in range(5):
        short_world, completed = advance_daily_tick(short_world)
        short_completed += completed
    assert long_world == short_world
    assert long_completed == short_completed == ((1, ActionType.LEISURE),)


@pytest.mark.parametrize("minutes", [0, -15, 7, 16, True])
def test_invalid_tick_length_rejected(minutes) -> None:
    with pytest.raises(ValueError, match="minutes"):
        advance_daily_tick(world_at(9), minutes)
