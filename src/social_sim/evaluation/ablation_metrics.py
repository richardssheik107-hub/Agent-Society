"""Objective Phase 8A summaries grouped by context policy and scenario.

Prelude events describe scenario setup and are deliberately excluded from
model action/rejection rates. No evaluator model or statistical ranking is used.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from statistics import median

from .metrics import MetricsAggregator
from .models import EpisodeResult, StepTrajectory


def _sorted_counts(counts: Counter[str]) -> dict[str, int]:
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _average(values: Sequence[int | float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def _percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower))


def _termination(episode: EpisodeResult) -> str:
    reason = episode.termination_reason
    return getattr(reason, "value", reason)


def _first_action(episode: EpisodeResult) -> tuple[str | None, str | None]:
    if not episode.steps:
        return None, None
    proposal = episode.steps[0].proposal
    action = proposal.get("action")
    target = proposal.get("target")
    return action if isinstance(action, str) else None, target if isinstance(target, str) else None


def _has_prelude_rejection(episode: EpisodeResult) -> bool:
    return bool(episode.prelude_rejection_count or episode.prelude_rejection_present)


def _first_repeats_prelude_rejection(episode: EpisodeResult) -> bool | None:
    if not _has_prelude_rejection(episode) or not episode.steps:
        return None
    action, target = _first_action(episode)
    # S1/S2 both set up exactly one failed BUY meal at home.
    return action == "BUY" and target == "meal"


def _same_rejected_action_repeats(steps: Sequence[StepTrajectory]) -> int:
    """Count repeats within an unchanged-world segment, not just adjacent steps."""
    repeated = 0
    seen: set[tuple[object, object, str]] = set()
    for step in steps:
        if step.state_before != step.state_after:
            seen.clear()
        if step.rule_allowed:
            continue
        if step.state_before == step.state_after:
            key = (
                step.proposal.get("action"), step.proposal.get("target"),
                step.rule_reason_code,
            )
            if key in seen:
                repeated += 1
            seen.add(key)
    return repeated


@dataclass(frozen=True)
class AblationGroupMetrics:
    context_policy_name: str
    scenario_variant: str | None
    episodes: int
    success: int
    completion_rate: float
    avg_decisions: float
    rejection_rate: float
    model_rejection_count: int
    prelude_rejection_count: int
    invalid_output_count: int
    invalid_output_rate: float
    provider_error_count: int
    provider_error_rate: float
    timeout_count: int
    timeout_rate: float
    infra_failure_count: int
    infra_failure_rate: float
    avg_context_chars: float
    median_context_chars: float
    max_context_chars: int
    avg_prompt_chars: float
    max_prompt_chars: int
    avg_input_tokens: float
    avg_output_tokens: float
    avg_reasoning_tokens: float
    avg_latency: float
    p50_latency: float
    p95_latency: float
    first_rejection_eligible_episodes: int
    first_rejection_repeat_count: int
    first_rejection_repeat_rate: float
    recovery_after_rejection_count: int
    recovery_after_rejection_rate: float
    same_rejected_action_repeat_count: int
    context_cost_chars: int
    input_token_cost: int
    success_per_1k_input_tokens: float | None
    total_provider_requests: int
    first_decision_action_counts: dict[str, int] = field(default_factory=dict)
    first_decision_target_counts: dict[str, int] = field(default_factory=dict)
    action_counts: dict[str, int] = field(default_factory=dict)
    trajectory_counts: dict[str, int] = field(default_factory=dict)
    rejection_reason_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ProviderModelStepMetrics:
    """Attribution-safe completed-step facts; never attributes episode success."""

    provider_model: str
    context_policy_name: str
    scenario_variant: str
    steps: int
    provider_requests: int
    accepted_actions: int
    rejected_actions: int
    rejection_rate: float
    avg_context_chars: float
    median_context_chars: float
    max_context_chars: int
    total_context_chars: int
    avg_prompt_chars: float
    max_prompt_chars: int
    total_prompt_chars: int
    avg_input_tokens: float
    total_input_tokens: int
    avg_output_tokens: float
    total_output_tokens: int
    avg_reasoning_tokens: float
    total_reasoning_tokens: int
    avg_latency: float
    p50_latency: float
    p95_latency: float
    total_latency: float
    action_counts: dict[str, int] = field(default_factory=dict)
    rejection_reason_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AblationSummary:
    episodes_total: int
    step_count: int
    total_provider_requests: int
    policy_metrics: dict[str, AblationGroupMetrics]
    policy_scenario_metrics: dict[str, dict[str, AblationGroupMetrics]]
    provider_model_counts: dict[str, int]
    model_backend_stable: bool | None
    unattributed_provider_requests: int
    backend_metrics: dict[str, AblationGroupMetrics]
    backend_policy_metrics: dict[str, dict[str, AblationGroupMetrics]]
    backend_policy_scenario_metrics: dict[str, dict[str, dict[str, AblationGroupMetrics]]]
    provider_model_policy_scenario_steps: dict[str, dict[str, dict[str, ProviderModelStepMetrics]]]
    backend_episode_success_attributable: dict[str, bool]

    def to_dict(self) -> dict[str, object]:
        return {
            "episodes_total": self.episodes_total,
            "step_count": self.step_count,
            "total_provider_requests": self.total_provider_requests,
            "policy_metrics": {key: value.to_dict() for key, value in self.policy_metrics.items()},
            "policy_scenario_metrics": {
                policy: {scenario: metrics.to_dict() for scenario, metrics in cells.items()}
                for policy, cells in self.policy_scenario_metrics.items()
            },
            "provider_model_counts": dict(self.provider_model_counts),
            "model_backend_stable": self.model_backend_stable,
            "unattributed_provider_requests": self.unattributed_provider_requests,
            "backend_metrics": {key: value.to_dict() for key, value in self.backend_metrics.items()},
            "backend_policy_metrics": {
                backend: {policy: item.to_dict() for policy, item in policies.items()}
                for backend, policies in self.backend_policy_metrics.items()
            },
            "backend_policy_scenario_metrics": {
                backend: {
                    policy: {scenario: item.to_dict() for scenario, item in scenarios.items()}
                    for policy, scenarios in policies.items()
                }
                for backend, policies in self.backend_policy_scenario_metrics.items()
            },
            "provider_model_policy_scenario_steps": {
                model: {
                    policy: {scenario: item.to_dict() for scenario, item in scenarios.items()}
                    for policy, scenarios in policies.items()
                }
                for model, policies in self.provider_model_policy_scenario_steps.items()
            },
            "backend_episode_success_attributable": dict(self.backend_episode_success_attributable),
        }


def _group_metrics(
    episodes: Sequence[EpisodeResult],
    *,
    policy_name: str,
    scenario_variant: str | None,
) -> AblationGroupMetrics:
    episode_list = tuple(episodes)
    steps = tuple(step for episode in episode_list for step in episode.steps)
    base = MetricsAggregator().aggregate(episode_list)
    contexts = [step.context_chars for step in steps]
    inputs = [step.input_tokens for step in steps if step.input_tokens is not None]
    first_actions: Counter[str] = Counter()
    first_targets: Counter[str] = Counter()
    eligible = 0
    first_repeats = 0
    repeated_rejections = 0
    for episode in episode_list:
        action, target = _first_action(episode)
        if action is not None:
            first_actions[action] += 1
        if target is not None:
            first_targets[target] += 1
        repeat = _first_repeats_prelude_rejection(episode)
        if repeat is not None:
            eligible += 1
            first_repeats += repeat
        repeated_rejections += _same_rejected_action_repeats(episode.steps)
    total_inputs = sum(inputs)
    timeout_count = sum(_termination(ep) == "TIMEOUT" for ep in episode_list)
    provider_error_count = sum(
        _termination(ep) != "TIMEOUT"
        and (_termination(ep) == "PROVIDER_ERROR" or ep.provider_errors > 0)
        for ep in episode_list
    )
    infra_failure_count = sum(
        _termination(ep) == "TIMEOUT"
        or _termination(ep) == "PROVIDER_ERROR"
        or ep.provider_errors > 0
        for ep in episode_list
    )
    return AblationGroupMetrics(
        context_policy_name=policy_name,
        scenario_variant=scenario_variant,
        episodes=base.episodes_total,
        success=base.episodes_success,
        completion_rate=base.completion_rate,
        avg_decisions=base.avg_decisions,
        rejection_rate=base.rejection_rate,
        model_rejection_count=base.rejected_actions_total,
        prelude_rejection_count=sum(ep.prelude_rejection_count for ep in episode_list),
        invalid_output_count=base.invalid_output_count,
        invalid_output_rate=(base.invalid_output_count / len(episode_list) if episode_list else 0.0),
        provider_error_count=provider_error_count,
        provider_error_rate=(provider_error_count / len(episode_list) if episode_list else 0.0),
        timeout_count=timeout_count,
        timeout_rate=(timeout_count / len(episode_list) if episode_list else 0.0),
        infra_failure_count=infra_failure_count,
        infra_failure_rate=(infra_failure_count / len(episode_list) if episode_list else 0.0),
        avg_context_chars=base.avg_context_chars,
        median_context_chars=float(median(contexts)) if contexts else 0.0,
        max_context_chars=base.max_context_chars,
        avg_prompt_chars=base.avg_prompt_chars,
        max_prompt_chars=base.max_prompt_chars,
        avg_input_tokens=base.avg_input_tokens_per_decision,
        avg_output_tokens=base.avg_output_tokens_per_decision,
        avg_reasoning_tokens=base.avg_reasoning_tokens_per_decision,
        avg_latency=base.avg_latency_per_decision,
        p50_latency=base.p50_latency,
        p95_latency=base.p95_latency,
        first_rejection_eligible_episodes=eligible,
        first_rejection_repeat_count=first_repeats,
        first_rejection_repeat_rate=first_repeats / eligible if eligible else 0.0,
        recovery_after_rejection_count=eligible - first_repeats,
        recovery_after_rejection_rate=(eligible - first_repeats) / eligible if eligible else 0.0,
        same_rejected_action_repeat_count=repeated_rejections,
        context_cost_chars=sum(contexts),
        input_token_cost=total_inputs,
        success_per_1k_input_tokens=(
            base.episodes_success / (total_inputs / 1000) if total_inputs else None
        ),
        total_provider_requests=base.total_provider_requests,
        first_decision_action_counts=_sorted_counts(first_actions),
        first_decision_target_counts=_sorted_counts(first_targets),
        action_counts=base.action_counts,
        trajectory_counts=base.trajectory_counts,
        rejection_reason_counts=base.rejection_reason_counts,
    )


def _step_group_metrics(
    steps: Sequence[StepTrajectory],
    *,
    model: str,
    policy: str,
    scenario: str,
) -> ProviderModelStepMetrics:
    step_list = tuple(steps)
    contexts = [step.context_chars for step in step_list]
    prompts = [step.prompt_chars for step in step_list]
    inputs = [step.input_tokens for step in step_list if step.input_tokens is not None]
    outputs = [step.output_tokens for step in step_list if step.output_tokens is not None]
    reasoning = [step.reasoning_tokens for step in step_list if step.reasoning_tokens is not None]
    latencies = [step.decision_latency_seconds for step in step_list]
    rejected = sum(not step.rule_allowed for step in step_list)
    actions = Counter(
        action for step in step_list
        for action in (step.proposal.get("action"),)
        if isinstance(action, str)
    )
    reasons = Counter(step.rule_reason_code for step in step_list if not step.rule_allowed)
    return ProviderModelStepMetrics(
        provider_model=model,
        context_policy_name=policy,
        scenario_variant=scenario,
        steps=len(step_list),
        provider_requests=sum(step.provider_request_count for step in step_list),
        accepted_actions=len(step_list) - rejected,
        rejected_actions=rejected,
        rejection_rate=rejected / len(step_list) if step_list else 0.0,
        avg_context_chars=_average(contexts),
        median_context_chars=float(median(contexts)) if contexts else 0.0,
        max_context_chars=max(contexts, default=0),
        total_context_chars=sum(contexts),
        avg_prompt_chars=_average(prompts),
        max_prompt_chars=max(prompts, default=0),
        total_prompt_chars=sum(prompts),
        avg_input_tokens=_average(inputs),
        total_input_tokens=sum(inputs),
        avg_output_tokens=_average(outputs),
        total_output_tokens=sum(outputs),
        avg_reasoning_tokens=_average(reasoning),
        total_reasoning_tokens=sum(reasoning),
        avg_latency=_average(latencies),
        p50_latency=_percentile(latencies, 0.5),
        p95_latency=_percentile(latencies, 0.95),
        total_latency=sum(latencies),
        action_counts=_sorted_counts(actions),
        rejection_reason_counts=_sorted_counts(reasons),
    )


class AblationMetricsAggregator:
    """Preserve every policy/scenario cell, including explicitly requested empties."""

    def aggregate(
        self,
        episodes: Sequence[EpisodeResult],
        *,
        policies: Sequence[str] | None = None,
        scenarios: Sequence[str] | None = None,
    ) -> AblationSummary:
        episode_list = tuple(episodes)
        policy_order = tuple(dict.fromkeys(policies)) if policies is not None else tuple(
            sorted({episode.context_policy_name for episode in episode_list})
        )
        scenario_order = tuple(dict.fromkeys(scenarios)) if scenarios is not None else tuple(
            sorted({episode.scenario_variant for episode in episode_list if episode.scenario_variant})
        )
        by_policy: dict[str, list[EpisodeResult]] = defaultdict(list)
        by_cell: dict[tuple[str, str], list[EpisodeResult]] = defaultdict(list)
        backend_episodes: dict[str, list[EpisodeResult]] = defaultdict(list)
        step_by_model_cell: dict[tuple[str, str, str], list[StepTrajectory]] = defaultdict(list)
        provider_models: Counter[str] = Counter()
        for episode in episode_list:
            if episode.context_policy_name not in policy_order:
                raise ValueError("episode context policy is absent from expected policies")
            if episode.scenario_variant not in scenario_order:
                raise ValueError("episode scenario variant is absent from expected scenarios")
            by_policy[episode.context_policy_name].append(episode)
            by_cell[(episode.context_policy_name, episode.scenario_variant)].append(episode)
            actual_models = {
                step.provider_model for step in episode.steps if step.provider_model
            }
            known_requests = sum(
                step.provider_request_count for step in episode.steps if step.provider_model
            )
            backend = (
                "MIXED_BACKEND" if len(actual_models) > 1
                else "PARTIALLY_UNKNOWN_BACKEND"
                if len(actual_models) == 1 and known_requests < episode.total_provider_requests
                else next(iter(actual_models)) if actual_models else "UNKNOWN_BACKEND"
            )
            backend_episodes[backend].append(episode)
            for step in episode.steps:
                step_by_model_cell[
                    (step.provider_model or "UNKNOWN_BACKEND",
                     episode.context_policy_name, episode.scenario_variant)
                ].append(step)
                if step.provider_model and step.provider_request_count:
                    provider_models[step.provider_model] += step.provider_request_count
        policy_metrics = {
            policy: _group_metrics(by_policy[policy], policy_name=policy, scenario_variant=None)
            for policy in policy_order
        }
        cell_metrics = {
            policy: {
                scenario: _group_metrics(
                    by_cell[(policy, scenario)], policy_name=policy, scenario_variant=scenario
                )
                for scenario in scenario_order
            }
            for policy in policy_order
        }
        total_requests = sum(episode.total_provider_requests for episode in episode_list)
        attributed_requests = sum(provider_models.values())
        if attributed_requests > total_requests:
            raise ValueError("attributed model requests exceed episode request totals")
        backend_metrics = {
            backend: _group_metrics(group, policy_name="ALL", scenario_variant=None)
            for backend, group in sorted(backend_episodes.items())
        }
        backend_policy_metrics = {
            backend: {
                policy: _group_metrics(
                    tuple(ep for ep in group if ep.context_policy_name == policy),
                    policy_name=policy,
                    scenario_variant=None,
                )
                for policy in policy_order
            }
            for backend, group in sorted(backend_episodes.items())
        }
        backend_policy_scenario_metrics = {
            backend: {
                policy: {
                    scenario: _group_metrics(
                        tuple(
                            ep for ep in group
                            if ep.context_policy_name == policy and ep.scenario_variant == scenario
                        ),
                        policy_name=policy,
                        scenario_variant=scenario,
                    )
                    for scenario in scenario_order
                }
                for policy in policy_order
            }
            for backend, group in sorted(backend_episodes.items())
        }
        model_keys = tuple(sorted({model for model, _, _ in step_by_model_cell}))
        step_metrics = {
            model: {
                policy: {
                    scenario: _step_group_metrics(
                        step_by_model_cell[(model, policy, scenario)],
                        model=model,
                        policy=policy,
                        scenario=scenario,
                    )
                    for scenario in scenario_order
                }
                for policy in policy_order
            }
            for model in model_keys
        }
        unattributed_requests = total_requests - attributed_requests
        return AblationSummary(
            episodes_total=len(episode_list),
            step_count=sum(len(episode.steps) for episode in episode_list),
            total_provider_requests=total_requests,
            policy_metrics=policy_metrics,
            policy_scenario_metrics=cell_metrics,
            provider_model_counts=_sorted_counts(provider_models),
            model_backend_stable=(
                len(provider_models) == 1 if provider_models else None
            ),
            unattributed_provider_requests=unattributed_requests,
            backend_metrics=backend_metrics,
            backend_policy_metrics=backend_policy_metrics,
            backend_policy_scenario_metrics=backend_policy_scenario_metrics,
            provider_model_policy_scenario_steps=step_metrics,
            backend_episode_success_attributable={
                backend: backend not in {
                    "MIXED_BACKEND", "UNKNOWN_BACKEND", "PARTIALLY_UNKNOWN_BACKEND"
                }
                for backend in backend_episodes
            },
        )


def aggregate_ablation_metrics(
    episodes: Sequence[EpisodeResult],
    *,
    policies: Sequence[str] | None = None,
    scenarios: Sequence[str] | None = None,
) -> AblationSummary:
    return AblationMetricsAggregator().aggregate(episodes, policies=policies, scenarios=scenarios)
