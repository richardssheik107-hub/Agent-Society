"""EAT consumes one owned item and lowers the hunger degree."""

from datetime import datetime, timezone

import pytest

from social_sim.actions import ActionIntent, proposal_to_intent
from social_sim.decision import ActionType, DecisionProposal
from social_sim.effects import EatEffect
from social_sim.rules import EatRule, ReasonCode, RuleEngine
from social_sim.world import OfferState, PersonWorldState, WorldState


def _world(*, inventory: dict[str, int] | None = None, hunger: float = 0.8) -> WorldState:
    return WorldState(
        time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        people={
            1: PersonWorldState(1, "home", 100.0, hunger, inventory or {})
        },
        venues={"restaurant": {"meal": OfferState("meal", 20.0, 10)}},
    )


def test_eat_accepts_any_location_and_declares_hunger_change_without_mutation() -> None:
    world = _world(inventory={"meal": 1})
    before = _world(inventory={"meal": 1})
    intent = ActionIntent(1, ActionType.EAT, "meal")

    result = EatRule().evaluate(world, intent)

    assert result.allowed
    assert result.reason_code is ReasonCode.ACCEPTED
    assert result.effects == (EatEffect(1, "meal", 1, 1, 0.8, 0.2),)
    assert RuleEngine().evaluate(world, intent) == result
    assert world == before
    assert world.get_person(1).inventory["meal"] == 1
    assert world.get_person(1).hunger == 0.8


@pytest.mark.parametrize(
    ("actor_id", "target", "reason"),
    [
        (1, "meal", ReasonCode.ITEM_NOT_OWNED),
        (1, "unknown", ReasonCode.ITEM_NOT_FOUND),
        (1, None, ReasonCode.MISSING_TARGET),
        (999, "meal", ReasonCode.ACTOR_NOT_FOUND),
    ],
)
def test_eat_rejections_have_no_effect_or_mutation(
    actor_id: int, target: str | None, reason: ReasonCode
) -> None:
    world = _world()
    before = _world()
    result = EatRule().evaluate(world, ActionIntent(actor_id, ActionType.EAT, target))
    assert not result.allowed
    assert result.reason_code is reason
    assert result.effects == ()
    assert world == before


def test_eat_hunger_floors_at_zero() -> None:
    result = EatRule().evaluate(
        _world(inventory={"meal": 1}, hunger=0.1), ActionIntent(1, ActionType.EAT, "meal")
    )
    assert result.effects == (EatEffect(1, "meal", 1, 1, 0.1, 0.0),)


def test_unknown_owned_item_cannot_be_eaten_as_a_meal() -> None:
    world = _world(inventory={"rock": 1})
    result = EatRule().evaluate(world, ActionIntent(1, ActionType.EAT, "rock"))
    assert result.reason_code is ReasonCode.ITEM_NOT_FOUND
    assert result.effects == ()


def test_eat_proposal_defaults_one_unit_only_in_python() -> None:
    proposal = DecisionProposal(ActionType.EAT, "meal")
    intent = proposal_to_intent(1, proposal)
    assert intent.params == {"quantity": 1}
    with pytest.raises(ValueError, match="EAT requires"):
        DecisionProposal(ActionType.EAT)
