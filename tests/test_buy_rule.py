"""BUY checks objective venue facts and only declares one-unit effects."""

from datetime import datetime, timezone

import pytest

from social_sim.actions import ActionIntent
from social_sim.decision import ActionType, DecisionProposal
from social_sim.effects import PurchaseEffect
from social_sim.rules import BuyRule, ReasonCode, RuleEngine
from social_sim.world import OfferState, PersonWorldState, WorldState


def _world(
    *, location: str = "restaurant", money: float = 100.0, stock: int = 10
) -> WorldState:
    return WorldState(
        time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        people={1: PersonWorldState(1, location, money, 0.8)},
        venues={"restaurant": {"meal": OfferState("meal", 20.0, stock)}},
    )


def test_buy_accepts_and_declares_snapshot_effect_without_mutation() -> None:
    world = _world()
    before = _world()
    intent = ActionIntent(1, ActionType.BUY, "meal")

    result = BuyRule().evaluate(world, intent)

    assert result.allowed
    assert result.reason_code is ReasonCode.ACCEPTED
    assert result.effects == (
        PurchaseEffect(1, "restaurant", "meal", 1, 20.0, 100.0, 10, 0),
    )
    assert RuleEngine().evaluate(world, intent) == result
    assert world == before
    assert world.get_person(1).money == 100.0
    assert world.get_offer("restaurant", "meal").stock == 10


@pytest.mark.parametrize(
    ("world", "actor_id", "target", "reason"),
    [
        (_world(location="home"), 1, "meal", ReasonCode.NOT_AT_SELLER),
        (_world(money=19.0), 1, "meal", ReasonCode.INSUFFICIENT_FUNDS),
        (_world(stock=0), 1, "meal", ReasonCode.OUT_OF_STOCK),
        (_world(), 1, "unknown", ReasonCode.ITEM_NOT_FOUND),
        (_world(), 1, None, ReasonCode.MISSING_TARGET),
        (_world(), 999, "meal", ReasonCode.ACTOR_NOT_FOUND),
    ],
)
def test_buy_rejections_have_no_effect_or_mutation(
    world: WorldState, actor_id: int, target: str | None, reason: ReasonCode
) -> None:
    before = WorldState(world.time, world.people, world.locations, world.venues)
    result = BuyRule().evaluate(world, ActionIntent(actor_id, ActionType.BUY, target))
    assert not result.allowed
    assert result.reason_code is reason
    assert result.effects == ()
    assert world == before


def test_buy_proposal_keeps_two_fields_and_python_adds_quantity() -> None:
    from social_sim.actions import proposal_to_intent

    proposal = DecisionProposal(ActionType.BUY, "meal")
    intent = proposal_to_intent(1, proposal)
    assert (intent.action, intent.target, intent.params) == (
        ActionType.BUY,
        "meal",
        {"quantity": 1},
    )
    with pytest.raises(TypeError):
        DecisionProposal(ActionType.BUY, "meal", quantity=1)  # type: ignore[call-arg]


def test_buy_rule_rejects_wrong_action() -> None:
    result = BuyRule().evaluate(_world(), ActionIntent(1, ActionType.WAIT))
    assert result.reason_code is ReasonCode.UNSUPPORTED_ACTION
