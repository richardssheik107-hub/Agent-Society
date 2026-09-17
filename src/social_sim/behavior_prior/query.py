"""Query and result contract; no simulator-private need or money fields."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .models import BUCKET_COUNT, CORE7, TICK_BUCKET_MINUTES


@dataclass(frozen=True)
class PriorQuery:
    bucket: int
    previous_activity: str | None
    day_type: str = "weekday"
    employment: str = "employed"

    def __post_init__(self) -> None:
        if not 0 <= self.bucket < BUCKET_COUNT:
            raise ValueError("bucket must be one of 48 half-hour intervals")
        if self.previous_activity is not None and self.previous_activity not in CORE7:
            raise ValueError("previous_activity must be Core7 or None")
        if (self.day_type, self.employment) != ("weekday", "employed"):
            raise ValueError("A2-Fast index is restricted to employed weekdays")

    @classmethod
    def at(cls, when: datetime, previous_activity: str | None) -> PriorQuery:
        return cls((when.hour * 60 + when.minute) // TICK_BUCKET_MINUTES, previous_activity)


@dataclass(frozen=True)
class PriorResult:
    activities: tuple[str, ...]
    fallback_level: str
    support_count: int
    excluded_other_mass: float
    bucket: int
    previous_activity: str | None


def previous_activity_from_events(events: tuple[object, ...]) -> str | None:
    """Find last successful canonical action; BUY is not a Core7 activity."""
    for event in reversed(events):
        if getattr(event, "success", False):
            value = getattr(getattr(event, "action", None), "value", None)
            if value in CORE7:
                return value
    return None
