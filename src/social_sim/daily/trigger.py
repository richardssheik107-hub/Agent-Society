"""Deterministic gate for daily decisions; ordinary ticks never call a model."""

from __future__ import annotations

from datetime import datetime
from enum import Enum


class TriggerReason(str, Enum):
    """Why a daily decision was requested at this simulation instant."""

    NO_ACTIVE_ACTIVITY = "NO_ACTIVE_ACTIVITY"
    ACTIVITY_COMPLETED = "ACTIVITY_COMPLETED"
    ACTION_REJECTED = "ACTION_REJECTED"
    OBLIGATION_BOUNDARY = "OBLIGATION_BOUNDARY"
    CRITICAL_NEED = "CRITICAL_NEED"
    WORLD_EVENT = "WORLD_EVENT"


class DecisionTrigger:
    """Request a decision only when the current activity cannot simply continue.

    ``time`` and ``activity_end_time`` are datetimes in the daily runner. Integer
    simulation minutes are also accepted for small, wall-clock-free unit tests.
    An ISO-8601 end time is accepted because it is the JSON-friendly world field.
    """

    @staticmethod
    def reason(
        time: datetime | int,
        activity: str | None,
        activity_end_time: datetime | int | str | None,
        *,
        rejected: bool = False,
        activity_completed: bool = False,
        obligation_boundary: bool = False,
        critical_need: bool = False,
        world_event_interrupt: bool = False,
    ) -> TriggerReason | None:
        if rejected:
            return TriggerReason.ACTION_REJECTED
        if world_event_interrupt:
            return TriggerReason.WORLD_EVENT
        if activity_completed:
            return TriggerReason.ACTIVITY_COMPLETED
        # An obligation boundary is relevant once an activity is absent or
        # completed; the A1 benchmark does not preempt an ongoing activity for
        # ordinary work-window boundaries.
        if activity is None or activity == "":
            if critical_need:
                return TriggerReason.CRITICAL_NEED
            if obligation_boundary:
                return TriggerReason.OBLIGATION_BOUNDARY
            return TriggerReason.NO_ACTIVE_ACTIVITY
        if activity_end_time is None:
            return None

        end: datetime | int
        if isinstance(activity_end_time, str):
            try:
                end = datetime.fromisoformat(activity_end_time)
            except ValueError as exc:
                raise ValueError("activity_end_time must be ISO-8601") from exc
        else:
            end = activity_end_time
        if isinstance(time, bool) or isinstance(end, bool):
            raise TypeError("time and activity_end_time must be datetimes or integer minutes")
        if isinstance(time, datetime) and isinstance(end, datetime):
            return TriggerReason.ACTIVITY_COMPLETED if time >= end else None
        if isinstance(time, int) and isinstance(end, int):
            return TriggerReason.ACTIVITY_COMPLETED if time >= end else None
        raise TypeError("time and activity_end_time must use the same representation")

    @staticmethod
    def should_decide(
        time: datetime | int,
        activity: str | None,
        activity_end_time: datetime | int | str | None,
        *,
        rejected: bool = False,
        activity_completed: bool = False,
        obligation_boundary: bool = False,
        critical_need: bool = False,
        world_event_interrupt: bool = False,
    ) -> bool:
        """Backward-compatible boolean form of :meth:`reason`."""
        return DecisionTrigger.reason(
            time, activity, activity_end_time,
            rejected=rejected,
            activity_completed=activity_completed,
            obligation_boundary=obligation_boundary,
            critical_need=critical_need,
            world_event_interrupt=world_event_interrupt,
        ) is not None
