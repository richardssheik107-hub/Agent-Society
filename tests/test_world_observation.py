"""Fast local tests; no AgentSociety runtime or LLM request is started."""

from datetime import datetime, timezone

import pytest

from social_sim.world import ObservationBuilder, PersonWorldState, WorldState
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
