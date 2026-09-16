"""Zero-LLM Phase 3 acceptance: valid MOVE, rejected MOVE, no hidden world writes."""

from __future__ import annotations

from datetime import datetime, timezone

from social_sim.actions import proposal_to_intent
from social_sim.decision import DecisionProposal
from social_sim.effects import MoveEffect
from social_sim.reducer import StateReducer
from social_sim.rules import RuleEngine
from social_sim.world import PersonWorldState, WorldState


def snapshot(world: WorldState) -> tuple:
    return world.time, world.people, world.locations


def main() -> None:
    world = WorldState(
        time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        people={1: PersonWorldState(1, "home", 100.0, 0.8)},
    )
    before = snapshot(world)
    assert world.get_person(1) == PersonWorldState(1, "home", 100.0, 0.8)
    print("WORLD_INIT_OK")

    proposal = DecisionProposal(action="MOVE", target="restaurant")
    print("PROPOSAL_OK")
    intent = proposal_to_intent(1, proposal)
    assert intent.actor_id == 1 and intent.target == "restaurant"
    print("INTENT_OK")

    result = RuleEngine().evaluate(world, intent)
    assert result.allowed and result.reason_code == "ACCEPTED"
    assert snapshot(world) == before
    print("RULE_ACCEPTED")
    assert result.effects == (MoveEffect(1, "home", "restaurant"),)
    print("EFFECT_CREATED")

    new_world = StateReducer().apply(world, result.effects)
    print("REDUCER_APPLIED")
    assert snapshot(world) == before
    old_person = world.get_person(1)
    new_person = new_world.get_person(1)
    assert old_person.location == "home"
    assert new_person.location == "restaurant"
    assert old_person.money == new_person.money == 100.0
    assert old_person.hunger == new_person.hunger == 0.8
    assert new_world.time == world.time and new_world.locations == world.locations
    print(f"OLD_LOCATION={old_person.location}")
    print(f"NEW_LOCATION={new_person.location}")
    print("MONEY_UNCHANGED")
    print("HUNGER_UNCHANGED")

    invalid = proposal_to_intent(1, DecisionProposal(action="MOVE", target="moon"))
    rejected = RuleEngine().evaluate(world, invalid)
    assert not rejected.allowed and rejected.reason_code == "UNKNOWN_DESTINATION"
    assert rejected.effects == ()
    assert snapshot(world) == before
    print("INVALID_MOVE_REJECTED")
    print(f"REASON={rejected.reason_code.value}")
    print("WORLD_UNCHANGED_AFTER_REJECT")
    print("ZERO_LLM_CALLS")
    print("PHASE3_MOVE_OK")


if __name__ == "__main__":
    main()
