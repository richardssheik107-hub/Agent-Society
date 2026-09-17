"""Deterministic, uncalibrated simulation clock and need dynamics."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

from social_sim.decision.models import ActionType
from social_sim.world.state import WorldState


DAY_START = "06:00"
DAY_END = "24:00"
TICK_MINUTES = 15
WORK_START = "09:00"
WORK_END = "17:00"
SLEEP_DURATION_MINUTES = 360
WORK_DURATION_MINUTES = 90
LEISURE_DURATION_MINUTES = 60
ACTIVITY_DURATIONS_MINUTES = {
    ActionType.SLEEP: SLEEP_DURATION_MINUTES,
    ActionType.WORK: WORK_DURATION_MINUTES,
    ActionType.LEISURE: LEISURE_DURATION_MINUTES,
}

# Mechanical baseline only. Research B may calibrate these values.
NEEDS_PARAMETER_STATUS = "UNCALIBRATED_BASELINE"
HUNGER_INCREASE_PER_TICK = 0.01
AWAKE_ENERGY_DECREASE_PER_TICK = 0.01
SLEEP_ENERGY_INCREASE_PER_TICK = 0.04


def _clamp01(value: float) -> float:
    return round(min(1.0, max(0.0, value)), 6)


def advance_daily_tick(
    world: WorldState,
    minutes: int = TICK_MINUTES,
) -> tuple[WorldState, tuple[tuple[int, ActionType], ...]]:
    """Advance the simulation, update needs, and clear completed activities.

    ``minutes`` is a positive multiple of 15. The API is pure and uses no
    wall-clock time or LLM. The caller owns EventLog IDs and appends one
    ``*_COMPLETED`` DomainEvent for each returned (actor_id, action) pair.
    """

    if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes <= 0:
        raise ValueError("minutes must be a positive integer")
    if minutes % TICK_MINUTES:
        raise ValueError("minutes must be a multiple of TICK_MINUTES")
    new_time = world.time + timedelta(minutes=minutes)
    completed: list[tuple[int, ActionType]] = []
    people = {}
    ticks = minutes // TICK_MINUTES
    for actor_id, person in world.people.items():
        # Iterate internally in 15-minute increments so a long advance has the
        # same dynamics as repeated normal ticks, including an activity end.
        hunger = person.hunger
        energy = person.energy
        activity = person.activity
        activity_end_time = person.activity_end_time
        for tick_index in range(ticks):
            tick_end = world.time + timedelta(minutes=TICK_MINUTES * (tick_index + 1))
            hunger = _clamp01(hunger + HUNGER_INCREASE_PER_TICK)
            if energy is not None:
                if activity == ActionType.SLEEP.value:
                    energy = _clamp01(energy + SLEEP_ENERGY_INCREASE_PER_TICK)
                else:
                    energy = _clamp01(energy - AWAKE_ENERGY_DECREASE_PER_TICK)
            if activity_end_time is not None and tick_end >= datetime.fromisoformat(activity_end_time):
                completed.append((actor_id, ActionType(activity)))
                activity = None
                activity_end_time = None
        people[actor_id] = replace(
            person,
            hunger=hunger,
            energy=energy,
            activity=activity,
            activity_end_time=activity_end_time,
        )
    return (
        WorldState(
            time=new_time, people=people, locations=world.locations,
            venues=world.venues,
        ),
        tuple(completed),
    )
