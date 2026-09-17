"""A1.1: completed-day behavior and partial infrastructure windows never mix."""

import asyncio
from dataclasses import replace

import httpx
import pytest

from social_sim.daily.models import DayOutcome, DailyTerminationReason
from social_sim.daily.report import summarize_daily_episodes
from social_sim.daily.runner import DailyEpisodeRunner
from social_sim.daily.scripted import PathologicalBuyAtHomeClient, ScriptedNormalDayClient
from social_sim.daily.validation import validate_daily_trajectory
from social_sim.decision.client import (
    DecisionReply, DecisionResponseMetadata, ProviderContractError,
)


class TimeoutAfterNDecisionClient:
    """Two known invalid decisions, then one no-retry timeout at 06:30."""

    def __init__(self, successful_requests: int = 2) -> None:
        self.successful_requests = successful_requests
        self.provider_request_count = 0
        self.call_count = 0
        self.last_metadata = None

    async def complete(self, system_prompt: str, user_prompt: str) -> DecisionReply:
        self.call_count += 1
        self.provider_request_count += 1
        if self.call_count > self.successful_requests:
            raise httpx.ReadTimeout("scripted timeout")
        return DecisionReply('{"action":"BUY","target":"meal"}', provider_request_count=1)


def _run(client, tmp_path, number=1):
    return asyncio.run(DailyEpisodeRunner(
        client, output_dir=tmp_path, write_artifacts=False,
    ).run_episode(number))


def test_scripted_full_day_is_the_only_valid_behavior_sample(tmp_path) -> None:
    day = _run(ScriptedNormalDayClient(), tmp_path)
    assert day.day_outcome is DayOutcome.DAY_COMPLETED
    assert day.termination_reason is DailyTerminationReason.DAY_END
    assert day.day_completed and day.behavior_metrics_valid
    assert day.observed_ticks == 72
    assert day.observed_minutes == 1080
    assert day.provider_request_count == 0
    assert day.truncation_reason is None
    assert day.provider_failures == ()
    assert day.full_day_behavior_metrics is not None
    assert day.partial_window_metrics is None
    assert day.full_day_behavior_metrics["work_minutes"] > 0
    assert day.to_dict()["full_day_behavior_metrics"]["idle_ratio"] == 0
    assert validate_daily_trajectory(day)


def test_timeout_immediately_truncates_and_has_partial_metrics_only(tmp_path) -> None:
    client = TimeoutAfterNDecisionClient()
    day = _run(client, tmp_path)
    assert day.termination_reason is DailyTerminationReason.TIMEOUT
    assert day.day_outcome is DayOutcome.DAY_TRUNCATED_PROVIDER
    assert day.truncation_reason == "DAY_TRUNCATED_PROVIDER"
    assert not day.day_completed and not day.behavior_metrics_valid
    assert day.observed_ticks == 2
    assert day.observed_minutes == 30
    assert day.decision_count == 3
    assert day.provider_request_count == client.call_count == 3
    assert len(day.trajectory.steps) == 2
    assert day.full_day_behavior_metrics is None
    assert day.partial_window_metrics == {
        "observed_minutes": 30,
        "observed_ticks": 2,
        "partial_idle_minutes": 30,
        "partial_idle_ratio": 1.0,
        "partial_activity_counts": {action: 0 for action in day.activity_counts},
        "partial_decisions": 3,
    }
    failure = day.provider_failures[0]
    assert failure["failure_type"] == "TIMEOUT"
    assert failure["simulation_time"].endswith("06:30:00+00:00")
    assert failure["trigger_reason"] == "ACTION_REJECTED"
    assert failure["latency_seconds"] >= 0
    assert failure["input_tokens"] is None
    assert failure["output_tokens"] is None
    assert failure["reasoning_tokens"] is None
    serialized = day.to_dict()
    assert serialized["full_day_behavior_metrics"] is None
    assert "idle_metrics" not in serialized
    assert "activity_metrics" not in serialized
    assert "activity_counts" not in serialized
    assert "failure_taxonomy" not in serialized
    assert serialized["partial_window_metrics"]["partial_idle_ratio"] == 1.0
    assert validate_daily_trajectory(day)


