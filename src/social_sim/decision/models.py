"""A proposal is a requested next action, not an executed world transition."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ActionType(str, Enum):
    WAIT = "WAIT"
    REST = "REST"
    MOVE = "MOVE"
    BUY = "BUY"
    EAT = "EAT"
    SLEEP = "SLEEP"
    WORK = "WORK"
    LEISURE = "LEISURE"
    PERSONAL_CARE = "PERSONAL_CARE"
    CHORES = "CHORES"


@dataclass(frozen=True)
class DecisionProposal:
    """The two-field, read-only output of one compact decision call."""

    action: ActionType
    target: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.action, str):
            try:
                action = ActionType(self.action)
            except ValueError as exc:
                raise ValueError(f"Unknown action: {self.action!r}") from exc
            object.__setattr__(self, "action", action)
        elif not isinstance(self.action, ActionType):
            raise ValueError(f"Unknown action: {self.action!r}")

        if self.action in (ActionType.MOVE, ActionType.BUY, ActionType.EAT):
            if not isinstance(self.target, str) or not self.target.strip():
                raise ValueError(f"{self.action.value} requires a nonempty string target")
        elif self.target is not None:
            raise ValueError(f"{self.action.value} requires target=None")
