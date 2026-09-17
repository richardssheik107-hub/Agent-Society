"""Controlled independent Research A2.0 segments and aggregate measurements."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean

from social_sim.evaluation.models import world_snapshot
from social_sim.world import OfferState, PersonWorldState, WorldState

from .models import DailyEpisodeResult
from .profiles import ExperimentBehaviorProfile
from .persona import NeutralPersona
from .runner import DailyEpisodeRunner


SEGMENTS = ("MORNING", "WORK", "MIDDAY", "EVENING")
_START = {
    "MORNING": (6, "home", 100.0, 0.3, 0.8),
    "WORK": (9, "office", 100.0, 0.4, 0.7),
    "MIDDAY": (12, "office", 100.0, 0.8, 0.6),
    "EVENING": (18, "home", 100.0, 0.4, 0.4),
}


def segment_world(segment: str) -> WorldState:
    hour, location, money, hunger, energy = _START[segment]
    return WorldState(
        time=datetime(2026, 1, 1, hour, tzinfo=timezone.utc),
        people={1: PersonWorldState(1, location, money, hunger, energy=energy)},
        locations=("home", "office", "restaurant", "park"),
        venues={"restaurant": {"meal": OfferState("meal", 20.0, 10)}},
    )


def interleaved_schedule(profiles: tuple[ExperimentBehaviorProfile, ...]) -> list[dict[str, object]]:
    order = ((0, 1, 2), (1, 2, 0), (2, 0, 1), (0, 2, 1))
    schedule = []
    for repeat in (1, 2):
        for index, segment in enumerate(SEGMENTS):
            for position in (order[index] if repeat == 1 else tuple(reversed(order[index]))):
                schedule.append({"episode": len(schedule) + 1, "repeat": repeat,
                                 "segment": segment, "profile": profiles[position].name})
    return schedule


def config_hash(config: dict[str, object]) -> str:
    return hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def episode_metrics(result: DailyEpisodeResult, *, segment: str, repeat: int) -> dict[str, object]:
    complete = result.day_completed
    activity = result.activity_metrics
    counts = Counter(step.proposal["action"] for step in result.trajectory.steps)
    return {
        "episode_id": result.episode_id, "profile": result.behavior_profile_name,
        "profile_hash": result.behavior_profile_hash,
        "segment": segment, "repeat": repeat, "segment_completion": complete,
        "termination_reason": result.termination_reason.value,
        "provider_failure": bool(result.provider_failures),
        "behavior_metrics_valid": complete,
        "observed_minutes": result.observed_minutes,
        "decision_count": result.decision_count,
        "provider_request_count": result.provider_request_count,
        "decisions_per_sim_hour": activity["decisions_per_sim_hour"],
        "decision_burst_count": activity["decision_burst_count"],
        "same_state_decision_count": activity["same_state_decision_count"],
        "accepted_actions": result.trajectory.accepted_actions,
        "rejected_actions": result.trajectory.rejected_actions,
        "rejection_rate": result.trajectory.rejected_actions / len(result.trajectory.steps) if result.trajectory.steps else 0,
        "idle_minutes": result.idle_metrics["idle_minutes"],
        "idle_ratio": result.idle_metrics["idle_ratio"],
        "max_idle_streak": result.idle_metrics["max_idle_streak_minutes"],
        "active_minutes": activity["active_minutes"],
        "unique_activity_types": result.unique_activity_types,
        "state_transition_count": activity["state_transition_count"],
        "unresolved_need_minutes": result.idle_metrics["unresolved_need_minutes"],
        "obligation_neglect_minutes": sum(
            15 for tick in result.ticks
            if 9 <= datetime.fromisoformat(tick.simulation_time).hour < 17
            and tick.active_activity != "WORK"
        ),
        "sleep_minutes": activity["sleep_minutes"], "work_minutes": activity["work_minutes"],
        "eat_count": activity["meal_count"], "leisure_minutes": activity["leisure_minutes"],
        "move_count": activity["move_count"],
        "personal_care_minutes": activity["personal_care_minutes"],
        "chores_minutes": activity["chores_minutes"],
        "personal_care_proposals": counts["PERSONAL_CARE"],
        "chores_proposals": counts["CHORES"],
        "personal_care_accepted": result.activity_counts.get("PERSONAL_CARE", 0),
        "chores_accepted": result.activity_counts.get("CHORES", 0),
        "avg_context_chars": mean(s.context_chars for s in result.trajectory.steps) if result.trajectory.steps else None,
        "avg_prompt_chars": mean(s.prompt_chars for s in result.trajectory.steps) if result.trajectory.steps else None,
        "input_tokens": result.trajectory.total_input_tokens,
        "output_tokens": result.trajectory.total_output_tokens,
        "reasoning_tokens": result.trajectory.total_reasoning_tokens,
        "latency_seconds": result.trajectory.total_latency_seconds,
        "provider_models": dict(Counter(s.provider_model for s in result.trajectory.steps if s.provider_model)),
        "no_action": "NO_ACTION" in result.failure_taxonomy if complete else None,
        "invalid_proposals": len(result.output_failures),
    }


_AVERAGES = (
    "decision_count", "decision_burst_count", "provider_request_count", "idle_ratio",
    "unique_activity_types", "unresolved_need_minutes", "obligation_neglect_minutes",
    "same_state_decision_count", "decisions_per_sim_hour", "active_minutes",
    "avg_context_chars", "avg_prompt_chars", "input_tokens", "output_tokens",
    "reasoning_tokens", "latency_seconds", "personal_care_minutes", "chores_minutes",
)


def aggregate(rows: list[dict[str, object]]) -> dict[str, object]:
    complete = [row for row in rows if row["segment_completion"]]
    return {
        "complete_segments": len(complete), "truncated_segments": len(rows) - len(complete),
        "provider_failures": sum(bool(row["provider_failure"]) for row in rows),
        "architecture_failures": sum(row["termination_reason"] == "ARCHITECTURE_ERROR" for row in rows),
        **{f"avg_{field}": mean(row[field] for row in complete if row[field] is not None)
           if any(row[field] is not None for row in complete) else None for field in _AVERAGES},
        "no_action_count": sum(bool(row["no_action"]) for row in complete),
        "personal_care_proposals": sum(row["personal_care_proposals"] for row in rows),
        "personal_care_accepted": sum(row["personal_care_accepted"] for row in rows),
        "chores_proposals": sum(row["chores_proposals"] for row in rows),
        "chores_accepted": sum(row["chores_accepted"] for row in rows),
    }


@dataclass
class CalibratedSegmentBenchmark:
    client: object
    output_dir: object
    model_name: str | None = None
    prior_index: object | None = None
    prior_limit: int = 0
    write_artifacts: bool = True

    async def run(self, number: int, segment: str, profile: ExperimentBehaviorProfile) -> DailyEpisodeResult:
        world = segment_world(segment)
        result = await DailyEpisodeRunner(
            self.client, output_dir=self.output_dir, model_name=self.model_name,
            persona=NeutralPersona(goal="live through this period while handling your basic needs and obligations"),
            behavior_profile=profile, initial_world=world, window_minutes=180,
            scenario_name="neutral_day", max_decisions_per_day=8,
            allow_deterministic_output_recovery=True,
            prior_index=self.prior_index, prior_limit=self.prior_limit,
            write_artifacts=self.write_artifacts,
        ).run_episode(number)
        if result.ticks and result.ticks[0].world_before != world_snapshot(world):
            raise ValueError("segment initial world changed")
        return result