def test_completed_and_truncated_metrics_are_aggregated_separately(tmp_path) -> None:
    complete = _run(ScriptedNormalDayClient(), tmp_path, 1)
    partial = _run(TimeoutAfterNDecisionClient(), tmp_path, 2)
    summary = summarize_daily_episodes((complete, partial))
    assert summary["completed_days_total"] == 1
    assert summary["truncated_days_total"] == 1
    assert summary["completion_rate"] == 0.5
    assert summary["full_day_behavior_metrics"]["avg_idle_ratio"] == 0
    assert summary["partial_window_metrics"]["partial_idle_ratio_weighted"] == 1.0
    assert summary["aggregate"]["avg_idle_ratio"] == 0
    assert summary["day_rows"][1]["idle_ratio"] is None
    assert summary["day_rows"][1]["partial_idle_ratio"] == 1.0
    assert summary["day_rows"][1]["failure_taxonomy"] is None


def test_empty_provider_content_is_infrastructure_not_behavior(tmp_path) -> None:
    class EmptyContentClient:
        provider_request_count = 0
        last_metadata = None

        async def complete(self, system_prompt: str, user_prompt: str) -> DecisionReply:
            self.provider_request_count += 1
            raise ProviderContractError(
                "EMPTY_FINAL_CONTENT",
                DecisionResponseMetadata(http_status=200, provider_model="ark-" + "x" * 32),
            )

    day = _run(EmptyContentClient(), tmp_path)
    assert day.day_outcome is DayOutcome.DAY_TRUNCATED_PROVIDER
    assert day.provider_failures[0]["failure_type"] == "EMPTY_CONTENT"
    assert day.provider_failures[0]["provider_model"] is None
    assert day.observed_ticks == 0
    assert day.partial_window_metrics["partial_idle_ratio"] is None
    assert day.failure_taxonomy == ("PROVIDER_FAILURE",)
    assert "NO_ACTION" not in day.failure_taxonomy


def test_validator_rejects_full_day_metric_on_truncated_day(tmp_path) -> None:
    day = _run(TimeoutAfterNDecisionClient(), tmp_path)
    damaged = replace(day, full_day_behavior_metrics={"idle_ratio": 1.0})
    with pytest.raises(ValueError, match="cannot have full-day metrics"):
        validate_daily_trajectory(damaged)


def test_behavior_loop_has_a_distinct_truncation_class(tmp_path) -> None:
    day = _run(PathologicalBuyAtHomeClient(), tmp_path)
    assert day.termination_reason is DailyTerminationReason.BEHAVIOR_LOOP
    assert day.day_outcome is DayOutcome.DAY_TRUNCATED_BEHAVIOR
    assert not day.behavior_metrics_valid
    assert day.full_day_behavior_metrics is None
    assert day.provider_failures == ()
    assert "INVALID_LOOP" in day.failure_taxonomy


def test_invalid_model_json_is_not_provider_or_full_day_behavior(tmp_path) -> None:
    class InvalidJsonClient:
        provider_request_count = 0

        async def complete(self, system_prompt: str, user_prompt: str) -> DecisionReply:
            self.provider_request_count += 1
            return DecisionReply("not json", provider_request_count=1)

    day = _run(InvalidJsonClient(), tmp_path)
    assert day.day_outcome is DayOutcome.DAY_TRUNCATED_MODEL_OUTPUT
    assert day.termination_reason is DailyTerminationReason.INVALID_MODEL_OUTPUT
    assert day.provider_failures == ()
    assert day.observed_ticks == 0
    assert day.full_day_behavior_metrics is None
    assert day.partial_window_metrics["partial_idle_ratio"] is None
