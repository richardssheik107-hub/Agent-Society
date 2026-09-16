"""Offline checks for objective benchmark metrics and dataset summaries."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from social_sim.evaluation.metrics import MetricsAggregator, trajectory_signature
from social_sim.evaluation.report import write_benchmark_report


def make_step(
    action: str,
    event_type: str,
    *,
    allowed: bool = True,
    reason: str = "ACCEPTED",
    latency: float = 1.0,
    input_tokens: int | None = 10,
    output_tokens: int | None = 2,
    reasoning_tokens: int | None = 1,
    prompt: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        proposal={"action": action},
        intent={"action": action},
        rule_allowed=allowed,
        rule_reason_code=reason,
        event={"event_type": event_type},
        context_chars=100,
        prompt_chars=200,
        decision_latency_seconds=latency,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        reasoning_tokens=reasoning_tokens,
        prompt=prompt,
    )


def make_episode(
    steps: tuple[SimpleNamespace, ...],
    *,
    success: bool = True,
    reason: str = "GOAL_REACHED",
    decision_count: int | None = None,
    requests: int | None = None,
    invalid_outputs: int = 0,
    provider_errors: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        steps=steps,
        success=success,
        termination_reason=reason,
        decision_count=len(steps) if decision_count is None else decision_count,
        accepted_actions=sum(step.rule_allowed for step in steps),
        rejected_actions=sum(not step.rule_allowed for step in steps),
        invalid_outputs=invalid_outputs,
        provider_errors=provider_errors,
        total_provider_requests=len(steps) if requests is None else requests,
        model_name="scripted",
    )


def test_metrics_aggregate_success_rejection_and_failed_request() -> None:
    direct = make_episode(
        (
            make_step("MOVE", "MOVED", latency=1.0),
            make_step("BUY", "PURCHASED", latency=2.0),
            make_step("EAT", "ATE", latency=3.0),
        )
    )
    with_rejection = make_episode(
        (
            make_step(
                "BUY", "ACTION_REJECTED", allowed=False,
                reason="NOT_AT_SELLER", latency=4.0,
            ),
            make_step("MOVE", "MOVED", latency=5.0),
            make_step("BUY", "PURCHASED", latency=6.0),
            make_step("EAT", "ATE", latency=7.0),
        )
    )
    timeout = make_episode(
        (), success=False, reason="TIMEOUT", decision_count=1,
        requests=1, provider_errors=1,
    )

    metrics = MetricsAggregator().aggregate([direct, with_rejection, timeout])

    assert metrics.episodes_total == 3
    assert metrics.episodes_success == 2
    assert metrics.completion_rate == pytest.approx(2 / 3)
    assert metrics.avg_decisions == pytest.approx(8 / 3)
    assert metrics.median_decisions == 3
    assert metrics.accepted_actions_total == 6
    assert metrics.rejected_actions_total == 1
    assert metrics.rejection_rate == pytest.approx(1 / 7)
    assert metrics.provider_error_count == metrics.timeout_count == 1
    assert metrics.total_provider_requests == 8
    assert metrics.avg_context_chars == 100
    assert metrics.max_context_chars == 100
    assert metrics.avg_prompt_chars == 200
    assert metrics.max_prompt_chars == 200
    assert metrics.avg_input_tokens_per_decision == 10
    assert metrics.avg_output_tokens_per_decision == 2
    assert metrics.avg_reasoning_tokens_per_decision == 1
    assert metrics.avg_latency_per_decision == 4
    assert metrics.p50_latency == 4
    assert metrics.p95_latency == pytest.approx(6.7)
    assert metrics.action_counts == {"BUY": 3, "EAT": 2, "MOVE": 2}
    assert metrics.rejection_reason_counts == {"NOT_AT_SELLER": 1}
    assert metrics.event_counts == {
        "MOVED": 2, "PURCHASED": 2, "ATE": 2, "ACTION_REJECTED": 1,
    }
    assert metrics.trajectory_counts == {
        "!TIMEOUT": 1,
        "BUY!NOT_AT_SELLER>MOVE>BUY>EAT": 1,
        "MOVE>BUY>EAT": 1,
    }
    assert trajectory_signature(with_rejection) == "BUY!NOT_AT_SELLER>MOVE>BUY>EAT"


def test_empty_and_partial_usage_have_defined_metrics() -> None:
    assert MetricsAggregator().aggregate([]).episodes_total == 0
    assert MetricsAggregator().aggregate([]).p95_latency == 0
    episode = make_episode(
        (
            make_step("MOVE", "MOVED", input_tokens=None, output_tokens=None,
                      reasoning_tokens=None, latency=1),
            make_step("BUY", "PURCHASED", input_tokens=40, output_tokens=8,
                      reasoning_tokens=3, latency=3),
        ),
        success=False,
        reason="MAX_DECISIONS",
    )
    metrics = MetricsAggregator().aggregate([episode])
    assert metrics.avg_input_tokens_per_decision == 40
    assert metrics.avg_output_tokens_per_decision == 8
    assert metrics.avg_reasoning_tokens_per_decision == 3
    assert metrics.p50_latency == 2
    assert metrics.p95_latency == pytest.approx(2.9)
    assert metrics.trajectory_counts == {"MOVE>BUY>!MAX_DECISIONS": 1}


def test_report_writes_summary_and_manifest_without_prompt_content(tmp_path) -> None:
    episode = make_episode(
        (make_step("MOVE", "MOVED", prompt="secret-canary"),)
    )
    metrics = MetricsAggregator().aggregate([episode])

    paths = write_benchmark_report(
        tmp_path, metrics, [episode], scenario_name="lunch",
        decision_client_type="ScriptedDecisionClient", model_name="scripted",
        created_at="2026-01-01T00:00:00+00:00",
    )

    summary = json.loads(paths.summary_json.read_text(encoding="utf-8"))
    manifest = json.loads(paths.dataset_manifest.read_text(encoding="utf-8"))
    markdown = paths.summary_markdown.read_text(encoding="utf-8")
    assert summary["completion_rate"] == 1
    assert summary["trajectory_counts"] == {"MOVE": 1}
    assert manifest == {
        "schema_version": "0.1",
        "scenario": "lunch",
        "created_at": "2026-01-01T00:00:00+00:00",
        "episode_count": 1,
        "step_count": 1,
        "decision_client_type": "ScriptedDecisionClient",
        "model": "scripted",
        "contains_raw_prompt": True,
        "contains_hidden_reasoning": False,
    }
    assert "# Lunch Benchmark" in markdown
    assert "Top Trajectories" in markdown
    assert "secret-canary" not in (
        paths.summary_json.read_text(encoding="utf-8")
        + paths.summary_markdown.read_text(encoding="utf-8")
        + paths.dataset_manifest.read_text(encoding="utf-8")
    )
