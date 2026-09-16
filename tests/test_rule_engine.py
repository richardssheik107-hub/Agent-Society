"""The Phase 3 dispatcher supports MOVE only and cannot mutate state."""

from datetime import datetime, timezone

import pytest

from social_sim.actions import ActionIntent
from social_sim.decision import ActionType
from social_sim.effects import MoveEffect
from social_sim.rules import ReasonCode, RuleEngine
from social_sim.world import PersonWorldState, WorldState


def _world() -> WorldState:
    return WorldState(
        time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        people={
            1: PersonWorldState(
                agent_id=1, location="home", money=100.0, hunger=0.8
            )
        },
    )


def test_engine_dispatches_move_deterministically_without_mutation() -> None:
    world = _world()
    intent = ActionIntent(actor_id=1, action=ActionType.MOVE, target="park")
    engine = RuleEngine()

    first = engine.evaluate(world, intent)
    second = engine.evaluate(world, intent)

    assert first == second
    assert first.allowed
    assert first.reason_code is ReasonCode.ACCEPTED
    assert first.effects == (MoveEffect(1, "home", "park"),)
    assert world == _world()
    assert world.get_person(1).location == "home"


@pytest.mark.parametrize("action", [ActionType.WAIT, ActionType.REST])
def test_engine_rejects_unsupported_actions_without_effects(action: ActionType) -> None:
    world = _world()
    result = RuleEngine().evaluate(world, ActionIntent(actor_id=1, action=action))

    assert result.actor_id == 1
    assert result.action is action
    assert result.allowed is False
    assert result.reason_code is ReasonCode.UNSUPPORTED_ACTION
    assert result.effects == ()
    assert world == _world()


def test_engine_rejects_invalid_move_without_mutation() -> None:
    world = _world()

    result = RuleEngine().evaluate(
        world, ActionIntent(actor_id=1, action=ActionType.MOVE, target="moon")
    )

    assert result.reason_code is ReasonCode.UNKNOWN_DESTINATION
    assert result.effects == ()
    assert world == _world()
