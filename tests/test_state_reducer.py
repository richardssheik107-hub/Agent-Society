"""Reducer changes only location in a new state, with stale-effect rejection."""

from datetime import datetime, timezone

import pytest

from social_sim.effects import MoveEffect
from social_sim.reducer import StateConflictError, StateReducer
from social_sim.world import PersonWorldState, WorldState


def make_world() -> WorldState:
    return WorldState(
        time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        people={
            1: PersonWorldState(1, "home", 100.0, 0.8),
            2: PersonWorldState(2, "park", 47.0, 0.3),
        },
    )


def test_apply_move_returns_new_world_with_location_only_changed() -> None:
    world = make_world()
    before = world.people
    after = StateReducer().apply(world, [MoveEffect(1, "home", "restaurant")])

    assert after is not world
    assert world.people == before
    assert world.get_person(1).location == "home"
    assert after.get_person(1) == PersonWorldState(1, "restaurant", 100.0, 0.8)
    assert after.get_person(2) == before[2]
    assert after.time == world.time
    assert after.locations == world.locations


def test_no_effects_returns_unchanged_state() -> None:
    world = make_world()
    assert StateReducer().apply(world, []) is world


def test_stale_source_location_is_state_conflict() -> None:
    world = make_world()
    with pytest.raises(StateConflictError, match="STATE_CONFLICT"):
        StateReducer().apply(world, [MoveEffect(1, "park", "restaurant")])
    assert world.get_person(1).location == "home"


def test_unknown_destination_is_rejected_by_reducer_too() -> None:
    world = make_world()
    with pytest.raises(StateConflictError, match="STATE_CONFLICT"):
        StateReducer().apply(world, [MoveEffect(1, "home", "moon")])
    assert world.get_person(1).location == "home"


def test_unknown_actor_is_state_conflict() -> None:
    world = make_world()
    with pytest.raises(StateConflictError, match="STATE_CONFLICT"):
        StateReducer().apply(world, [MoveEffect(999, "home", "park")])
    assert world == make_world()


def test_invalid_effect_type_fails_explicitly() -> None:
    world = make_world()
    with pytest.raises(TypeError, match="Unsupported effect type"):
        StateReducer().apply(world, [object()])
    assert world == make_world()


def test_failed_batch_cannot_mutate_original_world() -> None:
    world = make_world()
    with pytest.raises(StateConflictError, match="STATE_CONFLICT"):
        StateReducer().apply(
            world,
            [MoveEffect(1, "home", "restaurant"), MoveEffect(2, "home", "restaurant")],
        )
    assert world == make_world()
