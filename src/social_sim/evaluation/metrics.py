"""Pure-Python benchmark aggregation over recorded episode outcomes.

Unknown provider usage (``None``) is omitted from token averages rather than
being interpreted as zero tokens. All other per-decision averages use recorded
steps as their denominator. A failed request without a completed step is still
included in ``total_provider_requests`` and the episode failure counters.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from statistics import mean, median
from typing import TYPE_CHECKING, Mapping, Sequence

if TYPE_CHECKING:
    from .models import EpisodeResult, StepTrajectory


def _average(values: Sequence[int | float]) -> float:
    return float(mean(values)) if values else 0.0


def _percentile(values: Sequence[float], fraction: float) -> float:
    """Inclusive, linearly interpolated percentile; works for 0 or 1 sample."""

    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower))


def _sorted_counts(counter: Counter[str]) -> dict[str, int]:
    """Keep serialized distribution ordering stable across runs."""

    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0])))


def _action(step: StepTrajectory) -> str:
    proposal = step.proposal
    if isinstance(proposal, Mapping):
        action = proposal.get("action")
        if isinstance(action, str) and action:
            return action
    intent = step.intent
    if isinstance(intent, Mapping):
        action = intent.get("action")
        if isinstance(action, str) and action:
            return action
    return "UNKNOWN_ACTION"


def trajectory_signature(episode: EpisodeResult) -> str:
    """Compact, deterministic action path with rejection and failure markers."""

    parts: list[str] = []
    for step in episode.steps:
        action = _action(step)
        if not step.rule_allowed:
            action += f"!{step.rule_reason_code}"
        parts.append(action)
    if not episode.success:
        reason = episode.termination_reason
        parts.append(f"!{getattr(reason, 'value', reason)}")
    return ">".join(parts) if parts else "NO_ACTION"


@dataclass(frozen=True)
class BenchmarkMetrics:
    episodes_total: int = 0
    episodes_success: int = 0
    completion_rate: float = 0.0
    avg_decisions: float = 0.0
    median_decisions: float = 0.0
    accepted_actions_total: int = 0
    rejected_actions_total: int = 0
    rejection_rate: float = 0.0
    invalid_output_count: int = 0
    provider_error_count: int = 0
    timeout_count: int = 0
    avg_context_chars: float = 0.0
    max_context_chars: int = 0
    avg_prompt_chars: float = 0.0
    max_prompt_chars: int = 0
    avg_input_tokens_per_decision: float = 0.0
    avg_output_tokens_per_decision: float = 0.0
    avg_reasoning_tokens_per_decision: float = 0.0
    avg_latency_per_decision: float = 0.0
    p50_latency: float = 0.0
    p95_latency: float = 0.0
    total_provider_requests: int = 0
    action_counts: dict[str, int] = field(default_factory=dict)
    rejection_reason_counts: dict[str, int] = field(default_factory=dict)
    event_counts: dict[str, int] = field(default_factory=dict)
    trajectory_counts: dict[str, int] = field(default_factory=dict)


class MetricsAggregator:
    """Aggregate objective episode/step data without a model call or judge."""

    def aggregate(self, episodes: Sequence[EpisodeResult]) -> BenchmarkMetrics:
        episode_list = tuple(episodes)
        steps = tuple(step for episode in episode_list for step in episode.steps)
        episode_total = len(episode_list)
        success_total = sum(episode.success for episode in episode_list)
        accepted_total = sum(episode.accepted_actions for episode in episode_list)
        rejected_total = sum(episode.rejected_actions for episode in episode_list)
        completed_actions = accepted_total + rejected_total
        actions = Counter(_action(step) for step in steps)
        reasons = Counter(
            step.rule_reason_code for step in steps if not step.rule_allowed
        )
        event_types = Counter(
            event_type
            for step in steps
            if isinstance(step.event, Mapping)
            for event_type in (step.event.get("event_type"),)
            if isinstance(event_type, str) and event_type
        )
        trajectories = Counter(trajectory_signature(episode) for episode in episode_list)
        latencies = [step.decision_latency_seconds for step in steps]

        return BenchmarkMetrics(
            episodes_total=episode_total,
            episodes_success=success_total,
            completion_rate=success_total / episode_total if episode_total else 0.0,
            avg_decisions=_average([episode.decision_count for episode in episode_list]),
            median_decisions=(
                float(median(episode.decision_count for episode in episode_list))
                if episode_list else 0.0
            ),
            accepted_actions_total=accepted_total,
            rejected_actions_total=rejected_total,
            rejection_rate=rejected_total / completed_actions if completed_actions else 0.0,
            invalid_output_count=sum(episode.invalid_outputs for episode in episode_list),
            provider_error_count=sum(episode.provider_errors for episode in episode_list),
            timeout_count=sum(
                getattr(episode.termination_reason, "value", episode.termination_reason)
                == "TIMEOUT"
                for episode in episode_list
            ),
            avg_context_chars=_average([step.context_chars for step in steps]),
            max_context_chars=max((step.context_chars for step in steps), default=0),
            avg_prompt_chars=_average([step.prompt_chars for step in steps]),
            max_prompt_chars=max((step.prompt_chars for step in steps), default=0),
            avg_input_tokens_per_decision=_average(
                [step.input_tokens for step in steps if step.input_tokens is not None]
            ),
            avg_output_tokens_per_decision=_average(
                [step.output_tokens for step in steps if step.output_tokens is not None]
            ),
            avg_reasoning_tokens_per_decision=_average(
                [step.reasoning_tokens for step in steps if step.reasoning_tokens is not None]
            ),
            avg_latency_per_decision=_average(latencies),
            p50_latency=_percentile(latencies, 0.5),
            p95_latency=_percentile(latencies, 0.95),
            total_provider_requests=sum(
                episode.total_provider_requests for episode in episode_list
            ),
            action_counts=_sorted_counts(actions),
            rejection_reason_counts=_sorted_counts(reasons),
            event_counts=_sorted_counts(event_types),
            trajectory_counts=_sorted_counts(trajectories),
        )
