"""Descriptive Phase 8A tables and a secret-free dataset manifest."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .ablation_metrics import AblationGroupMetrics, AblationSummary
from .models import ABLATION_EPISODE_SCHEMA_VERSION, TRAJECTORY_SCHEMA_VERSION, EpisodeResult


@dataclass(frozen=True)
class AblationReport:
    policy_metrics_json: Path
    policy_scenario_metrics_json: Path
    summary_markdown: Path
    summary_csv: Path
    dataset_manifest: Path


def _timestamp(value: datetime | str | None) -> str:
    if value is None:
        value = datetime.now(timezone.utc)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("created_at must have a timezone")
        return value.isoformat()
    if isinstance(value, str) and value.strip():
        return value
    raise TypeError("created_at must be a timezone-aware datetime, nonempty string, or None")


def _valid_id(value: str, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", value):
        raise ValueError(f"{field} must be a short identifier")
    return value


def _json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as target:
        json.dump(value, target, ensure_ascii=False, indent=2, allow_nan=False)
        target.write("\n")


def _rate(value: float) -> str:
    return f"{value:.3f}"


def _number(value: float) -> str:
    return f"{value:.2f}"


def _first_repeat(metrics: AblationGroupMetrics) -> str:
    eligible = metrics.first_rejection_eligible_episodes
    return f"{_rate(metrics.first_rejection_repeat_rate)} (n={eligible})" if eligible else "N/A (n=0)"


def _table(rows: list[list[str]]) -> list[str]:
    if not rows:
        return []
    return [
        "| " + " | ".join(rows[0]) + " |",
        "| " + " | ".join("---" for _ in rows[0]) + " |",
        *("| " + " | ".join(row) + " |" for row in rows[1:]),
    ]


def _markdown(summary: AblationSummary, policies: Sequence[str], scenarios: Sequence[str]) -> str:
    by_policy = [[
        "Policy", "Episodes", "Success", "Completion", "Avg Decisions",
        "Rejection Rate", "Repeat-Rejection Rate (eligible)", "Avg Context Chars",
        "Avg Input Tokens", "Avg Latency (s)",
    ]]
    for policy in policies:
        item = summary.policy_metrics[policy]
        by_policy.append([
            policy, str(item.episodes), str(item.success), _rate(item.completion_rate),
            _number(item.avg_decisions), _rate(item.rejection_rate),
            _first_repeat(item), _number(item.avg_context_chars),
            _number(item.avg_input_tokens), _number(item.avg_latency),
        ])
    by_cell = [[
        "Scenario", "Policy", "Episodes", "Completion", "First Repeat Rate (eligible)",
        "Rejections", "Avg Decisions", "Avg Input Tokens",
    ]]
    for scenario in scenarios:
        for policy in policies:
            item = summary.policy_scenario_metrics[policy][scenario]
            by_cell.append([
                scenario, policy, str(item.episodes), _rate(item.completion_rate),
                _first_repeat(item), str(item.model_rejection_count),
                _number(item.avg_decisions), _number(item.avg_input_tokens),
            ])
    models = (
        ", ".join(f"{model}: {count} requests" for model, count in summary.provider_model_counts.items())
        if summary.provider_model_counts else "unknown (no actual provider model recorded)"
    )
    stable = (
        "UNKNOWN" if summary.model_backend_stable is None
        else "YES" if summary.model_backend_stable else "NO"
    )
    lines = [
        "# Phase 8A — Context Ablation Pilot",
        "",
        f"Episodes: {summary.episodes_total}",
        f"Model trajectory steps: {summary.step_count}",
        f"Provider requests: {summary.total_provider_requests}",
        f"Actual provider model(s): {models}",
        f"MODEL_BACKEND_STABLE={stable}",
        f"Unattributed provider requests: {summary.unattributed_provider_requests} "
        "(backend unknown; stability refers only to observed provider_model values).",
        "",
        "This is a descriptive pilot with two repetitions per policy × scenario cell; "
        "it does not establish statistical significance.",
        "Prelude rejections are scenario setup and are excluded from model rejection rate.",
        "Provider error rate excludes TIMEOUT; timeout and infrastructure-failure "
        "counts/rates are separate fields in the JSON metrics.",
        "Context, token and latency costs cover completed trajectory steps only; "
        "failed requests still count in provider requests but may lack usage/cost.",
        "First-repeat rate is N/A when no prelude-rejection episode has a valid first step.",
        "",
        "## Overall by Policy",
        "",
        *_table(by_policy),
        "",
        "## Policy × Scenario",
        "",
        *_table(by_cell),
        "",
        "## Key Scenario Comparisons",
        "",
    ]
    for label, scenario, left, right in (
        ("S1 last rejection: C0 vs C1", "S1_LAST_REJECTION", "C0_state", "C1_last"),
        ("S2 buried rejection: C3 vs CR", "S2_BURIED_REJECTION", "C3_recent3", "CR_relevant"),
        ("S3 move-only noise: C0 vs C3", "S3_NOISE_ONLY", "C0_state", "C3_recent3"),
    ):
        if scenario in scenarios and left in summary.policy_metrics and right in summary.policy_metrics:
            first = summary.policy_scenario_metrics[left][scenario]
            second = summary.policy_scenario_metrics[right][scenario]
            lines.append(
                f"- {label}: completion {_rate(first.completion_rate)} vs "
                f"{_rate(second.completion_rate)}; first-repeat "
                f"{_first_repeat(first)} vs "
                f"{_first_repeat(second)}; input tokens "
                f"{_number(first.avg_input_tokens)} vs {_number(second.avg_input_tokens)}."
            )
    step_rows = [[
        "Actual Model", "Policy", "Scenario", "Steps", "Requests", "Rejections",
        "Avg Context", "Avg Input", "Avg Output", "Avg Reasoning", "Avg Latency (s)",
    ]]
    for model, policy_groups in summary.provider_model_policy_scenario_steps.items():
        for policy in policies:
            for scenario in scenarios:
                item = policy_groups[policy][scenario]
                if item.steps:
                    step_rows.append([
                        model, policy, scenario, str(item.steps), str(item.provider_requests),
                        str(item.rejected_actions), _number(item.avg_context_chars),
                        _number(item.avg_input_tokens), _number(item.avg_output_tokens),
                        _number(item.avg_reasoning_tokens), _number(item.avg_latency),
                    ])
    lines.extend([
        "", "## Actual Provider-Model Step Metrics", "",
        "These costs and rejections are attributed by each StepTrajectory.provider_model. "
        "Episode success is not attributed in this table.",
        "", *_table(step_rows),
    ])
    if not summary.model_backend_stable and summary.model_backend_stable is not None:
        lines.extend([
            "", "MODEL_BACKEND_CHANGED_DURING_EXPERIMENT",
            "Do not interpret pooled policy differences as a pure context effect; "
            "inspect the per-step provider-model cells above and in the JSON artifacts.",
        ])
        backend_rows = [["Episode Backend Bucket", "Policy", "Episodes", "Completion", "Avg Decisions"]]
        for backend, policy_groups in summary.backend_policy_metrics.items():
            for policy in policies:
                item = policy_groups[policy]
                backend_rows.append([
                    backend, policy, str(item.episodes),
                    _rate(item.completion_rate)
                    if summary.backend_episode_success_attributable[backend] else "N/A (not attributable)",
                    _number(item.avg_decisions),
                ])
        lines.extend([
            "", "## By Actual Provider Backend", "",
            "Episode-level MIXED_BACKEND and unknown buckets are retained for audit, "
            "but their success cannot be attributed to one actual model.",
            "", *_table(backend_rows),
        ])
    lines.extend([
        "", "## Limitations", "",
        "Only one scenario family and one provider alias were used. Provider reasoning "
        "behavior may vary, and these outcomes do not yet represent local 8B performance.",
        "No policy winner is selected from this pilot.", "",
    ])
    return "\n".join(lines)


def write_ablation_report(
    output_dir: str | Path,
    summary: AblationSummary,
    episodes: Sequence[EpisodeResult],
    *,
    policies: Sequence[str],
    scenarios: Sequence[str],
    repetitions_per_cell: int,
    provider_alias: str,
    experiment_config_hash: str,
    created_at: datetime | str | None = None,
) -> AblationReport:
    """Write metrics, tables and manifest; never include context or raw prompts."""
    episode_list = tuple(episodes)
    if summary.episodes_total != len(episode_list):
        raise ValueError("summary and episodes disagree")
    if isinstance(repetitions_per_cell, bool) or not isinstance(repetitions_per_cell, int) or repetitions_per_cell < 1:
        raise ValueError("repetitions_per_cell must be positive")
    policy_order = tuple(_valid_id(policy, "policy") for policy in policies)
    scenario_order = tuple(_valid_id(scenario, "scenario") for scenario in scenarios)
    if len(set(policy_order)) != len(policy_order) or len(set(scenario_order)) != len(scenario_order):
        raise ValueError("policy and scenario IDs must be unique")
    if not policy_order or not scenario_order:
        raise ValueError("policies and scenarios cannot be empty")
    _valid_id(provider_alias, "provider_alias")
    if not isinstance(experiment_config_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", experiment_config_hash):
        raise ValueError("experiment_config_hash must be a SHA-256 hex digest")
    if set(summary.policy_metrics) != set(policy_order):
        raise ValueError("summary policy cells do not match declared policies")
    if any(set(summary.policy_scenario_metrics[policy]) != set(scenario_order) for policy in policy_order):
        raise ValueError("summary scenario cells do not match declared scenarios")
    if any(ep.experiment_config_hash != experiment_config_hash for ep in episode_list):
        raise ValueError("episode experiment_config_hash does not match report")
    timestamp = _timestamp(created_at)
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    report = AblationReport(
        policy_metrics_json=directory / "policy_metrics.json",
        policy_scenario_metrics_json=directory / "policy_scenario_metrics.json",
        summary_markdown=directory / "ablation_summary.md",
        summary_csv=directory / "ablation_summary.csv",
        dataset_manifest=directory / "dataset_manifest.json",
    )
    paths = tuple(vars(report).values())
    if any(path.exists() for path in paths):
        raise FileExistsError("ablation report output already exists")
    policy_data = {
        "experiment_config_hash": experiment_config_hash,
        "provider_model_counts": summary.provider_model_counts,
        "model_backend_stable": summary.model_backend_stable,
        "unattributed_provider_requests": summary.unattributed_provider_requests,
        "backend_metrics": {key: item.to_dict() for key, item in summary.backend_metrics.items()},
        "backend_policy_metrics": {
            backend: {policy: item.to_dict() for policy, item in groups.items()}
            for backend, groups in summary.backend_policy_metrics.items()
        },
        "backend_episode_success_attributable": summary.backend_episode_success_attributable,
        "backend_episode_metrics_note": (
            "Episode-level buckets are not per-step provider-model metrics. "
            "MIXED_BACKEND/unknown bucket success is not attributable to one model."
        ),
        "policies": {policy: summary.policy_metrics[policy].to_dict() for policy in policy_order},
    }
    cell_data = {
        "experiment_config_hash": experiment_config_hash,
        "cells": {
            policy: {
                scenario: summary.policy_scenario_metrics[policy][scenario].to_dict()
                for scenario in scenario_order
            }
            for policy in policy_order
        },
        "backend_cells": {
            backend: {
                policy: {
                    scenario: item.to_dict() for scenario, item in scenarios.items()
                }
                for policy, scenarios in policies.items()
            }
            for backend, policies in summary.backend_policy_scenario_metrics.items()
        },
        "provider_model_steps": {
            model: {
                policy: {
                    scenario: item.to_dict() for scenario, item in cells.items()
                }
                for policy, cells in policies.items()
            }
            for model, policies in summary.provider_model_policy_scenario_steps.items()
        },
    }
    manifest = {
        "trajectory_schema_version": TRAJECTORY_SCHEMA_VERSION,
        "episode_schema_version": ABLATION_EPISODE_SCHEMA_VERSION,
        "experiment_type": "context_ablation",
        "created_at": timestamp,
        "policies": list(policy_order),
        "scenarios": list(scenario_order),
        "repetitions_per_cell": repetitions_per_cell,
        "episode_count": summary.episodes_total,
        "step_count": summary.step_count,
        "provider_alias": provider_alias,
        "actual_provider_models": summary.provider_model_counts,
        "model_backend_stable": summary.model_backend_stable,
        "experiment_config_hash": experiment_config_hash,
        "contains_hidden_reasoning": False,
        "contains_raw_prompt": any(
            step.prompt is not None for episode in episode_list for step in episode.steps
        ),
    }
    _json(report.policy_metrics_json, policy_data)
    _json(report.policy_scenario_metrics_json, cell_data)
    with report.summary_markdown.open("x", encoding="utf-8") as target:
        target.write(_markdown(summary, policy_order, scenario_order))
    with report.summary_csv.open("x", newline="", encoding="utf-8") as target:
        writer = csv.writer(target)
        writer.writerow([
            "scenario", "policy", "episodes", "success", "completion_rate",
            "first_rejection_eligible_episodes", "first_rejection_repeat_rate",
            "model_rejections", "avg_decisions",
            "avg_context_chars", "avg_input_tokens", "avg_latency",
        ])
        for scenario in scenario_order:
            for policy in policy_order:
                item: AblationGroupMetrics = summary.policy_scenario_metrics[policy][scenario]
                writer.writerow([
                    scenario, policy, item.episodes, item.success, item.completion_rate,
                    item.first_rejection_eligible_episodes,
                    item.first_rejection_repeat_rate
                    if item.first_rejection_eligible_episodes else "N/A",
                    item.model_rejection_count,
                    item.avg_decisions, item.avg_context_chars, item.avg_input_tokens,
                    item.avg_latency,
                ])
    _json(report.dataset_manifest, manifest)
    return report
