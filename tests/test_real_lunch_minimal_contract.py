"""Offline contract checks for the bounded real-lunch runner."""

import asyncio
import json
from datetime import datetime, timezone

from social_sim.closed_loop import ClosedLoopStep, LunchScenarioRunner
from social_sim.decision import ActionType, CompactDecisionService
from social_sim.decision.client import DecisionReply
from social_sim.events import EventLog, EventType
from social_sim.world import ObservationBuilder, OfferState, PersonWorldState, WorldState


GOAL = "reduce hunger by obtaining and eating a meal"
AVAILABLE_ACTIONS = (ActionType.MOVE, ActionType.BUY, ActionType.EAT)
PROFILE = {"name": "Alice", "goal": GOAL}


class ScriptedDecisionClient:
    def __init__(self, *replies: str) -> None:
        self.replies = replies
        self.calls: list[tuple[str, str]] = []

    async def complete(self, system_prompt: str, user_prompt: str) -> DecisionReply:
        call_index = len(self.calls)
        assert call_index < len(self.replies), "runner made an unexpected extra decision"
        self.calls.append((system_prompt, user_prompt))
        return DecisionReply(self.replies[call_index])


def initial_world() -> WorldState:
    return WorldState(
        time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        people={1: PersonWorldState(1, "home", 100.0, 0.8)},
        venues={"restaurant": {"meal": OfferState("meal", 20.0, 10)}},
    )


def prompt_context(call: tuple[str, str]) -> dict[str, object]:
    return json.loads(call[1].split("Context:", 1)[1])


def assert_prompts_are_goal_based(client: ScriptedDecisionClient) -> None:
    for call in client.calls:
        context = prompt_context(call)
        assert context["p"]["goal"] == GOAL
        assert context["a"] == ["MOVE", "BUY", "EAT"]
        prompt = " ".join(call).lower()
        for scripted_order in (
            "first move",
            "then buy",
            "then eat",
            "move -> buy",
            "buy -> eat",
        ):
            assert scripted_order not in prompt


def test_move_buy_eat_uses_updated_world_and_recent_events() -> None:
    world = initial_world()
    client = ScriptedDecisionClient(
        '{"action":"MOVE","target":"restaurant"}',
        '{"action":"BUY","target":"meal"}',
        '{"action":"EAT","target":"meal"}',
    )
    service = CompactDecisionService(client)
    log = EventLog()
    decision_counts: list[tuple[int, int, int]] = []
    runner = LunchScenarioRunner(ClosedLoopStep(service, log), max_decisions=5)

    result = asyncio.run(
        runner.run(
            world,
            1,
            PROFILE,
            available_actions=AVAILABLE_ACTIONS,
            on_step=lambda number, _: decision_counts.append(
                (number, len(client.calls), service.decision_call_count)
            ),
        )
    )

    assert_prompts_are_goal_based(client)
    contexts = [prompt_context(call) for call in client.calls]
    assert contexts[0]["s"]["loc"] == "home"
    assert contexts[1]["s"]["loc"] == "restaurant"
    assert contexts[1]["e"] == ["MOVED:restaurant"]
    assert contexts[2]["s"]["inv"]["meal"] == 1
    assert contexts[2]["e"] == ["MOVED:restaurant", "PURCHASED:meal"]
    assert decision_counts == [(1, 1, 1), (2, 2, 2), (3, 3, 3)]
    assert len(result.steps) == len(client.calls) == service.decision_call_count == 3
    assert [step.proposal.action for step in result.steps] == list(AVAILABLE_ACTIONS)
    assert all(step.outcome.allowed for step in result.steps)
    assert [step.observation_before for step in result.steps] == [
        ObservationBuilder(previous).build(1)
        for previous in (world, result.steps[0].world_after, result.steps[1].world_after)
    ]
    assert [event.event_type for event in result.events] == [
        EventType.MOVED, EventType.PURCHASED, EventType.ATE
    ]
    assert result.events == log.all()
    assert result.final_observation == ObservationBuilder(result.world_after).build(1)
    assert result.final_observation.location == "restaurant"
    assert result.final_observation.money == 80.0
    assert result.final_observation.hunger == 0.2
    assert result.final_observation.inventory["meal"] == 0
    assert result.world_after.get_offer("restaurant", "meal").stock == 9


def test_rejected_buy_at_home_feeds_back_before_next_move() -> None:
    world = initial_world()
    client = ScriptedDecisionClient(
        '{"action":"BUY","target":"meal"}',
        '{"action":"MOVE","target":"restaurant"}',
        '{"action":"BUY","target":"meal"}',
        '{"action":"EAT","target":"meal"}',
    )
    service = CompactDecisionService(client)
    log = EventLog()
    decision_counts: list[tuple[int, int, int]] = []

    result = asyncio.run(
        LunchScenarioRunner(ClosedLoopStep(service, log), max_decisions=5).run(
            world,
            1,
            PROFILE,
            available_actions=AVAILABLE_ACTIONS,
            on_step=lambda number, _: decision_counts.append(
                (number, len(client.calls), service.decision_call_count)
            ),
        )
    )

    assert_prompts_are_goal_based(client)
    contexts = [prompt_context(call) for call in client.calls]
    rejected = result.steps[0]
    assert rejected.proposal.action is ActionType.BUY
    assert not rejected.outcome.allowed
    assert rejected.outcome.reason_code == "NOT_AT_SELLER"
    assert rejected.world_after is world
    assert result.events[0].event_type is EventType.ACTION_REJECTED
    assert result.events[0].compact() == "ACTION_REJECTED:NOT_AT_SELLER"
    assert contexts[1]["s"]["loc"] == "home"
    assert contexts[1]["e"] == ["ACTION_REJECTED:NOT_AT_SELLER"]
    assert result.steps[1].proposal.action is ActionType.MOVE
    assert result.steps[1].observation_before == ObservationBuilder(world).build(1)
    assert contexts[2]["s"]["loc"] == "restaurant"
    assert contexts[2]["e"] == [
        "ACTION_REJECTED:NOT_AT_SELLER", "MOVED:restaurant"
    ]
    assert contexts[3]["s"]["inv"]["meal"] == 1
    assert decision_counts == [(1, 1, 1), (2, 2, 2), (3, 3, 3), (4, 4, 4)]
    assert len(result.steps) == len(client.calls) == service.decision_call_count == 4
    assert result.events == log.all()
    assert result.final_observation == ObservationBuilder(result.world_after).build(1)
    assert (
        result.final_observation.location,
        result.final_observation.money,
        result.final_observation.hunger,
        result.final_observation.inventory["meal"],
    ) == ("restaurant", 80.0, 0.2, 0)
    assert result.world_after.get_offer("restaurant", "meal").stock == 9
