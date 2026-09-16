"""MOVE rules are deterministic, auditable, and read-only."""

from datetime import datetime, timezone

import pytest

from social_sim.actions import ActionIntent
from social_sim.decision import ActionType
from social_sim.effects import MoveEffect
from social_sim.rules import MoveRule, ReasonCode, RuleResult
from social_sim.world import PersonWorldState, WorldState


def _world(*, locations: tuple[str, ...] = ("home", "park", "restaurant")) -> WorldState:
    return WorldState(
        time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        people={
            1: PersonWorldState(
                agent_id=1, location="home", money=100.0, hunger=0.8
            )
        },
        locations=locations,
    )


@pytest.mark.parametrize("destination", ["restaurant", "park"])
def test_valid_move_declares_effect_without_mutating_world(destination: str) -> None:
    world = _world()
    before = _world()
    intent = ActionIntent(actor_id=1, action=ActionType.MOVE, target=destination)

    result = MoveRule().evaluate(world, intent)

    assert result == RuleResult(
        actor_id=1,
        action=ActionType.MOVE,
        allowed=True,
        reason_code=ReasonCode.ACCEPTED,
        effects=(MoveEffect(1, "home", destination),),
    )
    assert world == before
    assert world.get_person(1).location == "home"


@pytest.mark.parametrize(
    ("actor_id", "target", "reason"),
    [
        (1, "moon", ReasonCode.UNKNOWN_DESTINATION),
        (999, "park", ReasonCode.ACTOR_NOT_FOUND),
        (1, None, ReasonCode.MISSING_TARGET),
        (1, "", ReasonCode.MISSING_TARGET),
        (1, "   ", ReasonCode.MISSING_TARGET),
        (1, "home", ReasonCode.ALREADY_AT_DESTINATION),
    ],
)
def test_invalid_move_is_rejected_without_effect_or_mutation(
    actor_id: int, target: str | None, reason: ReasonCode
) -> None:
    world = _world()
    before = _world()

    result = MoveRule().evaluate(
        world, ActionIntent(actor_id=actor_id, action=ActionType.MOVE, target=target)
    )

    assert result.actor_id == actor_id
    assert result.action is ActionType.MOVE
    assert result.allowed is False
    assert result.reason_code is reason
    assert result.effects == ()
    assert world == before


def test_move_uses_world_locations_as_only_destination_source() -> None:
    world = _world(locations=("home", "park"))

    result = MoveRule().evaluate(
        world, ActionIntent(actor_id=1, action=ActionType.MOVE, target="restaurant")
    )

    assert result.reason_code is ReasonCode.UNKNOWN_DESTINATION
    assert result.effects == ()


def test_move_rule_directly_rejects_non_move_action() -> None:
    result = MoveRule().evaluate(
        _world(), ActionIntent(actor_id=1, action=ActionType.WAIT)
    )

    assert result.reason_code is ReasonCode.UNSUPPORTED_ACTION
    assert not result.allowed
    assert result.effects == ()


def test_rule_result_rejects_inconsistent_audit_fields() -> None:
    with pytest.raises(ValueError, match="must agree"):
        RuleResult(1, ActionType.MOVE, True, ReasonCode.UNKNOWN_DESTINATION)
    with pytest.raises(ValueError, match="cannot declare effects"):
        RuleResult(
            1,
            ActionType.MOVE,
            False,
            ReasonCode.UNKNOWN_DESTINATION,
            effects=(MoveEffect(1, "home", "park"),),
        )
