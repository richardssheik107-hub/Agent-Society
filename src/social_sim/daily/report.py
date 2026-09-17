"""Objective neutral-day tables, taxonomy and secret-free dataset manifest."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Sequence

from .models import DAILY_SCHEMA_VERSION, DailyEpisodeResult, DailyTerminationReason
from .support import SupportCondition, TOY_UNCALIBRATED_PRIORS


def _mean(values: Sequence[int | float]) -> float:
    return float(mean(values)) if values else 0.0


def _percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    low = int(index)
    high = min(low + 1, len(ordered) - 1)
    return float(ordered[low] + (ordered[high] - ordered[low]) * (index - low))


def daily_signature(result: DailyEpisodeResult) -> str:
    parts = []
    for step in result.trajectory.steps:
        action = str(step.proposal["action"])
        if not step.rule_allowed:
            action += f"!{step.rule_reason_code}"
        parts.append(action)
    return ">".join(parts) if parts else "NO_ACTION"


def summarize_daily_episodes(results: Sequence[DailyEpisodeResult]) -> dict[str, object]:
    days = tuple(results)
    completed_days = tuple(day for day in days if day.behavior_metrics_valid)
    truncated_days = tuple(day for day in days if not day.behavior_metrics_valid)
    steps = tuple(step for day in days for step in day.trajectory.steps)
    contexts = [step.context_chars for step in steps]
    prompts = [step.prompt_chars for step in steps]
    inputs = [step.input_tokens for step in steps if step.input_tokens is not None]
    outputs = [step.output_tokens for step in steps if step.output_tokens is not None]
    reasoning = [step.reasoning_tokens for step in steps if step.reasoning_tokens is not None]
    latency = [step.decision_latency_seconds for step in steps]
    models: Counter[str] = Counter()
    for step in steps:
        if step.provider_model:
            models[step.provider_model] += step.provider_request_count
    day_rows = []
    for day in days:
        formal_actions = len(day.trajectory.steps)
        day_contexts = [step.context_chars for step in day.trajectory.steps]
        day_inputs = [step.input_tokens for step in day.trajectory.steps if step.input_tokens is not None]
        day_outputs = [step.output_tokens for step in day.trajectory.steps if step.output_tokens is not None]
        day_reasoning = [step.reasoning_tokens for step in day.trajectory.steps if step.reasoning_tokens is not None]
        day_latency = [step.decision_latency_seconds for step in day.trajectory.steps]
        row = {
            "episode_id": day.episode_id,
            "termination": day.termination_reason.value,
            "day_outcome": day.day_outcome.value,
            "day_completed": day.day_completed,
            "behavior_metrics_valid": day.behavior_metrics_valid,
            "truncation_reason": day.truncation_reason,
            "observed_minutes": day.observed_minutes,
            "observed_ticks": day.observed_ticks,
            "simulated_minutes": day.simulated_minutes,
            "idle_ratio": day.idle_metrics["idle_ratio"] if day.behavior_metrics_valid else None,
            "idle_minutes": day.idle_metrics["idle_minutes"] if day.behavior_metrics_valid else None,
            "max_idle_streak_minutes": day.idle_metrics["max_idle_streak_minutes"] if day.behavior_metrics_valid else None,
            "partial_idle_ratio": (
                day.partial_window_metrics["partial_idle_ratio"]
                if day.partial_window_metrics is not None else None
            ),
            "partial_idle_minutes": (
                day.partial_window_metrics["partial_idle_minutes"]
                if day.partial_window_metrics is not None else None
            ),
            "decision_count": day.decision_count,
            "provider_request_count": day.provider_request_count,
            "activity_counts": day.activity_counts if day.behavior_metrics_valid else None,
            "partial_activity_counts": day.activity_counts if not day.behavior_metrics_valid else None,
            "unique_activity_types": day.unique_activity_types if day.behavior_metrics_valid else None,
            "valid_activity_count": day.valid_activity_count if day.behavior_metrics_valid else None,
            "rejected_actions": day.trajectory.rejected_actions,
            "rejection_rate": (
                day.trajectory.rejected_actions / formal_actions if formal_actions else 0.0
            ) if day.behavior_metrics_valid else None,
            "repeated_invalid_count": day.idle_metrics["repeated_invalid_count"] if day.behavior_metrics_valid else None,
            "behavior_loop_count": day.idle_metrics["behavior_loop_count"] if day.behavior_metrics_valid else None,
            "unresolved_need_minutes": day.idle_metrics["unresolved_need_minutes"] if day.behavior_metrics_valid else None,
            "activity_metrics": day.activity_metrics if day.behavior_metrics_valid else None,
            "partial_window_metrics": day.partial_window_metrics,
            "provider_failures": [dict(failure) for failure in day.provider_failures],
            "failure_taxonomy": list(day.failure_taxonomy) if day.behavior_metrics_valid else None,
            "trajectory_signature": daily_signature(day),
            "context_chars_avg": _mean(day_contexts) if day_contexts else None,
            "context_chars_max": max(day_contexts, default=None),
            "observed_input_tokens": sum(day_inputs),
            "observed_output_tokens": sum(day_outputs),
            "observed_reasoning_tokens": sum(day_reasoning),
            "token_usage_observed_steps": len(day_inputs),
            "latency_seconds_avg": _mean(day_latency) if day_latency else None,
            "latency_seconds_p95": _percentile(day_latency, 0.95) if day_latency else None,
        }
        day_rows.append(row)
    requests = sum(day.provider_request_count for day in days)
    completed_count = len(completed_days)
    truncated_count = len(truncated_days)
    full_day_behavior = {
        "days": completed_count,
        "avg_idle_ratio": _mean([day.idle_metrics["idle_ratio"] for day in completed_days]) if completed_days else None,
        "avg_idle_minutes": _mean([day.idle_metrics["idle_minutes"] for day in completed_days]) if completed_days else None,
        "avg_max_idle_streak_minutes": _mean([day.idle_metrics["max_idle_streak_minutes"] for day in completed_days]) if completed_days else None,
        "avg_unique_activity_types": _mean([day.unique_activity_types for day in completed_days]) if completed_days else None,
        "avg_rejection_rate": _mean([row["rejection_rate"] for row in day_rows if row["day_completed"]]) if completed_days else None,
        "avg_repeated_invalid_count": _mean([day.idle_metrics["repeated_invalid_count"] for day in completed_days]) if completed_days else None,
        "avg_unresolved_need_minutes": _mean([day.idle_metrics["unresolved_need_minutes"] for day in completed_days]) if completed_days else None,
        "avg_sleep_minutes": _mean([day.activity_metrics["sleep_minutes"] for day in completed_days]) if completed_days else None,
        "avg_work_minutes": _mean([day.activity_metrics["work_minutes"] for day in completed_days]) if completed_days else None,
        "avg_leisure_minutes": _mean([day.activity_metrics["leisure_minutes"] for day in completed_days]) if completed_days else None,
        "avg_meal_count": _mean([day.activity_metrics["meal_count"] for day in completed_days]) if completed_days else None,
        "behavior_taxonomy_counts": dict(sorted(Counter(
            flag for day in completed_days for flag in day.failure_taxonomy
        ).items())),
    }
    partial_observed = sum(day.observed_minutes for day in truncated_days)
    partial_window = {
        "days": truncated_count,
        "observed_minutes_total": partial_observed,
        "observed_ticks_total": sum(day.observed_ticks for day in truncated_days),
        "partial_idle_minutes_total": sum(day.idle_metrics["idle_minutes"] for day in truncated_days),
        "partial_idle_ratio_weighted": (
            sum(day.idle_metrics["idle_minutes"] for day in truncated_days) / partial_observed
            if partial_observed else None
        ),
        "partial_decisions_total": sum(day.decision_count for day in truncated_days),
        "partial_activity_counts": dict(sorted(Counter({
            action: sum(day.activity_counts.get(action, 0) for day in truncated_days)
            for action in {action for day in truncated_days for action in day.activity_counts}
        }).items())),
        "truncation_reason_counts": dict(sorted(Counter(
            day.truncation_reason for day in truncated_days
        ).items())),
        "provider_failure_count": sum(len(day.provider_failures) for day in truncated_days),
    }
    return {
        "experiment_type": "neutral_day_idle_benchmark",
        "episode_count": len(days),
        "completed_days_total": completed_count,
        "truncated_days_total": truncated_count,
        "completion_rate": completed_count / len(days) if days else None,
        "full_day_behavior_metrics": full_day_behavior,
        "partial_window_metrics": partial_window,
        "support_condition": SupportCondition.B0_NONE.value if all(
            day.trajectory.decision_policy_name == SupportCondition.B0_NONE.value for day in days
        ) else "MIXED",
        "day_rows": day_rows,
        "aggregate": {
            "avg_idle_ratio": full_day_behavior["avg_idle_ratio"],
            "idle_ratio_observed_days": completed_count,
            "avg_max_idle_streak_minutes": full_day_behavior["avg_max_idle_streak_minutes"],
            "avg_decisions": _mean([day.decision_count for day in completed_days]) if completed_days else None,
            "avg_unique_activity_types": full_day_behavior["avg_unique_activity_types"],
            "avg_rejection_rate": full_day_behavior["avg_rejection_rate"],
            "behavior_loop_days": sum(day.termination_reason is DailyTerminationReason.BEHAVIOR_LOOP for day in days),
            "provider_error_days": sum(day.termination_reason in (
                DailyTerminationReason.PROVIDER_ERROR, DailyTerminationReason.TIMEOUT
            ) for day in days),
            "failure_taxonomy_counts": full_day_behavior["behavior_taxonomy_counts"],
            "provider_requests": requests,
            "completed_decision_steps": len(steps),
            "avg_context_chars": _mean(contexts),
            "max_context_chars": max(contexts, default=0),
            "avg_prompt_chars": _mean(prompts),
            "max_prompt_chars": max(prompts, default=0),
            "avg_input_tokens": _mean(inputs),
            "avg_output_tokens": _mean(outputs),
            "avg_reasoning_tokens": _mean(reasoning),
            "total_observed_input_tokens": sum(inputs),
            "total_observed_output_tokens": sum(outputs),
            "total_observed_reasoning_tokens": sum(reasoning),
            "avg_latency_seconds": _mean(latency),
            "p50_latency_seconds": _percentile(latency, 0.5),
            "p95_latency_seconds": _percentile(latency, 0.95),
            "actual_provider_models": dict(sorted(models.items())),
            "unattributed_provider_requests": requests - sum(models.values()),
        },
    }


def _markdown(summary: dict[str, object]) -> str:
    rows = summary["day_rows"]
    aggregate = summary["aggregate"]
    lines = [
        "# Neutral-Day Runtime Summary", "",
        f"Days executed: {summary['episode_count']}",
        f"Completed/truncated: {summary['completed_days_total']}/{summary['truncated_days_total']}",
        f"Completion rate: {summary['completion_rate']:.3f}" if summary["completion_rate"] is not None else "Completion rate: N/A",
        f"Support: {summary['support_condition']}",
        "No human-realism pass/fail threshold is defined in this pilot.",
        "Full-day behavior metrics use completed days only. Truncated-day observations are reported in a separate partial window and never enter behavior averages.",
        "Partial idle ratio is N/A for a day with zero observed ticks.",
        "Token/context/latency averages cover completed decision steps; failed requests may lack usage.",
        "", "| Day | Termination | Full-Day Idle Ratio | Partial Idle Ratio | Observed Minutes | Ticks | Decisions | Requests | Activities (full or partial) | Rejections |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |",
    ]
    for index, row in enumerate(rows, start=1):
        counts = row["activity_counts"] or row["partial_activity_counts"] or {}
        activities = ",".join(f"{key}:{count}" for key, count in counts.items() if count)
        idle_ratio = f"{row['idle_ratio']:.3f}" if row["idle_ratio"] is not None else "N/A"
        partial_ratio = f"{row['partial_idle_ratio']:.3f}" if row["partial_idle_ratio"] is not None else "N/A"
        lines.append(
            f"| {index} | {row['termination']} | {idle_ratio} | "
            f"{partial_ratio} | {row['observed_minutes']} | {row['observed_ticks']} | "
            f"{row['decision_count']} | {row['provider_request_count']} | "
            f"{activities or 'none'} | {row['rejected_actions']} |"
        )
    avg_idle = f"{aggregate['avg_idle_ratio']:.3f}" if aggregate["avg_idle_ratio"] is not None else "N/A"
    avg_streak = f"{aggregate['avg_max_idle_streak_minutes']:.1f}" if aggregate["avg_max_idle_streak_minutes"] is not None else "N/A"
    lines.extend([
        "", "## Completed-Day Behavior", "",
        f"- Average idle ratio: {avg_idle}",
        f"- Completed days in behavior average: {aggregate['idle_ratio_observed_days']}",
        f"- Average max idle streak (min): {avg_streak}",
        f"- Average unique activity types/day: {aggregate['avg_unique_activity_types']:.1f}" if aggregate["avg_unique_activity_types"] is not None else "- Average unique activity types/day: N/A",
        f"- Average formal-action rejection rate: {aggregate['avg_rejection_rate']:.3f}" if aggregate["avg_rejection_rate"] is not None else "- Average formal-action rejection rate: N/A",
        "", "## Truncated Partial Windows", "",
        f"- Truncated days: {summary['truncated_days_total']}",
        f"- Observed minutes/ticks: {summary['partial_window_metrics']['observed_minutes_total']}/{summary['partial_window_metrics']['observed_ticks_total']}",
        f"- Partial idle minutes: {summary['partial_window_metrics']['partial_idle_minutes_total']}",
        (
            f"- Weighted partial idle ratio: {summary['partial_window_metrics']['partial_idle_ratio_weighted']:.3f}"
            if summary["partial_window_metrics"]["partial_idle_ratio_weighted"] is not None
            else "- Weighted partial idle ratio: N/A"
        ),
        f"- Partial decisions: {summary['partial_window_metrics']['partial_decisions_total']}",
        f"- Provider failures: {summary['partial_window_metrics']['provider_failure_count']}",
        "", "## Runtime and Provider", "",
        f"- Average attempted decisions/completed day: {aggregate['avg_decisions']:.1f}" if aggregate["avg_decisions"] is not None else "- Average attempted decisions/completed day: N/A",
        f"- Behavior-loop days: {aggregate['behavior_loop_days']}",
        f"- Provider-error/timeout days: {aggregate['provider_error_days']}",
        f"- Provider requests: {aggregate['provider_requests']}",
        "", "## Completed-Day Behavior Taxonomy", "",
    ])
    taxonomy = aggregate["failure_taxonomy_counts"]
    lines.extend((f"- {key}: {count}" for key, count in taxonomy.items()))
    if not taxonomy:
        lines.append("- None observed")
    lines.extend(["", "## Truncation Reasons", ""])
    truncations = summary["partial_window_metrics"]["truncation_reason_counts"]
    lines.extend((f"- {key}: {count}" for key, count in truncations.items()))
    if not truncations:
        lines.append("- None observed")
    lines.extend([
        "", "## Context and Cost", "",
        f"- Context chars, avg/max: {aggregate['avg_context_chars']:.1f}/{aggregate['max_context_chars']}",
        f"- Prompt chars, avg/max: {aggregate['avg_prompt_chars']:.1f}/{aggregate['max_prompt_chars']}",
        f"- Tokens per completed step, input/output/reasoning: {aggregate['avg_input_tokens']:.1f}/"
        f"{aggregate['avg_output_tokens']:.1f}/{aggregate['avg_reasoning_tokens']:.1f}",
        f"- Latency seconds, mean/p50/p95: {aggregate['avg_latency_seconds']:.2f}/"
        f"{aggregate['p50_latency_seconds']:.2f}/{aggregate['p95_latency_seconds']:.2f}",
        f"- Actual provider model counts: {aggregate['actual_provider_models']}",
        f"- Unattributed requests: {aggregate['unattributed_provider_requests']}",
        "", "## Per-Day Context and Cost", "",
        "| Day | Context chars avg/max | Observed tokens in/out/reasoning | Usage steps | Latency sec avg/p95 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ])
    for index, row in enumerate(rows, start=1):
        context = (
            f"{row['context_chars_avg']:.1f}/{row['context_chars_max']}"
            if row["context_chars_avg"] is not None else "N/A"
        )
        latency_day = (
            f"{row['latency_seconds_avg']:.2f}/{row['latency_seconds_p95']:.2f}"
            if row["latency_seconds_avg"] is not None else "N/A"
        )
        lines.append(
            f"| {index} | {context} | "
            f"{row['observed_input_tokens']}/{row['observed_output_tokens']}/{row['observed_reasoning_tokens']} | "
            f"{row['token_usage_observed_steps']} | {latency_day} |"
        )
    lines.extend([
        "", "## Compact Trajectories", "",
    ])
    lines.extend((f"- Day {index}: `{row['trajectory_signature']}`" for index, row in enumerate(rows, start=1)))
    lines.extend([
        "", "This is an uncalibrated baseline: one persona, one provider alias, "
        "no real behavior corpus, and no claim of human realism.", "",
    ])
    return "\n".join(lines)


def write_daily_report(
    output_dir: str | Path,
    results: Sequence[DailyEpisodeResult],
    *,
    provider_alias: str,
    created_at: datetime | None = None,
) -> dict[str, Path]:
    """Persist reproducible summaries without prompts, secrets or reasoning text."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    summary = summarize_daily_episodes(results)
    timestamp = (created_at or datetime.now(timezone.utc)).isoformat()
    paths = {
        "summary_json": directory / "summary.json",
        "summary_markdown": directory / "summary.md",
        "dataset_manifest": directory / "dataset_manifest.json",
    }
    if any(path.exists() for path in paths.values()):
        raise FileExistsError("daily report already exists")
    summary["created_at"] = timestamp
    manifest = {
        "schema_version": DAILY_SCHEMA_VERSION,
        "experiment_type": "neutral_day_idle_benchmark",
        "created_at": timestamp,
        "episode_count": len(results),
        "tick_count": sum(len(day.ticks) for day in results),
        "decision_step_count": sum(len(day.trajectory.steps) for day in results),
        "provider_alias": provider_alias,
        "support_condition": summary["support_condition"],
        "support_source": TOY_UNCALIBRATED_PRIORS,
        "real_behavior_corpus_used": False,
        "actual_provider_models": summary["aggregate"]["actual_provider_models"],
        "contains_raw_prompt": any(
            step.prompt is not None for day in results for step in day.trajectory.steps
        ),
        "contains_hidden_reasoning": False,
    }
    for key, value in (
        ("summary_json", summary), ("dataset_manifest", manifest)
    ):
        with paths[key].open("x", encoding="utf-8") as target:
            json.dump(value, target, ensure_ascii=False, indent=2, allow_nan=False)
            target.write("\n")
    with paths["summary_markdown"].open("x", encoding="utf-8") as target:
        target.write(_markdown(summary))
    return paths
