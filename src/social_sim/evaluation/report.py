"""Small, deterministic benchmark summaries and a secret-free dataset manifest."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from .metrics import BenchmarkMetrics

if TYPE_CHECKING:
    from .models import EpisodeResult


TRAJECTORY_SCHEMA_VERSION = "0.1"


@dataclass(frozen=True)
class BenchmarkReport:
    summary_json: Path
    summary_markdown: Path
    dataset_manifest: Path


def _created_at(value: datetime | str | None) -> str:
    if value is None:
        value = datetime.now(timezone.utc)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return value.isoformat()
    if isinstance(value, str) and value.strip():
        return value
    raise TypeError("created_at must be a datetime, nonempty string, or None")


def _top_lines(counts: dict[str, int]) -> list[str]:
    return [f"- {name}: {count}" for name, count in counts.items()] or ["- None"]


def _markdown(scenario_name: str, metrics: BenchmarkMetrics) -> str:
    title = f"{scenario_name.replace('_', ' ').title()} Benchmark"
    lines = [
        f"# {title}",
        "",
        f"Episodes: {metrics.episodes_total}",
        f"Successes: {metrics.episodes_success}",
        f"Completion Rate: {metrics.completion_rate:.3f}",
        f"Average Decisions: {metrics.avg_decisions:.3f}",
        f"Median Decisions: {metrics.median_decisions:.3f}",
        f"Rejection Rate: {metrics.rejection_rate:.3f}",
        f"Invalid Outputs: {metrics.invalid_output_count}",
        f"Provider Errors: {metrics.provider_error_count}",
        f"Timeouts: {metrics.timeout_count}",
        f"Provider Requests: {metrics.total_provider_requests}",
        f"Average Context Chars: {metrics.avg_context_chars:.1f}",
        f"Maximum Context Chars: {metrics.max_context_chars}",
        f"Average Prompt Chars: {metrics.avg_prompt_chars:.1f}",
        f"Maximum Prompt Chars: {metrics.max_prompt_chars}",
        "Average Tokens Per Decision "
        f"(input/output/reasoning): {metrics.avg_input_tokens_per_decision:.1f} / "
        f"{metrics.avg_output_tokens_per_decision:.1f} / "
        f"{metrics.avg_reasoning_tokens_per_decision:.1f}",
        f"Average Latency (s): {metrics.avg_latency_per_decision:.3f}",
        f"P50 Latency (s): {metrics.p50_latency:.3f}",
        f"P95 Latency (s): {metrics.p95_latency:.3f}",
        "",
        "## Top Trajectories",
        "",
        *_top_lines(metrics.trajectory_counts),
        "",
        "## Top Rejection Reasons",
        "",
        *_top_lines(metrics.rejection_reason_counts),
        "",
        "## Actions",
        "",
        *_top_lines(metrics.action_counts),
        "",
        "## Events",
        "",
        *_top_lines(metrics.event_counts),
        "",
    ]
    return "\n".join(lines)


def write_benchmark_report(
    output_dir: str | Path,
    metrics: BenchmarkMetrics,
    episodes: Sequence[EpisodeResult],
    *,
    scenario_name: str,
    decision_client_type: str,
    model_name: str | None = None,
    created_at: datetime | str | None = None,
) -> BenchmarkReport:
    """Write summary.json, summary.md and manifest without raw prompts or secrets.

    The manifest reports the *actual* recorded prompt presence, never merely a
    caller's requested flag. Hidden reasoning is absent from the trajectory
    schema and therefore always false here.
    """

    if not scenario_name.strip() or not decision_client_type.strip():
        raise ValueError("scenario_name and decision_client_type must be nonempty")
    episode_list = tuple(episodes)
    if metrics.episodes_total != len(episode_list):
        raise ValueError("metrics and episodes disagree on episode count")
    models = {episode.model_name for episode in episode_list if episode.model_name}
    resolved_model = model_name if model_name is not None else (
        next(iter(models)) if len(models) == 1 else "mixed" if models else None
    )
    timestamp = _created_at(created_at)
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    report = BenchmarkReport(
        summary_json=directory / "summary.json",
        summary_markdown=directory / "summary.md",
        dataset_manifest=directory / "dataset_manifest.json",
    )
    summary = {
        "scenario_name": scenario_name,
        "created_at": timestamp,
        **asdict(metrics),
    }
    manifest = {
        "schema_version": TRAJECTORY_SCHEMA_VERSION,
        "scenario": scenario_name,
        "created_at": timestamp,
        "episode_count": len(episode_list),
        "step_count": sum(len(episode.steps) for episode in episode_list),
        "decision_client_type": decision_client_type,
        "model": resolved_model,
        "contains_raw_prompt": any(
            step.prompt is not None
            for episode in episode_list
            for step in episode.steps
        ),
        "contains_hidden_reasoning": False,
    }
    report.summary_json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    report.summary_markdown.write_text(
        _markdown(scenario_name, metrics), encoding="utf-8"
    )
    report.dataset_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return report
