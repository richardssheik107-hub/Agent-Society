"""Decision proposals are small immutable requests, never world effects."""

from dataclasses import FrozenInstanceError

import pytest

from social_sim.decision.models import ActionType, DecisionProposal


def test_wait_is_valid_without_target() -> None:
    proposal = DecisionProposal(action=ActionType.WAIT)
    assert proposal.action is ActionType.WAIT
    assert proposal.target is None


def test_rest_is_valid_without_target() -> None:
    assert DecisionProposal(action="REST") == DecisionProposal(ActionType.REST)


def test_move_is_valid_with_target() -> None:
    proposal = DecisionProposal(action=ActionType.MOVE, target="restaurant")
    assert (proposal.action, proposal.target) == (ActionType.MOVE, "restaurant")


@pytest.mark.parametrize("action", ["FLY", "wait", "", 1, None])
def test_unknown_action_rejected(action: object) -> None:
    with pytest.raises(ValueError, match="Unknown action"):
        DecisionProposal(action=action)


@pytest.mark.parametrize("target", [None, "", "   ", 7])
def test_move_without_nonempty_string_target_rejected(target: object) -> None:
    with pytest.raises(ValueError, match="MOVE requires"):
        DecisionProposal(action=ActionType.MOVE, target=target)


@pytest.mark.parametrize("action", [ActionType.WAIT, ActionType.REST])
def test_non_move_target_rejected(action: ActionType) -> None:
    with pytest.raises(ValueError, match="requires target=None"):
        DecisionProposal(action=action, target="park")


def test_world_mutation_fields_are_not_part_of_proposal() -> None:
    with pytest.raises(TypeError):
        DecisionProposal(action=ActionType.WAIT, money=0)  # type: ignore[call-arg]
    proposal = DecisionProposal(action=ActionType.WAIT)
    with pytest.raises(FrozenInstanceError):
        proposal.target = "park"  # type: ignore[misc]
