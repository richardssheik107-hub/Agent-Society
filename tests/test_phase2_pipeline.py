"""The complete compact proposal path cannot mutate the world."""

import asyncio
from datetime import datetime, timezone

from social_sim.decision import CompactDecisionService, FakeDecisionClient
from social_sim.world import ObservationBuilder, PersonWorldState, WorldState


def test_world_to_single_call_proposal_without_execution() -> None:
    world = WorldState(
        time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        people={
            1: PersonWorldState(
                agent_id=1, location="home", money=100.0, hunger=0.8
            )
        },
    )
    before = WorldState(time=world.time, people=world.people)
    observation = ObservationBuilder(world).build(1)
    client = FakeDecisionClient('{"action":"MOVE","target":"park"}')
    service = CompactDecisionService(client)

    result = asyncio.run(
        service.decide(
            {"name": "Alice"}, observation,
            available_actions=["WAIT", "REST", "MOVE"],
            available_targets=["park", "restaurant"],
        )
    )

    assert result.proposal.action.value == "MOVE"
    assert result.proposal.target == "park"
    assert client.call_count == service.decision_call_count == 1
    assert world == before
    assert world.get_person(1).location == "home"
