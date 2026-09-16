"""EAT preconditions and hunger reduction; no state mutation."""

from __future__ import annotations

from social_sim.actions.models import ActionIntent
from social_sim.decision.models import ActionType
from social_sim.effects.models import EatEffect, MEAL_HUNGER_REDUCTION
from social_sim.rules.base import ReasonCode, RuleResult
from social_sim.world.state import WorldState


class EatRule:
    action_type = ActionType.EAT

    def evaluate(self, world: WorldState, intent: ActionIntent) -> RuleResult:
        if intent.action is not ActionType.EAT:
            return self._reject(intent, ReasonCode.UNSUPPORTED_ACTION)

        person = world.people.get(intent.actor_id)
        if person is None:
            return self._reject(intent, ReasonCode.ACTOR_NOT_FOUND)

        item_id = intent.target
        if not isinstance(item_id, str) or not item_id.strip():
            return self._reject(intent, ReasonCode.MISSING_TARGET)
        if not world.has_item(item_id):
            return self._reject(intent, ReasonCode.ITEM_NOT_FOUND)
        quantity_before = person.inventory.get(item_id, 0)
        if quantity_before < 1:
            return self._reject(intent, ReasonCode.ITEM_NOT_OWNED)

        new_hunger = round(max(0.0, person.hunger - MEAL_HUNGER_REDUCTION), 6)
        return RuleResult(
            actor_id=intent.actor_id,
            action=intent.action,
            allowed=True,
            reason_code=ReasonCode.ACCEPTED,
            effects=(
                EatEffect(
                    agent_id=intent.actor_id,
                    item_id=item_id,
                    quantity=1,
                    expected_inventory_before=quantity_before,
                    expected_hunger_before=person.hunger,
                    new_hunger=new_hunger,
                ),
            ),
        )

    @staticmethod
    def _reject(intent: ActionIntent, reason_code: ReasonCode) -> RuleResult:
        return RuleResult(
            actor_id=intent.actor_id,
            action=intent.action,
            allowed=False,
            reason_code=reason_code,
        )
