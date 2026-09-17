"""Decision-call spacing diagnostics for a simulated neutral day.

This observer never invokes a model or changes world state. A call is recorded
immediately before the provider attempt, so a timeout is still a decision
attempt and cannot silently disappear from frequency diagnostics.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from social_sim.world import WorldState

from .trigger import TriggerReason


@dataclass(frozen=True)
class DecisionCallAudit:
    simulation_time: str
    trigger_reason: str
    same_state_as_previous: bool
    in_decision_burst: bool


def _minute_index(value: datetime | str) -> tuple[int, str]:
    if isinstance(value, str):
        try:
            time = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("simulation_time must be ISO-8601") from exc
    elif isinstance(value, datetime):
        time = value
    else:
        raise TypeError("simulation_time must be a datetime or ISO-8601 string")
    if time.second or time.microsecond:
        raise ValueError("decision simulation_time must be minute-aligned")
    return time.toordinal() * 1440 + time.hour * 60 + time.minute, time.isoformat()


def _core_state(world: WorldState) -> tuple[object, ...]:
    if not isinstance(world, WorldState):
        raise TypeError("world_before must be a WorldState")
    person = world.get_person(1)
    return (
        person.location,
        person.activity,
        person.money,
        tuple(sorted(person.inventory.items())),
        round(person.hunger, 1),
        round(person.energy, 1) if person.energy is not None else None,
    )


class DecisionTriggerAudit:
    """Count attempted calls, overlapping 30-minute bursts, and core-state repeats.

    Each third-or-later call whose preceding two calls fall within the same
    30-minute window contributes one burst. Four calls at 15-minute spacing
    therefore contribute two overlapping bursts. Same-state compares each
    pre-decision world core with that of the immediately preceding attempt;
    clock, activity end time, and minor (<0.1) need drift are excluded.
    """

    def __init__(self) -> None:
        self._minute_indices: list[int] = []
        self._cores: list[tuple[object, ...]] = []
        self._records: list[DecisionCallAudit] = []

    @property
    def records(self) -> tuple[DecisionCallAudit, ...]:
        return tuple(self._records)

    def record_decision(
        self,
        simulation_time: datetime | str,
        world_before: WorldState,
        trigger_reason: TriggerReason | str,
    ) -> DecisionCallAudit:
        minute, timestamp = _minute_index(simulation_time)
        if self._minute_indices and minute <= self._minute_indices[-1]:
            raise ValueError("decision simulation_time must advance")
        if isinstance(trigger_reason, TriggerReason):
            reason = trigger_reason.value
        elif isinstance(trigger_reason, str) and trigger_reason in TriggerReason._value2member_map_:
            reason = trigger_reason
        else:
            raise ValueError("unknown trigger_reason")
        core = _core_state(world_before)
        same_state = bool(self._cores and core == self._cores[-1])
        burst = len(self._minute_indices) >= 2 and minute - self._minute_indices[-2] <= 30
        record = DecisionCallAudit(timestamp, reason, same_state, burst)
        self._minute_indices.append(minute)
        self._cores.append(core)
        self._records.append(record)
        return record

    def summary(self, *, observed_ticks: int, active_minutes: int) -> dict[str, object]:
        if isinstance(observed_ticks, bool) or not isinstance(observed_ticks, int) or observed_ticks < 0:
            raise ValueError("observed_ticks must be a non-negative integer")
        if isinstance(active_minutes, bool) or not isinstance(active_minutes, int) or active_minutes < 0:
            raise ValueError("active_minutes must be a non-negative integer")
        if active_minutes > observed_ticks * 15:
            raise ValueError("active_minutes cannot exceed observed time")
        decisions = len(self._records)
        counts = Counter(record.trigger_reason for record in self._records)
        return {
            "decision_attempts": decisions,
            "decision_burst_count": sum(record.in_decision_burst for record in self._records),
            "same_state_decision_count": sum(record.same_state_as_previous for record in self._records),
            "decisions_per_sim_hour": decisions / (observed_ticks / 4) if observed_ticks else None,
            "ticks_per_decision": observed_ticks / decisions if decisions else None,
            "active_minutes_per_decision": active_minutes / decisions if decisions else None,
            "trigger_reason_counts": {reason.value: counts[reason.value] for reason in TriggerReason},
            "high_decision_frequency_warning": decisions > 30,
        }
