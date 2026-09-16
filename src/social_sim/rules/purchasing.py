"""BUY preconditions and one-unit effect declaration; no state mutation."""

from __future__ import annotations

from social_sim.actions.models import ActionIntent
from social_sim.decision.models import ActionType
from social_sim.effects.models import PurchaseEffect
from social_sim.rules.base import ReasonCode, RuleResult
from social_sim.world.state import WorldState


class BuyRule:
    action_type = ActionType.BUY

    def evaluate(self, world: WorldState, intent: ActionIntent) -> RuleResult:
        if intent.action is not ActionType.BUY:
            return self._reject(intent, ReasonCode.UNSUPPORTED_ACTION)

        person = world.people.get(intent.actor_id)
        if person is None:
            return self._reject(intent, ReasonCode.ACTOR_NOT_FOUND)

        item_id = intent.target
        if not isinstance(item_id, str) or not item_id.strip():
            return self._reject(intent, ReasonCode.MISSING_TARGET)
        if not world.has_item(item_id):
            return self._reject(intent, ReasonCode.ITEM_NOT_FOUND)

        offer = world.get_offer(person.location, item_id)
        if offer is None:
            return self._reject(intent, ReasonCode.NOT_AT_SELLER)
        if offer.stock < 1:
            return self._reject(intent, ReasonCode.OUT_OF_STOCK)
        if person.money < offer.price:
            return self._reject(intent, ReasonCode.INSUFFICIENT_FUNDS)

        return RuleResult(
            actor_id=intent.actor_id,
            action=intent.action,
            allowed=True,
            reason_code=ReasonCode.ACCEPTED,
            effects=(
                PurchaseEffect(
                    agent_id=intent.actor_id,
                    location_id=person.location,
                    item_id=item_id,
                    quantity=1,
                    unit_price=offer.price,
                    expected_money_before=person.money,
                    expected_stock_before=offer.stock,
                    expected_inventory_before=person.inventory.get(item_id, 0),
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
