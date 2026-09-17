"""Event selection policies isolate history as the Phase 8A variable."""

from __future__ import annotations

import pytest

from social_sim.context import (
    C0StatePolicy,
    C1LastPolicy,
    C3Recent3Policy,
    CRRelevantPolicy,
)
from social_sim.world.observation import LocalObservation


@pytest.fixture
def observation() -> LocalObservation:
    return LocalObservation(1, "2026-01-01T00:00:00", "home", 100.0, 0.8)


GOAL = "reduce hunger by obtaining and eating a meal"
HISTORY = (
    "ACTION_REJECTED:NOT_AT_SELLER",
    "MOVED:park",
    "MOVED:home",
    "MOVED:park",
    "MOVED:home",
)


def test_policy_names_are_stable() -> None:
    assert [
        C0StatePolicy().name,
        C1LastPolicy().name,
        C3Recent3Policy().name,
        CRRelevantPolicy().name,
    ] == ["C0_state", "C1_last", "C3_recent3", "CR_relevant"]


@pytest.mark.parametrize("history", [(), HISTORY])
def test_c0_always_selects_no_events(
    history: tuple[str, ...], observation: LocalObservation
) -> None:
    assert C0StatePolicy().select_events(history, observation, GOAL) == []


def test_c1_keeps_only_last_event(observation: LocalObservation) -> None:
    policy = C1LastPolicy()
    assert policy.select_events((), observation, GOAL) == []
    assert policy.select_events(HISTORY, observation, GOAL) == ["MOVED:home"]


def test_c3_matches_phase7_last_three_in_original_order(
    observation: LocalObservation,
) -> None:
    policy = C3Recent3Policy()
    assert policy.select_events((), observation, GOAL) == []
    assert policy.select_events(HISTORY[:2], observation, GOAL) == list(HISTORY[:2])
    assert policy.select_events(HISTORY, observation, GOAL) == list(HISTORY[-3:])


def test_cr_prioritizes_older_rejection_over_recent_moves(
    observation: LocalObservation,
) -> None:
    assert CRRelevantPolicy().select_events(HISTORY, observation, GOAL) == [
        "ACTION_REJECTED:NOT_AT_SELLER",
        "MOVED:park",
        "MOVED:home",
    ]


def test_s2_buried_rejection_distinguishes_policies(
    observation: LocalObservation,
) -> None:
    c1 = C1LastPolicy().select_events(HISTORY, observation, GOAL)
    c3 = C3Recent3Policy().select_events(HISTORY, observation, GOAL)
    cr = CRRelevantPolicy().select_events(HISTORY, observation, GOAL)
    assert "ACTION_REJECTED:NOT_AT_SELLER" not in c1
    assert "ACTION_REJECTED:NOT_AT_SELLER" not in c3
    assert "ACTION_REJECTED:NOT_AT_SELLER" in cr


def test_cr_keeps_at_most_three_and_prefers_newest_rejections(
    observation: LocalObservation,
) -> None:
    events = (
        "ACTION_REJECTED:OLD",
        "MOVED:park",
        "ACTION_REJECTED:MIDDLE",
        "MOVED:home",
        "ACTION_REJECTED:NEWEST",
        "PURCHASED:meal",
        "ACTION_REJECTED:LAST",
    )
    assert CRRelevantPolicy().select_events(events, observation, GOAL) == [
        "ACTION_REJECTED:MIDDLE",
        "ACTION_REJECTED:NEWEST",
        "ACTION_REJECTED:LAST",
    ]


def test_cr_selection_is_deterministic_and_preserves_input(
    observation: LocalObservation,
) -> None:
    events = list(HISTORY)
    policy = CRRelevantPolicy()
    first = policy.select_events(events, observation, GOAL)
    for _ in range(10):
        assert policy.select_events(events, observation, GOAL) == first
    assert events == list(HISTORY)


@pytest.mark.parametrize(
    "policy", [C0StatePolicy(), C1LastPolicy(), C3Recent3Policy(), CRRelevantPolicy()]
)
def test_empty_history_is_supported(policy: object, observation: LocalObservation) -> None:
    assert policy.select_events((), observation, GOAL) == []  # type: ignore[attr-defined]
