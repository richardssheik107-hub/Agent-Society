"""Daily runner reuses the closed-loop decision path and validates tick continuity."""

import asyncio
from dataclasses import replace

import pytest

from social_sim.daily.report import summarize_daily_episodes, write_daily_report
from social_sim.daily.models import DailyTerminationReason
from social_sim.daily.runner import DailyEpisodeRunner
from social_sim.daily.scripted import PathologicalBuyAtHomeClient, ScriptedNormalDayClient
from social_sim.daily.validation import validate_daily_trajectory
from social_sim.decision.client import DecisionClientError


def test_scripted_day_has_72_ticks_without_idle_or_provider_requests(tmp_path) -> None:
    client = ScriptedNormalDayClient()
    result = asyncio.run(DailyEpisodeRunner(client, output_dir=tmp_path).run_episode(1))
    assert result.termination_reason is DailyTerminationReason.DAY_END
    assert len(result.ticks) == 72
    assert result.ticks[0].simulation_time.endswith("06:00:00+00:00")
    assert result.ticks[-1].end_time.endswith("00:00:00+00:00")
    assert result.provider_request_count == 0
    assert result.decision_count == client.call_count <= 30
    assert result.idle_metrics["idle_minutes"] == 0
    assert result.idle_metrics["repeated_invalid_count"] == 0
    assert result.trajectory.rejected_actions == 0
    assert result.activity_metrics["work_minutes"] > 0
    assert result.activity_metrics["sleep_minutes"] > 0
    assert result.activity_metrics["leisure_minutes"] > 0
    assert result.activity_metrics["meal_count"] == 1
    assert result.unique_activity_types == 6
    assert any(tick.active_activity == "WORK" and tick.decision_step_index is None for tick in result.ticks)
    assert validate_daily_trajectory(result)
    assert any(tick.completion_events for tick in result.ticks)
    assert len(list((tmp_path / "episodes").glob("episode_*.json"))) == 1
    assert len(list((tmp_path / "daily_episodes").glob("episode_*.json"))) == 1


def test_pathological_buy_loop_is_counted_and_terminated(tmp_path) -> None:
    client = PathologicalBuyAtHomeClient()
    result = asyncio.run(DailyEpisodeRunner(client, output_dir=tmp_path).run_episode(1))
    assert result.termination_reason is DailyTerminationReason.BEHAVIOR_LOOP
    assert result.decision_count == 5
    assert result.provider_request_count == 0
    assert result.trajectory.rejected_actions == 5
    assert result.idle_metrics["idle_minutes"] >= 30
    assert result.idle_metrics["repeated_invalid_count"] >= 1
    assert result.idle_metrics["behavior_loop_count"] >= 1
    assert "INVALID_LOOP" in result.failure_taxonomy
    assert validate_daily_trajectory(result)


def test_daily_validator_detects_non_deterministic_tick(tmp_path) -> None:
    result = asyncio.run(DailyEpisodeRunner(
        ScriptedNormalDayClient(), output_dir=tmp_path, write_artifacts=False,
    ).run_episode(1))
    tick = result.ticks[0]
    changed = dict(tick.world_after)
    people = dict(changed["people"])
    person = dict(people["1"])
    person["hunger"] = 0.99
    people["1"] = person
    changed["people"] = people
    damaged = replace(result, ticks=(replace(tick, world_after=changed),) + result.ticks[1:])
    with pytest.raises(ValueError, match="deterministic replay"):
        validate_daily_trajectory(damaged)


def test_provider_error_before_first_tick_has_no_idle_observation(tmp_path) -> None:
    class FailingClient:
        provider_request_count = 0

        async def complete(self, system_prompt, user_prompt):
            self.provider_request_count += 1
            raise DecisionClientError("unavailable")

    result = asyncio.run(DailyEpisodeRunner(
        FailingClient(), output_dir=tmp_path, write_artifacts=False,
    ).run_episode(1))
    assert result.termination_reason is DailyTerminationReason.PROVIDER_ERROR
    assert result.simulated_minutes == 0
    assert result.provider_request_count == 1
    assert "NO_ACTION" not in result.failure_taxonomy
    summary = summarize_daily_episodes([result])
    assert summary["day_rows"][0]["idle_ratio"] is None
    assert summary["aggregate"]["avg_idle_ratio"] is None
    paths = write_daily_report(tmp_path / "report", [result], provider_alias="fake")
    markdown = paths["summary_markdown"].read_text(encoding="utf-8")
    assert "| 1 | PROVIDER_ERROR | N/A |" in markdown
    assert "Average idle ratio: N/A" in markdown
