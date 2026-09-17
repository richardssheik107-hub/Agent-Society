"""Immutable, opt-in Research A2.0 experimental behavior profiles."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from social_sim.decision.models import ActionType

from .runner import DAILY_ACTIONS
from .time import ACTIVITY_DURATIONS_MINUTES, TICK_MINUTES


SOURCE = Path(__file__).resolve().parents[3] / "config/experimental/neutral_day_calibrated_v1.yaml"
CORE5 = ("SLEEP", "WORK", "EAT", "LEISURE", "MOVE")
CORE7 = (*CORE5, "PERSONAL_CARE", "CHORES")


def quantize_duration_to_tick(empirical_minutes: int, tick_minutes: int = TICK_MINUTES) -> int:
    """Nearest positive tick, ties away from zero (not bankers rounding)."""
    if (isinstance(empirical_minutes, bool) or not isinstance(empirical_minutes, int)
            or empirical_minutes <= 0 or isinstance(tick_minutes, bool)
            or not isinstance(tick_minutes, int) or tick_minutes <= 0):
        raise ValueError("durations and tick must be positive integers")
    return ((2 * empirical_minutes + tick_minutes) // (2 * tick_minutes)) * tick_minutes


@dataclass(frozen=True)
class ExperimentBehaviorProfile:
    name: str
    ontology: tuple[str, ...]
    empirical_minutes: dict[str, int]
    duration_overrides: dict[str, int]
    experimental_actions_enabled: bool
    behavior_support_policy: str
    source_profile: str

    @property
    def available_actions(self) -> tuple[ActionType, ...]:
        if self.experimental_actions_enabled:
            return (*DAILY_ACTIONS, ActionType.PERSONAL_CARE, ActionType.CHORES)
        return DAILY_ACTIONS

    def snapshot(self) -> dict[str, object]:
        return {
            "name": self.name, "ontology": list(self.ontology),
            "empirical_minutes": dict(self.empirical_minutes),
            "duration_overrides": dict(self.duration_overrides),
            "experimental_actions_enabled": self.experimental_actions_enabled,
            "behavior_support_policy": self.behavior_support_policy,
            "source_profile": self.source_profile,
            "available_actions": [action.value for action in self.available_actions],
        }

    @property
    def profile_hash(self) -> str:
        return hashlib.sha256(json.dumps(self.snapshot(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load_experiment_profiles(source: Path = SOURCE) -> tuple[ExperimentBehaviorProfile, ...]:
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    candidates = data["duration_candidates"]
    if tuple(data["ontology"]["activities"]) != CORE7:
        raise ValueError("B1.2 ontology differs from frozen A2.0 contract")
    original = {action.value: duration for action, duration in ACTIVITY_DURATIONS_MINUTES.items()}
    calibrated = {
        action: quantize_duration_to_tick(candidates[action])
        for action in ("SLEEP", "WORK", "LEISURE")
    }
    extended = {
        **calibrated,
        **{action: quantize_duration_to_tick(candidates[action])
           for action in ("PERSONAL_CARE", "CHORES")},
    }
    return (
        ExperimentBehaviorProfile("G0_ORIGINAL", CORE5, dict(original), dict(original),
                                  False, "B0_NONE", "frozen-production-defaults@9139744"),
        ExperimentBehaviorProfile("G1_DURATION", CORE5,
                                  {action: candidates[action] for action in calibrated},
                                  calibrated, False, "B0_NONE", str(source.relative_to(source.parents[2]))),
        ExperimentBehaviorProfile("G2_CORE7", CORE7,
                                  {action: candidates[action] for action in extended},
                                  extended, True, "B0_NONE", str(source.relative_to(source.parents[2]))),
    )
