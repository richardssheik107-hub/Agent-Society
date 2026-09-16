"""Fast local tests; no AgentSociety runtime or LLM request is started."""

from datetime import datetime, timezone
import pickle

import pytest

from social_sim.world import ObservationBuilder, OfferState, PersonWorldState, WorldState
from social_sim.world.env import RuleWorldEnv


def make_world() -> WorldState:
    return WorldState(
        time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        people={
            1: PersonWorldState(
                agent_id=1, location="home", money=100.0, hunger=0.8
            )
        },
    )


def test_world_initializes_alice() -> None:
    alice = make_world().get_person(1)
    assert (alice.location, alice.money, alice.hunger) == ("home", 100.0, 0.8)


def test_observe_returns_structured_facts() -> None:
    observation = RuleWorldEnv(make_world()).observe_person(1)
    assert observation == {
        "agent_id": 1,
        "time": "2026-01-01T00:00:00+00:00",
        "location": "home",
        "money": 100.0,
        "hunger": 0.8,
    }


def test_observe_does_not_change_world() -> None:
    world = make_world()
    before = (world.time, world.people)
    RuleWorldEnv(world).observe_person(1)
    assert (world.time, world.people) == before
    exposed_people = world.people
    exposed_people.clear()
    assert world.get_person(1).location == "home"


def test_unknown_agent_is_explicit() -> None:
    world = make_world()
    with pytest.raises(ValueError, match="Unknown agent_id: 999"):
        world.get_person(999)
    assert RuleWorldEnv(world).observe_person(999) == {
        "agent_id": 999,
        "error": "unknown_agent_id",
    }


def test_observation_builder_is_local_and_read_only() -> None:
    world = make_world()
    before = WorldState(time=world.time, people=world.people)
    observation = ObservationBuilder(world).build(1)
    assert observation.to_dict() == RuleWorldEnv(world).observe_person(1)
    assert set(observation.to_dict()) == {
        "agent_id", "time", "location", "money", "hunger"
    }
    assert world == before
    with pytest.raises(ValueError, match="Unknown agent_id: 999"):
        ObservationBuilder(world).build(999)


def test_observation_excludes_other_people_and_rules() -> None:
    alice = make_world().get_person(1)
    world = WorldState(
        time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        people={
            1: alice,
            2: PersonWorldState(
                agent_id=2, location="private-bob-location", money=999.0, hunger=0.2
            ),
        },
    )
    data = ObservationBuilder(world).build(1).to_dict()
    assert "private-bob-location" not in str(data)
    assert "rules" not in data
    assert "people" not in data


@pytest.mark.parametrize("money,hunger", [(-1, 0.5), (1, -0.1), (1, 1.1)])
def test_person_state_validates_ranges(money: float, hunger: float) -> None:
    with pytest.raises(ValueError):
        PersonWorldState(agent_id=1, location="home", money=money, hunger=hunger)


def test_inventory_is_immutable_snapshot_and_keeps_zero_count() -> None:
    supplied_inventory = {"meal": 0}
    person = PersonWorldState(1, "restaurant", 80.0, 0.2, supplied_inventory)
    supplied_inventory["meal"] = 99
    assert person.inventory["meal"] == 0
    with pytest.raises(TypeError):
        person.inventory["meal"] = 1

    world = WorldState(
        time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        people={1: person},
    )
    observed = ObservationBuilder(world).build(1)
    assert observed.to_dict()["inventory"] == {"meal": 0}
    exposed = observed.to_dict()
    exposed["inventory"]["meal"] = 42
    assert ObservationBuilder(world).build(1).inventory["meal"] == 0


@pytest.mark.parametrize("inventory", [{"meal": -1}, {"meal": 1.5}, {"meal": True}])
def test_inventory_quantities_are_validated(inventory: dict) -> None:
    with pytest.raises(ValueError, match="inventory quantities"):
        PersonWorldState(1, "home", 100.0, 0.8, inventory)


@pytest.mark.parametrize("price,stock", [(-1.0, 1), (float("nan"), 1), (20.0, -1), (20.0, 1.2)])
def test_offer_validates_price_and_stock(price: float, stock: int) -> None:
    with pytest.raises(ValueError):
        OfferState("meal", price, stock)


def test_venue_is_single_source_and_local_observation_hides_remote_stock() -> None:
    supplied_venues = {"restaurant": {"meal": OfferState("meal", 20.0, 10)}}
    world = WorldState(
        time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        people={1: PersonWorldState(1, "home", 100.0, 0.8)},
        venues=supplied_venues,
    )
    supplied_venues["restaurant"].clear()
    assert world.get_offer("restaurant", "meal") == OfferState("meal", 20.0, 10)
    assert world.has_item("meal")
    assert world.get_offer("home", "meal") is None
    assert "offers" not in ObservationBuilder(world).build(1).to_dict()

    copied = world.venues
    copied["restaurant"].clear()
    assert world.offers_at("restaurant") == {"meal": OfferState("meal", 20.0, 10)}
    assert WorldState(world.time, world.people, world.locations, world.venues) == world

    restaurant_world = WorldState(
        world.time,
        {1: PersonWorldState(1, "restaurant", 100.0, 0.8)},
        world.locations,
        world.venues,
    )
    observed = ObservationBuilder(restaurant_world).build(1).to_dict()
    assert observed["offers"] == {"meal": {"price": 20.0, "available": True}}
    assert "stock" not in str(observed)


def test_immutable_snapshots_are_serializable_for_runtime_boundaries() -> None:
    world = WorldState(
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        {1: PersonWorldState(1, "restaurant", 80.0, 0.2, {"meal": 0})},
        venues={"restaurant": {"meal": OfferState("meal", 20.0, 9)}},
    )
    assert pickle.loads(pickle.dumps(world)) == world
    observation = ObservationBuilder(world).build(1)
    assert pickle.loads(pickle.dumps(observation)) == observation
