"""Research A1 tick/episode records layered over the Phase 7 decision trajectory."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from social_sim.evaluation.models import EpisodeResult


DAILY_SCHEMA_VERSION = "0.5"


class DailyTerminationReason(str, Enum):
    DAY_END = "DAY_END"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    INVALID_MODEL_OUTPUT = "INVALID_MODEL_OUTPUT"
    MAX_DECISIONS = "MAX_DECISIONS"
    BEHAVIOR_LOOP = "BEHAVIOR_LOOP"
    ARCHITECTURE_ERROR = "ARCHITECTURE_ERROR"
    TIMEOUT = "TIMEOUT"


class DayOutcome(str, Enum):
    """Completion is orthogonal to the reason a partial day stopped."""

    DAY_COMPLETED = "DAY_COMPLETED"
    DAY_TRUNCATED_PROVIDER = "DAY_TRUNCATED_PROVIDER"
    DAY_TRUNCATED_MODEL_OUTPUT = "DAY_TRUNCATED_MODEL_OUTPUT"
    DAY_TRUNCATED_ARCHITECTURE = "DAY_TRUNCATED_ARCHITECTURE"
    DAY_TRUNCATED_BEHAVIOR = "DAY_TRUNCATED_BEHAVIOR"


@dataclass(frozen=True)
class DailyTickRecord:
    """One deterministic 15-minute interval, whether or not it used a model."""

    tick_index: int
    simulation_time: str
    end_time: str
    world_before: dict[str, object]
    world_after_decision: dict[str, object]
    world_after: dict[str, object]
    decision_step_index: int | None
    attempted_action: str | None
    attempted_target: str | None
    action_accepted: bool | None
    rejection_reason: str | None
    active_activity: str | None
    completed_activities: tuple[str, ...] = ()
    completion_events: tuple[dict[str, object], ...] = ()
    trigger_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": DAILY_SCHEMA_VERSION,
            "tick_index": self.tick_index,
            "simulation_time": self.simulation_time,
            "end_time": self.end_time,
            "world_before": self.world_before,
            "world_after_decision": self.world_after_decision,
            "world_after": self.world_after,
            "decision_step_index": self.decision_step_index,
            "attempted_action": self.attempted_action,
            "attempted_target": self.attempted_target,
            "action_accepted": self.action_accepted,
            "rejection_reason": self.rejection_reason,
            "active_activity": self.active_activity,
            "completed_activities": list(self.completed_activities),
            "completion_events": [dict(event) for event in self.completion_events],
            "trigger_reason": self.trigger_reason,
        }


@dataclass(frozen=True)
class DailyEpisodeResult:
    """Daily-only metrics plus a reference to the unmodified decision record path."""

    episode_id: str
    termination_reason: DailyTerminationReason
    trajectory: EpisodeResult
    ticks: tuple[DailyTickRecord, ...]
    idle_metrics: dict[str, object]
    activity_metrics: dict[str, object]
    failure_taxonomy: tuple[str, ...]
    decision_count: int
    provider_request_count: int
    valid_activity_count: int
    unique_activity_types: int
    activity_counts: dict[str, int]
    simulated_minutes: int
    day_outcome: DayOutcome
    day_completed: bool
    observed_minutes: int
    observed_ticks: int
    truncation_reason: str | None
    provider_failures: tuple[dict[str, object], ...]
    output_failures: tuple[dict[str, object], ...]
    behavior_metrics_valid: bool
    full_day_behavior_metrics: dict[str, object] | None
    partial_window_metrics: dict[str, object] | None

    def to_dict(self) -> dict[str, Any]:
        record = {
            "schema_version": DAILY_SCHEMA_VERSION,
            "experiment_type": "neutral_day_idle_benchmark",
            "episode_id": self.episode_id,
            "termination_reason": self.termination_reason.value,
            "trajectory_episode_id": self.trajectory.episode_id,
            "decision_count": self.decision_count,
            "provider_request_count": self.provider_request_count,
            "valid_activity_count": self.valid_activity_count,
            "unique_activity_types": self.unique_activity_types,
            "activity_counts": dict(self.activity_counts),
            "simulated_minutes": self.simulated_minutes,
            "day_outcome": self.day_outcome.value,
            "day_completed": self.day_completed,
            "observed_minutes": self.observed_minutes,
            "observed_ticks": self.observed_ticks,
            "truncation_reason": self.truncation_reason,
            "provider_failures": [dict(failure) for failure in self.provider_failures],
            "output_failures": [dict(failure) for failure in self.output_failures],
            "behavior_metrics_valid": self.behavior_metrics_valid,
            "full_day_behavior_metrics": (
                dict(self.full_day_behavior_metrics)
                if self.full_day_behavior_metrics is not None else None
            ),
            "partial_window_metrics": (
                dict(self.partial_window_metrics)
                if self.partial_window_metrics is not None else None
            ),
            "failure_taxonomy": list(self.failure_taxonomy),
            "ticks": [tick.to_dict() for tick in self.ticks],
        }
        # Legacy fields remain on complete-day records only. On a truncated
        # episode they would be easy to mistake for full-day measurements.
        if self.day_completed:
            record.update(
                valid_activity_count=self.valid_activity_count,
                unique_activity_types=self.unique_activity_types,
                activity_counts=dict(self.activity_counts),
                idle_metrics=dict(self.idle_metrics),
                activity_metrics=dict(self.activity_metrics),
            )
        else:
            for key in (
                "valid_activity_count", "unique_activity_types", "activity_counts",
                "failure_taxonomy",
            ):
                record.pop(key, None)
        return record
