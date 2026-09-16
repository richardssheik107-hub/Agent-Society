"""Deterministic, read-only rule contracts for proposed actions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from social_sim.actions.models import ActionIntent
from social_sim.decision.models import ActionType
from social_sim.effects.models import Effect
from social_sim.world.state import WorldState


class ReasonCode(str, Enum):
    ACCEPTED = "ACCEPTED"
    ACTOR_NOT_FOUND = "ACTOR_NOT_FOUND"
    MISSING_TARGET = "MISSING_TARGET"
    UNKNOWN_DESTINATION = "UNKNOWN_DESTINATION"
    ALREADY_AT_DESTINATION = "ALREADY_AT_DESTINATION"
    ITEM_NOT_FOUND = "ITEM_NOT_FOUND"
    NOT_AT_SELLER = "NOT_AT_SELLER"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    ITEM_NOT_OWNED = "ITEM_NOT_OWNED"
    UNSUPPORTED_ACTION = "UNSUPPORTED_ACTION"


@dataclass(frozen=True)
class RuleResult:
    """Auditable judgment and declared effects; never an executed transition."""

    actor_id: int
    action: ActionType
    allowed: bool
    reason_code: ReasonCode
    effects: tuple[Effect, ...] = ()

    def __post_init__(self) -> None:
        if self.allowed != (self.reason_code is ReasonCode.ACCEPTED):
            raise ValueError("allowed and reason_code must agree")
        if not self.allowed and self.effects:
            raise ValueError("rejected actions cannot declare effects")


class Rule(Protocol):
    action_type: ActionType

    def evaluate(self, world: WorldState, intent: ActionIntent) -> RuleResult: ...
