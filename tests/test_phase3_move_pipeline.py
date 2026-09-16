"""A proposal may become an intent, but only rules and reducer make it real."""

from datetime import datetime, timezone

from social_sim.actions import proposal_to_intent
from social_sim.decision import ActionType, DecisionProposal
from social_sim.effects import MoveEffect
from social_sim.reducer import StateReducer
from social_sim.rules import RuleEngine
from social_sim.world import PersonWorldState, WorldState


def make_world(*, locations: tuple[str, ...] = ("home", "park", "restaurant")) -> WorldState:
    return WorldState(
        time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        people={1: PersonWorldState(1, "home", 100.0, 0.8)},
        locations=locations,
    )


def test_valid_move_closed_loop_changes_only_new_world_location() -> None:
    old_world = make_world()
    snapshot = (old_world.time, old_world.people, old_world.locations)
    proposal = DecisionProposal(action=ActionType.MOVE, target="restaurant")
    intent = proposal_to_intent(1, proposal)
    result = RuleEngine().evaluate(old_world, intent)

    assert result.actor_id == 1
    assert result.action is ActionType.MOVE
    assert result.allowed is True
    assert result.reason_code == "ACCEPTED"
    assert result.effects == (MoveEffect(1, "home", "restaurant"),)
    assert (old_world.time, old_world.people, old_world.locations) == snapshot

    new_world = StateReducer().apply(old_world, result.effects)
    assert old_world.get_person(1) == PersonWorldState(1, "home", 100.0, 0.8)
    assert new_world.get_person(1) == PersonWorldState(1, "restaurant", 100.0, 0.8)
    assert new_world.time == old_world.time
    assert new_world.locations == old_world.locations


def test_invalid_move_rejected_without_reducer_or_world_change() -> None:
    world = make_world()
    before = (world.time, world.people, world.locations)
    intent = proposal_to_intent(1, DecisionProposal(action="MOVE", target="moon"))
    result = RuleEngine().evaluate(world, intent)

    assert result.actor_id == 1
    assert result.action is ActionType.MOVE
    assert result.allowed is False
    assert result.reason_code == "UNKNOWN_DESTINATION"
    assert result.effects == ()
    assert (world.time, world.people, world.locations) == before
    assert world.get_person(1).location == "home"


def test_move_rule_uses_world_location_registry_not_a_second_list() -> None:
    world = make_world(locations=("home", "park"))
    result = RuleEngine().evaluate(
        world, proposal_to_intent(1, DecisionProposal("MOVE", "restaurant"))
    )
    assert result.allowed is False
    assert result.reason_code == "UNKNOWN_DESTINATION"
    assert result.effects == ()
