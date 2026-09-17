"""Phase 8A policies change only event content in the compact decision prompt."""

from __future__ import annotations

import asyncio
import json

import pytest

from social_sim.context import (
    C0StatePolicy,
    C1LastPolicy,
    C3Recent3Policy,
    CRRelevantPolicy,
    ContextCompiler,
    ContextPolicy,
)
from social_sim.decision import ActionType, CompactDecisionService
from social_sim.decision.client import FakeDecisionClient
from social_sim.world.observation import LocalObservation


PROFILE = {"name": "Alice", "goal": "reduce hunger by obtaining and eating a meal"}
ACTIONS = (ActionType.MOVE, ActionType.BUY, ActionType.EAT)
TARGETS = ("home", "park", "restaurant", "meal")
HISTORY = (
    "ACTION_REJECTED:NOT_AT_SELLER",
    "MOVED:park",
    "MOVED:home",
    "MOVED:park",
    "MOVED:home",
)
POLICIES = (C0StatePolicy(), C1LastPolicy(), C3Recent3Policy(), CRRelevantPolicy())


@pytest.fixture
def observation() -> LocalObservation:
    return LocalObservation(1, "2026-01-01T00:00:00", "home", 100.0, 0.8)


def _decide(policy: ContextPolicy, observation: LocalObservation):
    client = FakeDecisionClient('{"action":"MOVE","target":"restaurant"}')
    service = CompactDecisionService(
        client,
        compiler=ContextCompiler(max_chars=2000),
        context_policy=policy,
    )
    result = asyncio.run(
        service.decide(
            PROFILE,
            observation,
            available_actions=ACTIONS,
            available_targets=TARGETS,
            recent_events=HISTORY,
        )
    )
    assert client.call_count == service.decision_call_count == 1
    assert result.provider_request_count == 0
    return result


def test_same_observation_differs_only_in_event_list(
    observation: LocalObservation,
) -> None:
    results = {policy.name: _decide(policy, observation) for policy in POLICIES}
    contexts = {name: json.loads(result.context) for name, result in results.items()}
    assert all("e" in context for context in contexts.values())
    assert contexts["C0_state"]["e"] == []
    assert contexts["C1_last"]["e"] == ["MOVED:home"]
    assert contexts["C3_recent3"]["e"] == list(HISTORY[-3:])
    assert contexts["CR_relevant"]["e"] == [
        "ACTION_REJECTED:NOT_AT_SELLER", "MOVED:park", "MOVED:home"
    ]
    without_events = [
        {key: value for key, value in context.items() if key != "e"}
        for context in contexts.values()
    ]
    assert all(context == without_events[0] for context in without_events[1:])
    assert len({result.system_prompt for result in results.values()}) == 1
    for result in results.values():
        assert result.user_prompt.split("Context:", 1)[0] == next(
            iter(results.values())
        ).user_prompt.split("Context:", 1)[0]


def test_c3_serialization_exactly_matches_phase7_last_three(
    observation: LocalObservation,
) -> None:
    result = _decide(C3Recent3Policy(), observation)
    baseline = ContextCompiler(max_chars=2000).compile(
        PROFILE,
        observation,
        available_actions=[action.value for action in ACTIONS],
        available_targets=TARGETS,
        events=HISTORY[-3:],
    )
    assert result.context == baseline


@pytest.mark.parametrize("policy", POLICIES, ids=lambda policy: policy.name)
def test_each_policy_stays_within_existing_context_and_prompt_budgets(
    policy: ContextPolicy, observation: LocalObservation,
) -> None:
    result = _decide(policy, observation)
    assert result.context_chars == len(result.context) < 2000
    assert result.prompt_chars == len(result.system_prompt) + len(result.user_prompt) < 3000
