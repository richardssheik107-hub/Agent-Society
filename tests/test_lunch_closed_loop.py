"""Scripted, network-free decision-to-observation lunch loop acceptance."""

import asyncio
from datetime import datetime, timezone

import pytest

from social_sim.closed_loop import (
    ClosedLoopStep,
    LunchScenarioRunner,
    ScenarioIncompleteError,
)
from social_sim.decision import CompactDecisionService
from social_sim.decision.client import DecisionReply
from social_sim.events import DomainEvent, EventLog, EventType
from social_sim.decision import ActionType
from social_sim.world import ObservationBuilder, OfferState, PersonWorldState, WorldState


class ScriptedDecisionClient:
    def __init__(self, *replies: str) -> None:
        self.replies = replies
        self.call_count = 0
        self.user_prompts: list[str] = []

    async def complete(self, system_prompt: str, user_prompt: str) -> DecisionReply:
        self.user_prompts.append(user_prompt)
        raw = self.replies[self.call_count]
        self.call_count += 1
        return DecisionReply(raw)


def make_lunch_world() -> WorldState:
    return WorldState(
        time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        people={1: PersonWorldState(1, "home", 100.0, 0.8)},
        venues={"restaurant": {"meal": OfferState("meal", 20.0, 10)}},
    )


def test_scripted_lunch_closes_decision_rule_state_event_observation_loop() -> None:
    client = ScriptedDecisionClient(
        '{"action":"MOVE","target":"restaurant"}',
        '{"action":"BUY","target":"meal"}',
        '{"action":"EAT","target":"meal"}',
    )
    service = CompactDecisionService(client)
    log = EventLog()
    runner = LunchScenarioRunner(ClosedLoopStep(service, log))
    world0 = make_lunch_world()

    run = asyncio.run(runner.run(world0, 1, {"name": "Alice"}))

    assert len(run.steps) == client.call_count == service.decision_call_count == 3
    assert [step.proposal.action.value for step in run.steps] == ["MOVE", "BUY", "EAT"]
    assert all(step.outcome.allowed for step in run.steps)
    assert [step.outcome.reason_code for step in run.steps] == ["ACCEPTED"] * 3
    assert all(step.context_chars < 1000 for step in run.steps)
    assert all(step.prompt_chars < 1500 for step in run.steps)

    world1, world2, world3 = (step.world_after for step in run.steps)
    assert (world0.get_person(1).location, world0.get_person(1).money, world0.get_person(1).hunger) == (
        "home", 100.0, 0.8
    )
    assert (world1.get_person(1).location, world1.get_person(1).money, world1.get_person(1).hunger) == (
        "restaurant", 100.0, 0.8
    )
    assert world1.get_person(1).inventory.get("meal", 0) == 0
    assert world1.get_offer("restaurant", "meal").stock == 10
    assert (world2.get_person(1).location, world2.get_person(1).money, world2.get_person(1).hunger) == (
        "restaurant", 80.0, 0.8
    )
    assert world2.get_person(1).inventory["meal"] == 1
    assert world2.get_offer("restaurant", "meal").stock == 9
    assert (world3.get_person(1).location, world3.get_person(1).money, world3.get_person(1).hunger) == (
        "restaurant", 80.0, 0.2
    )
    assert world3.get_person(1).inventory["meal"] == 0
    assert world3.get_offer("restaurant", "meal").stock == 9
    assert world1.get_person(1).money == 100.0
    assert world2.get_person(1).hunger == 0.8
    assert run.world_after is world3

    assert [event.event_type for event in run.events] == [
        EventType.MOVED, EventType.PURCHASED, EventType.ATE
    ]
    assert [event.event_id for event in run.events] == [
        "event-000001", "event-000002", "event-000003"
    ]
    assert run.events == log.all()
    assert [event.compact() for event in log.recent_for_agent(1, 3)] == [
        "MOVED:restaurant", "PURCHASED:meal", "ATE:meal"
    ]

    final_observation = run.final_observation
    assert final_observation == ObservationBuilder(world3).build(1)
    assert final_observation.location == "restaurant"
    assert final_observation.money == 80.0
    assert final_observation.hunger == 0.2
    assert final_observation.inventory["meal"] == 0
    assert final_observation.offers["meal"]["price"] == 20.0
    assert final_observation.offers["meal"]["available"] is True

    assert '"loc":"restaurant"' in client.user_prompts[1]
    assert '"inv":{"meal":1}' in client.user_prompts[2]
    assert "MOVED:restaurant" in client.user_prompts[1]
    assert "PURCHASED:meal" in client.user_prompts[2]
    assert "UNKNOWN_DESTINATION" not in "".join(client.user_prompts)


