"""Network-free acceptance tests for the Phase 6.5 real-runner path.

The real smoke changes only the decision client; these tests deliberately drive
the same ClosedLoopStep and LunchScenarioRunner with scripted model replies.
"""

import asyncio
import json
from datetime import datetime, timezone

import pytest

from social_sim.closed_loop import (
    ClosedLoopStep,
    LunchScenarioRunner,
    ScenarioIncompleteError,
)
from social_sim.decision import ActionType, CompactDecisionService
from social_sim.decision.client import DecisionReply
from social_sim.decision.parser import DecisionParseError
from social_sim.decision.prompt import MAX_CONTEXT_CHARS, MAX_PROMPT_CHARS
from social_sim.events import EventLog, EventType
from social_sim.world import OfferState, PersonWorldState, WorldState


ALL_ACTIONS = (
    ActionType.WAIT,
    ActionType.REST,
    ActionType.MOVE,
    ActionType.BUY,
    ActionType.EAT,
)
PROFILE = {"name": "Alice", "goal": "reduce hunger by obtaining and eating a meal"}


class ScriptedDecisionClient:
    """The same one-reply-per-call interface as the real provider adapter."""

    def __init__(self, *replies: str) -> None:
        self.replies = replies
        self.call_count = 0
        self.user_prompts: list[str] = []

    async def complete(self, system_prompt: str, user_prompt: str) -> DecisionReply:
        self.user_prompts.append(user_prompt)
        raw = self.replies[self.call_count]
        self.call_count += 1
        return DecisionReply(raw, input_tokens=11, output_tokens=7)


def initial_world() -> WorldState:
    return WorldState(
        time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        people={1: PersonWorldState(1, "home", 100.0, 0.8)},
        venues={"restaurant": {"meal": OfferState("meal", 20.0, 10)}},
    )


def context_from_prompt(user_prompt: str) -> dict[str, object]:
    return json.loads(user_prompt.split("Context:", 1)[1])


def test_real_runner_path_with_scripted_brain_is_one_step_at_a_time() -> None:
    client = ScriptedDecisionClient(
        '{"action":"MOVE","target":"restaurant"}',
        '{"action":"BUY","target":"meal"}',
        '{"action":"EAT","target":"meal"}',
    )
    service = CompactDecisionService(client)
    log = EventLog()
    callbacks = []
    runner = LunchScenarioRunner(ClosedLoopStep(service, log), max_decisions=5)

    result = asyncio.run(
        runner.run(
            initial_world(),
            1,
            PROFILE,
            available_actions=ALL_ACTIONS,
            on_step=lambda number, step: callbacks.append((number, step)),
        )
    )

    contexts = [context_from_prompt(prompt) for prompt in client.user_prompts]
    assert contexts[0]["p"]["goal"] == PROFILE["goal"]
    assert contexts[0]["a"] == [action.value for action in ALL_ACTIONS]
    assert contexts[0]["targets"] == ["home", "meal", "park", "restaurant"]
    assert contexts[1]["s"]["loc"] == "restaurant"
    assert contexts[1]["e"] == ["MOVED:restaurant"]
    assert contexts[2]["s"]["inv"]["meal"] == 1
    assert contexts[2]["e"] == ["MOVED:restaurant", "PURCHASED:meal"]
    assert len(result.steps) == client.call_count == service.decision_call_count == 3
    assert [number for number, _ in callbacks] == [1, 2, 3]
    assert [step for _, step in callbacks] == list(result.steps)
    assert [step.proposal.action for step in result.steps] == [
        ActionType.MOVE, ActionType.BUY, ActionType.EAT
    ]
    assert result.steps[1].observation_before.location == result.steps[0].world_after.get_person(1).location
    assert result.steps[2].observation_before.inventory["meal"] == result.steps[1].world_after.get_person(1).inventory["meal"]
    assert [event.event_type for event in result.events] == [
        EventType.MOVED, EventType.PURCHASED, EventType.ATE
    ]
    assert result.events == log.all()
    assert all(step.outcome.allowed for step in result.steps)
    assert all(0 < step.context_chars < MAX_CONTEXT_CHARS for step in result.steps)
    assert all(0 < step.prompt_chars < MAX_PROMPT_CHARS for step in result.steps)
    assert all(step.decision_latency_seconds >= 0 for step in result.steps)
    assert all((step.input_tokens, step.output_tokens) == (11, 7) for step in result.steps)
    assert [step.raw_output_chars for step in result.steps] == [
        len(reply) for reply in client.replies
    ]
    assert result.final_observation.location == "restaurant"
    assert result.final_observation.money == 80.0
    assert result.final_observation.hunger == 0.2
    assert result.final_observation.inventory["meal"] == 0
    assert result.world_after.get_offer("restaurant", "meal").stock == 9

    prompt_text = " ".join(client.user_prompts)
    for forbidden in (
        "BUY requires restaurant",
        "BUY requires money",
        "EAT requires inventory",
        "NOT_AT_SELLER",
        "OUT_OF_STOCK",
        "first move",
        "then buy",
    ):
        assert forbidden not in prompt_text


