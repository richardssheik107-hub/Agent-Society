"""Deterministic selection of compact event history for context ablations.

Policies select already-compact events. Serialization, field bounds, and the
total character budget remain the responsibility of :class:`ContextCompiler`.
The input sequence is chronological (oldest first), and selected events are
returned in the same chronological order.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from social_sim.world.observation import LocalObservation


class ContextPolicy(Protocol):
    """Select at most three compact events without changing other context."""

    name: str

    def select_events(
        self,
        events: Sequence[str],
        observation: LocalObservation,
        goal: str,
    ) -> list[str]: ...


class C0StatePolicy:
    """Current state only; no event history."""

    name = "C0_state"

    def select_events(
        self,
        events: Sequence[str],
        observation: LocalObservation,
        goal: str,
    ) -> list[str]:
        return []


class C1LastPolicy:
    """Keep the most recent compact event, if any."""

    name = "C1_last"

    def select_events(
        self,
        events: Sequence[str],
        observation: LocalObservation,
        goal: str,
    ) -> list[str]:
        return list(events[-1:])


class C3Recent3Policy:
    """Preserve the Phase 7 baseline: the last three events in order."""

    name = "C3_recent3"

    def select_events(
        self,
        events: Sequence[str],
        observation: LocalObservation,
        goal: str,
    ) -> list[str]:
        return list(events[-3:])


class CRRelevantPolicy:
    """Prefer recent rejection feedback, then recent state-changing events.

    Ranking is newest-first within each category. Once the three event slots
    are chosen, restore chronological order for the model-facing history.
    """

    name = "CR_relevant"
    MAX_EVENTS = 3

    def select_events(
        self,
        events: Sequence[str],
        observation: LocalObservation,
        goal: str,
    ) -> list[str]:
        newest_first = range(len(events) - 1, -1, -1)
        rejected = [
            index for index in newest_first
            if events[index].startswith("ACTION_REJECTED:")
        ]
        successful = [
            index for index in newest_first
            if not events[index].startswith("ACTION_REJECTED:")
        ]
        selected = sorted((rejected + successful)[: self.MAX_EVENTS])
        return [events[index] for index in selected]


__all__ = [
    "ContextPolicy",
    "C0StatePolicy",
    "C1LastPolicy",
    "C3Recent3Policy",
    "CRRelevantPolicy",
]
