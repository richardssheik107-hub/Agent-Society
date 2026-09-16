"""The model proposes; Python supplies identity and later applies any effect."""

from dataclasses import FrozenInstanceError

import pytest

from social_sim.actions import ActionIntent, proposal_to_intent
from social_sim.decision.models import ActionType, DecisionProposal
from social_sim.effects import MoveEffect


def test_move_proposal_becomes_intent_with_python_owned_actor() -> None:
    proposal = DecisionProposal(action=ActionType.MOVE, target="restaurant")

    intent = proposal_to_intent(actor_id=1, proposal=proposal)

    assert intent == ActionIntent(1, ActionType.MOVE, "restaurant")
    assert intent.params == {}
    assert proposal == DecisionProposal(ActionType.MOVE, "restaurant")


def test_non_move_proposal_retains_no_target() -> None:
    intent = proposal_to_intent(1, DecisionProposal(ActionType.WAIT))
    assert intent.action is ActionType.WAIT
    assert intent.target is None


def test_intent_can_represent_missing_target_for_rule_rejection() -> None:
    assert ActionIntent(1, ActionType.MOVE).target is None
    assert ActionIntent(1, "MOVE", " ").target == " "


def test_intent_params_are_copied_and_read_only() -> None:
    source = {"note": "local"}
    intent = ActionIntent(1, ActionType.MOVE, "park", source)
    source["note"] = "changed"
    assert intent.params == {"note": "local"}
    with pytest.raises(TypeError):
        intent.params["note"] = "changed"  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        intent.target = "home"  # type: ignore[misc]


@pytest.mark.parametrize("actor_id", [None, 1.5, "1", True])
def test_invalid_actor_id_rejected(actor_id: object) -> None:
    with pytest.raises(ValueError, match="actor_id"):
        ActionIntent(actor_id, ActionType.MOVE, "park")  # type: ignore[arg-type]


def test_proposal_adapter_requires_proposal() -> None:
    with pytest.raises(TypeError, match="DecisionProposal"):
        proposal_to_intent(1, {"action": "MOVE"})  # type: ignore[arg-type]


@pytest.mark.parametrize("quantity", [0, 2, True, 1.0, "1"])
def test_buy_and_eat_intents_reject_non_unit_quantity(quantity: object) -> None:
    for action in (ActionType.BUY, ActionType.EAT):
        with pytest.raises(ValueError, match="quantity=1 only"):
            ActionIntent(1, action, "meal", {"quantity": quantity})


def test_move_effect_is_declarative_and_immutable() -> None:
    effect = MoveEffect(agent_id=1, from_location="home", to_location="restaurant")
    assert (effect.agent_id, effect.from_location, effect.to_location) == (
        1,
        "home",
        "restaurant",
    )
    with pytest.raises(FrozenInstanceError):
        effect.to_location = "park"  # type: ignore[misc]


@pytest.mark.parametrize("from_location,to_location", [("", "park"), ("home", "")])
def test_move_effect_requires_explicit_locations(
    from_location: str, to_location: str
) -> None:
    with pytest.raises(ValueError, match="location"):
        MoveEffect(1, from_location, to_location)
