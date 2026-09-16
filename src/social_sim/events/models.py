"""Compact deterministic events for action feedback and audit."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from social_sim.decision.models import ActionType


class EventType(str, Enum):
    MOVED = "MOVED"
    PURCHASED = "PURCHASED"
    ATE = "ATE"
    ACTION_REJECTED = "ACTION_REJECTED"


@dataclass(frozen=True)
class DomainEvent:
    event_id: str
    actor_id: int
    event_type: EventType
    action: ActionType
    target: str | None
    success: bool
    reason_code: str

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, str) or not self.event_id.strip():
            raise ValueError("event_id must be a nonempty string")
        if not isinstance(self.actor_id, int) or isinstance(self.actor_id, bool):
            raise ValueError("actor_id must be an integer")
        if isinstance(self.event_type, str):
            object.__setattr__(self, "event_type", EventType(self.event_type))
        elif not isinstance(self.event_type, EventType):
            raise ValueError("event_type must be an EventType")
        if isinstance(self.action, str):
            object.__setattr__(self, "action", ActionType(self.action))
        elif not isinstance(self.action, ActionType):
            raise ValueError("action must be an ActionType")
        if self.target is not None and not isinstance(self.target, str):
            raise ValueError("target must be a string or None")
        if not isinstance(self.success, bool):
            raise ValueError("success must be a bool")
        if not isinstance(self.reason_code, str) or not self.reason_code:
            raise ValueError("reason_code must be a nonempty string")
        if self.success == (self.event_type is EventType.ACTION_REJECTED):
            raise ValueError("success and event_type disagree")
        if self.success != (self.reason_code == "ACCEPTED"):
            raise ValueError("success and reason_code disagree")

    def compact(self) -> str:
        """Only the action outcome needed for bounded decision feedback."""

        if not self.success:
            return f"{self.event_type.value}:{self.reason_code}"
        return (
            f"{self.event_type.value}:{self.target}"
            if self.target is not None
            else self.event_type.value
        )
