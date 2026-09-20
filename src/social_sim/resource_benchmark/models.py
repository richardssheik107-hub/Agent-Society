"""Immutable Q4 resource truth, projections, and fixed-state contracts."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from social_sim.decision.models import ActionType


class ResourceLevel(str, Enum):
    R8 = "R8"
    R16 = "R16"
    R32 = "R32"
    R64 = "R64"


@dataclass(frozen=True)
class ResourceProjection:
    level: ResourceLevel
    values: Mapping[str, float]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))


@dataclass(frozen=True)
class ResourceTruth:
    """The complete objective resource state shared by every arm."""

    values: Mapping[str, float]

    def __post_init__(self) -> None:
        from .schema import ALL_RESOURCE_FIELDS

        if set(self.values) != set(ALL_RESOURCE_FIELDS):
            missing = sorted(set(ALL_RESOURCE_FIELDS) - set(self.values))
            extra = sorted(set(self.values) - set(ALL_RESOURCE_FIELDS))
            raise ValueError(f"resource truth schema mismatch missing={missing} extra={extra}")
        normalized: dict[str, float] = {}
        for name in ALL_RESOURCE_FIELDS:
            value = self.values[name]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"resource value must be numeric: {name}")
            number = float(value)
            if not math.isfinite(number) or not 0.0 <= number <= 1.0:
                raise ValueError(f"resource value must be in [0, 1]: {name}")
            normalized[name] = number
        object.__setattr__(self, "values", MappingProxyType(normalized))

    def project(self, level: ResourceLevel | str) -> ResourceProjection:
        from .schema import resource_fields

        level = ResourceLevel(level)
        return ResourceProjection(level, {name: self.values[name] for name in resource_fields(level)})


@dataclass(frozen=True)
class ResourceScenario:
    """One fixed-state decision with identical world truth across conditions."""

    scenario_id: str
    family: str
    time: str
    location: str
    previous_activity: str | None
    recent_events: tuple[str, ...]
    behavior_prior: tuple[str, ...]
    world_facts: Mapping[str, object]
    truth: ResourceTruth
    acceptable_action_set: tuple[ActionType, ...]
    critical_resources: tuple[str, ...]
    available_actions: tuple[ActionType, ...]
    available_targets: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.scenario_id or not self.scenario_id.replace("_", "").isalnum():
            raise ValueError("scenario_id must be a stable identifier")
        if not self.family or not self.time or not self.location:
            raise ValueError("scenario identity fields are required")
        if not self.acceptable_action_set:
            raise ValueError("acceptable_action_set must not be empty")
        if not self.critical_resources:
            raise ValueError("critical_resources must not be empty")
        if any(name not in self.truth.values for name in self.critical_resources):
            raise ValueError("critical resource is absent from truth")
        if len(set(self.available_actions)) != len(self.available_actions):
            raise ValueError("available actions must be unique")
        if not set(self.acceptable_action_set).issubset(set(self.available_actions)):
            raise ValueError("acceptable actions must be available")
        object.__setattr__(self, "world_facts", MappingProxyType(dict(self.world_facts)))
        object.__setattr__(self, "recent_events", tuple(self.recent_events))
        object.__setattr__(self, "behavior_prior", tuple(self.behavior_prior))
        object.__setattr__(self, "acceptable_action_set", tuple(self.acceptable_action_set))
        object.__setattr__(self, "critical_resources", tuple(self.critical_resources))
        object.__setattr__(self, "available_actions", tuple(self.available_actions))
        object.__setattr__(self, "available_targets", tuple(self.available_targets))


@dataclass(frozen=True)
class ScheduleEntry:
    case_id: str
    scenario_id: str
    repetition: int
    level: ResourceLevel

    def __post_init__(self) -> None:
        if self.repetition <= 0:
            raise ValueError("repetition must be positive")


@dataclass(frozen=True)
class HeldoutActionStats:
    action_share: float
    rank: int | None
    top3_match: bool


@dataclass(frozen=True)
class PilotConfig:
    phase: str
    attempt_id: str = "q4_attempt_1"
    repetitions: int = 2
    max_scenarios: int | None = None
    timeout_seconds: float = 60.0

    def __post_init__(self) -> None:
        if self.phase not in ("smoke", "full"):
            raise ValueError("phase must be smoke or full")
        if self.repetitions <= 0:
            raise ValueError("repetitions must be positive")
        if self.max_scenarios is not None and self.max_scenarios <= 0:
            raise ValueError("max_scenarios must be positive")
        if not self.attempt_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in self.attempt_id):
            raise ValueError("attempt_id must be artifact-safe")
