"""Reducer changes only location in a new state, with stale-effect rejection."""

from datetime import datetime, timezone

import pytest

from social_sim.effects import EatEffect, MoveEffect, PurchaseEffect
from social_sim.reducer import StateConflictError, StateReducer
from social_sim.world import OfferState, PersonWorldState, WorldState


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


def make_lunch_world(*, inventory: dict[str, int] | None = None) -> WorldState:
    return WorldState(
        time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        people={
            1: PersonWorldState(
                1, "restaurant", 100.0, 0.8, inventory=inventory or {}
            )
        },
        venues={"restaurant": {"meal": OfferState("meal", 20.0, 10)}},
    )


def test_purchase_effect_changes_money_stock_and_inventory_only() -> None:
    world = make_lunch_world()
    before = (world.get_person(1), world.get_offer("restaurant", "meal"))
    effect = PurchaseEffect(1, "restaurant", "meal", 1, 20.0, 100.0, 10, 0)

    after = StateReducer().apply(world, [effect])

    assert after.get_person(1).location == "restaurant"
    assert after.get_person(1).money == 80.0
    assert after.get_person(1).hunger == 0.8
    assert after.get_person(1).inventory["meal"] == 1
    assert after.get_offer("restaurant", "meal").stock == 9
    assert (world.get_person(1), world.get_offer("restaurant", "meal")) == before


def test_eat_effect_reduces_hunger_and_inventory_only() -> None:
    world = make_lunch_world(inventory={"meal": 1})
    effect = EatEffect(1, "meal", 1, 1, 0.8, 0.2)

    after = StateReducer().apply(world, [effect])

    assert after.get_person(1).location == "restaurant"
    assert after.get_person(1).money == 100.0
    assert after.get_person(1).hunger == 0.2
    assert after.get_person(1).inventory["meal"] == 0
    assert after.get_offer("restaurant", "meal").stock == 10
    assert world.get_person(1).inventory["meal"] == 1
    assert world.get_person(1).hunger == 0.8


@pytest.mark.parametrize(
    "effect",
    [
        PurchaseEffect(1, "restaurant", "meal", 1, 20.0, 99.0, 10, 0),
        PurchaseEffect(1, "restaurant", "meal", 1, 20.0, 100.0, 9, 0),
        PurchaseEffect(1, "restaurant", "meal", 1, 20.0, 100.0, 10, 1),
        EatEffect(1, "meal", 1, 1, 0.8, 0.2),
    ],
)
def test_stale_purchase_or_eat_effect_is_state_conflict(effect: object) -> None:
    world = make_lunch_world()
    with pytest.raises(StateConflictError, match="STATE_CONFLICT"):
        StateReducer().apply(world, [effect])  # type: ignore[list-item]
    assert world.get_person(1).money == 100.0
    assert world.get_person(1).hunger == 0.8
    assert world.get_offer("restaurant", "meal").stock == 10
