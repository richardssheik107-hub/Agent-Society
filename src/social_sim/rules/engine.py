"""Small deterministic dispatcher for the supported domain actions."""

from __future__ import annotations

from social_sim.actions.models import ActionIntent
from social_sim.decision.models import ActionType
from social_sim.rules.base import ReasonCode, Rule, RuleResult
from social_sim.rules.activity import ActivityRule
from social_sim.rules.eating import EatRule
from social_sim.rules.movement import MoveRule
from social_sim.rules.purchasing import BuyRule
from social_sim.world.state import WorldState


class RuleEngine:
    def __init__(self) -> None:
        self._rules: dict[ActionType, Rule] = {
            ActionType.MOVE: MoveRule(),
            ActionType.BUY: BuyRule(),
            ActionType.EAT: EatRule(),
            ActionType.SLEEP: ActivityRule(ActionType.SLEEP),
            ActionType.WORK: ActivityRule(ActionType.WORK),
            ActionType.LEISURE: ActivityRule(ActionType.LEISURE),
        }

    def evaluate(self, world: WorldState, intent: ActionIntent) -> RuleResult:
        rule = self._rules.get(intent.action)
        if rule is None:
            return RuleResult(
                actor_id=intent.actor_id,
                action=intent.action,
                allowed=False,
                reason_code=ReasonCode.UNSUPPORTED_ACTION,
            )
        return rule.evaluate(world, intent)