def test_rejected_buy_at_home_returns_same_world_and_feedback() -> None:
    world = make_lunch_world()
    client = ScriptedDecisionClient('{"action":"BUY","target":"meal"}')
    log = EventLog()
    step = ClosedLoopStep(CompactDecisionService(client), log)

    result = asyncio.run(step.run(world, 1, {"name": "Alice"}))

    assert result.outcome.allowed is False
    assert result.outcome.reason_code == "NOT_AT_SELLER"
    assert result.outcome.new_world is world
    assert result.world_after is world
    assert result.outcome.effects == ()
    assert len(result.outcome.events) == 1
    assert result.outcome.events[0].event_type is EventType.ACTION_REJECTED
    assert result.outcome.events[0].compact() == "ACTION_REJECTED:NOT_AT_SELLER"
    assert log.all() == result.outcome.events
    observation_after = ObservationBuilder(result.world_after).build(1)
    assert (observation_after.location, observation_after.money, observation_after.hunger) == (
        "home", 100.0, 0.8
    )
    assert client.call_count == 1


def test_rejection_event_is_bounded_feedback_on_next_decision() -> None:
    world = make_lunch_world()
    client = ScriptedDecisionClient(
        '{"action":"BUY","target":"meal"}',
        '{"action":"MOVE","target":"restaurant"}',
    )
    log = EventLog()
    step = ClosedLoopStep(CompactDecisionService(client), log)

    async def run_two_steps():
        first = await step.run(world, 1, {"name": "Alice"})
        second = await step.run(first.world_after, 1, {"name": "Alice"})
        return first, second

    first, second = asyncio.run(run_two_steps())

    assert first.world_after is world
    assert second.observation_before.location == "home"
    assert second.observation_before.money == 100.0
    assert second.observation_before.hunger == 0.8
    assert "ACTION_REJECTED:NOT_AT_SELLER" in client.user_prompts[1]
    assert second.world_after.get_person(1).location == "restaurant"
    assert client.call_count == 2
    assert [event.event_type for event in log.all()] == [
        EventType.ACTION_REJECTED, EventType.MOVED
    ]


def test_scenario_has_five_decision_hard_cap_and_no_retry() -> None:
    with pytest.raises(ValueError, match="between 1 and 5"):
        LunchScenarioRunner(ClosedLoopStep(CompactDecisionService(ScriptedDecisionClient()), EventLog()), max_decisions=6)

    client = ScriptedDecisionClient(*(['{"action":"BUY","target":"meal"}'] * 2))
    log = EventLog()
    runner = LunchScenarioRunner(ClosedLoopStep(CompactDecisionService(client), log), max_decisions=2)
    with pytest.raises(ScenarioIncompleteError, match="within 2 decisions"):
        asyncio.run(runner.run(make_lunch_world(), 1, {"name": "Alice"}))
    assert client.call_count == 2
    assert len(log.all()) == 2


def test_run_result_events_exclude_preexisting_log_history() -> None:
    log = EventLog()
    log.append(
        DomainEvent(
            "event-000001", 2, EventType.MOVED, ActionType.MOVE,
            "park", True, "ACCEPTED"
        )
    )
    client = ScriptedDecisionClient(
        '{"action":"MOVE","target":"restaurant"}',
        '{"action":"BUY","target":"meal"}',
        '{"action":"EAT","target":"meal"}',
    )
    runner = LunchScenarioRunner(
        ClosedLoopStep(CompactDecisionService(client), log)
    )

    result = asyncio.run(runner.run(make_lunch_world(), 1, {"name": "Alice"}))

    assert [event.event_id for event in result.events] == [
        "event-000002", "event-000003", "event-000004"
    ]
    assert len(log.all()) == 4
    assert len(result.events) == 3


def test_already_satiated_world_stops_without_a_decision() -> None:
    initial = make_lunch_world()
    world = WorldState(
        time=initial.time,
        people={1: PersonWorldState(1, "home", 100.0, 0.2, {"meal": 0})},
        locations=initial.locations,
        venues=initial.venues,
    )
    client = ScriptedDecisionClient()
    log = EventLog()
    runner = LunchScenarioRunner(ClosedLoopStep(CompactDecisionService(client), log))

    result = asyncio.run(runner.run(world, 1, {"name": "Alice"}))

    assert result.world_after is world
    assert result.steps == ()
    assert result.events == ()
    assert result.final_observation.hunger == 0.2
    assert result.final_observation.inventory["meal"] == 0
    assert client.call_count == 0
    assert log.all() == ()