def test_rejected_action_is_feedback_and_not_a_retry() -> None:
    world = initial_world()
    client = ScriptedDecisionClient(
        '{"action":"BUY","target":"meal"}',
        '{"action":"MOVE","target":"restaurant"}',
        '{"action":"BUY","target":"meal"}',
        '{"action":"EAT","target":"meal"}',
    )
    service = CompactDecisionService(client)
    log = EventLog()
    result = asyncio.run(
        LunchScenarioRunner(ClosedLoopStep(service, log), max_decisions=5).run(
            world, 1, PROFILE, available_actions=ALL_ACTIONS
        )
    )

    contexts = [context_from_prompt(prompt) for prompt in client.user_prompts]
    assert result.steps[0].outcome.allowed is False
    assert result.steps[0].outcome.reason_code == "NOT_AT_SELLER"
    assert result.steps[0].world_after is world
    assert result.events[0].event_type is EventType.ACTION_REJECTED
    assert contexts[1]["s"]["loc"] == "home"
    assert "ACTION_REJECTED:NOT_AT_SELLER" in contexts[1]["e"]
    assert contexts[2]["s"]["loc"] == "restaurant"
    assert contexts[3]["s"]["inv"]["meal"] == 1
    assert result.final_observation.hunger == 0.2
    assert len(result.steps) == client.call_count == service.decision_call_count == 4


def test_five_unsupported_actions_stop_at_budget_without_retry() -> None:
    client = ScriptedDecisionClient(*(['{"action":"REST","target":null}'] * 5))
    service = CompactDecisionService(client)
    log = EventLog()
    callbacks = []
    runner = LunchScenarioRunner(ClosedLoopStep(service, log), max_decisions=5)

    with pytest.raises(ScenarioIncompleteError, match="within 5 decisions"):
        asyncio.run(
            runner.run(
                initial_world(), 1, PROFILE,
                available_actions=ALL_ACTIONS,
                on_step=lambda number, step: callbacks.append((number, step)),
            )
        )

    assert [number for number, _ in callbacks] == [1, 2, 3, 4, 5]
    assert client.call_count == service.decision_call_count == 5
    assert len(log.all()) == 5
    assert all(not step.outcome.allowed for _, step in callbacks)
    assert all(step.outcome.reason_code == "UNSUPPORTED_ACTION" for _, step in callbacks)
    assert all(event.event_type is EventType.ACTION_REJECTED for event in log.all())
    assert all(
        len(context_from_prompt(prompt).get("e", [])) <= 3
        for prompt in client.user_prompts
    )


@pytest.mark.parametrize(
    "raw_reply",
    ["not JSON", '{"action":"WORK","target":null}'],
)
def test_invalid_model_output_stops_without_repair_or_execution(raw_reply: str) -> None:
    world = initial_world()
    client = ScriptedDecisionClient(raw_reply)
    service = CompactDecisionService(client)
    log = EventLog()
    callbacks = []
    runner = LunchScenarioRunner(ClosedLoopStep(service, log), max_decisions=5)

    with pytest.raises(DecisionParseError):
        asyncio.run(
            runner.run(
                world, 1, PROFILE,
                available_actions=ALL_ACTIONS,
                on_step=lambda number, step: callbacks.append((number, step)),
            )
        )

    assert client.call_count == service.decision_call_count == 1
    assert len(client.user_prompts) == 1
    assert callbacks == []
    assert log.all() == ()
    assert (world.get_person(1).location, world.get_person(1).money, world.get_person(1).hunger) == (
        "home", 100.0, 0.8
    )


def test_provider_timeout_stops_after_one_call_without_a_rule_event() -> None:
    class TimeoutClient:
        def __init__(self) -> None:
            self.call_count = 0

        async def complete(self, system_prompt: str, user_prompt: str) -> DecisionReply:
            self.call_count += 1
            raise TimeoutError("simulated provider timeout")

    client = TimeoutClient()
    service = CompactDecisionService(client)
    log = EventLog()
    world = initial_world()
    runner = LunchScenarioRunner(ClosedLoopStep(service, log), max_decisions=5)

    with pytest.raises(TimeoutError, match="simulated provider timeout"):
        asyncio.run(runner.run(world, 1, PROFILE, available_actions=ALL_ACTIONS))

    assert client.call_count == service.decision_call_count == 1
    assert log.all() == ()
    assert world.get_person(1).location == "home"
