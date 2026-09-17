"""A1.1 decision spacing and trigger-reason evidence; no provider calls."""

import asyncio
from dataclasses import replace
from datetime import timedelta

import pytest

from social_sim.daily.runner import DailyEpisodeRunner, neutral_day_initial_world
from social_sim.daily.scripted import PathologicalBuyAtHomeClient, ScriptedNormalDayClient
from social_sim.daily.trigger import DecisionTrigger, TriggerReason
from social_sim.daily.trigger_audit import DecisionTriggerAudit
from social_sim.decision.client import DecisionClientError
from social_sim.world import WorldState


def _at(minute: int, *, hunger: float = 0.3, location: str = "home") -> WorldState:
    baseline = neutral_day_initial_world()
    person = replace(baseline.get_person(1), hunger=hunger, location=location)
    return WorldState(
        baseline.time + timedelta(minutes=minute),
        people={1: person}, locations=baseline.locations, venues=baseline.venues,
    )


def test_trigger_reason_precedence_and_non_preemptive_activity() -> None:
    trigger = DecisionTrigger()
    start = neutral_day_initial_world().time
    end = start + timedelta(minutes=90)
    for minute in range(0, 90, 15):
        assert trigger.reason(
            start + timedelta(minutes=minute), "WORK", end,
            obligation_boundary=True, critical_need=True,
        ) is None
    assert trigger.reason(end, "WORK", end) is TriggerReason.ACTIVITY_COMPLETED
    assert trigger.reason(end, None, None, activity_completed=True) is TriggerReason.ACTIVITY_COMPLETED
    assert trigger.reason(end, None, None, rejected=True) is TriggerReason.ACTION_REJECTED
    assert trigger.reason(end, None, None, critical_need=True) is TriggerReason.CRITICAL_NEED
    assert trigger.reason(end, None, None, obligation_boundary=True) is TriggerReason.OBLIGATION_BOUNDARY
    assert trigger.reason(end, None, None, world_event_interrupt=True) is TriggerReason.WORLD_EVENT
    assert trigger.reason(end, None, None) is TriggerReason.NO_ACTIVE_ACTIVITY


def test_audit_counts_attempts_bursts_same_state_and_efficiency() -> None:
    audit = DecisionTriggerAudit()
    for minute, location in ((0, "home"), (15, "home"), (30, "home"), (60, "office")):
        audit.record_decision(
            _at(minute, hunger=0.3 + minute / 1000, location=location).time,
            _at(minute, hunger=0.3 + minute / 1000, location=location),
            TriggerReason.NO_ACTIVE_ACTIVITY,
        )
    summary = audit.summary(observed_ticks=8, active_minutes=60)
    assert summary["decision_attempts"] == 4
    assert summary["decision_burst_count"] == 1
    assert summary["same_state_decision_count"] == 2
    assert summary["decisions_per_sim_hour"] == 2
    assert summary["ticks_per_decision"] == 2
    assert summary["active_minutes_per_decision"] == 15
    assert summary["trigger_reason_counts"]["NO_ACTIVE_ACTIVITY"] == 4
    assert not summary["high_decision_frequency_warning"]
    with pytest.raises(ValueError, match="advance"):
        audit.record_decision(_at(60).time, _at(60), TriggerReason.NO_ACTIVE_ACTIVITY)


def test_scripted_full_day_has_no_calls_during_activity_and_persists_reasons(tmp_path) -> None:
    client = ScriptedNormalDayClient()
    day = asyncio.run(DailyEpisodeRunner(
        client, output_dir=tmp_path, write_artifacts=False,
    ).run_episode(1))
    assert day.day_completed
    assert day.observed_ticks == 72
    assert day.provider_request_count == 0
    steps = day.trajectory.steps
    assert steps
    assert all(step.trigger_reason in TriggerReason._value2member_map_ for step in steps)
    assert all(step.to_dict()["trigger_reason"] == step.trigger_reason for step in steps)
    assert any(step.trigger_reason == "ACTIVITY_COMPLETED" for step in steps)
    assert all(
        tick.decision_step_index is None
        for tick in day.ticks
        if tick.world_before["people"]["1"].get("activity")
        and tick.world_before["people"]["1"].get("activity_end_time") > tick.simulation_time
    )
    work_starts = [step for step in steps if step.proposal["action"] == "WORK" and step.rule_allowed]
    assert work_starts
    first_work = work_starts[0]
    work_end = first_work.effects[0]["end_time"]
    assert not any(
        first_work.simulation_time < step.simulation_time < work_end
        for step in steps
    )
    activity_metrics = day.activity_metrics
    assert activity_metrics["decision_attempts"] == day.decision_count
    assert activity_metrics["decision_burst_count"] >= 0
    assert activity_metrics["same_state_decision_count"] >= 0
    assert activity_metrics["ticks_per_decision"] == 72 / day.decision_count


def test_rejected_action_persists_next_trigger_reason_and_burst(tmp_path) -> None:
    day = asyncio.run(DailyEpisodeRunner(
        PathologicalBuyAtHomeClient(), output_dir=tmp_path, write_artifacts=False,
    ).run_episode(1))
    steps = day.trajectory.steps
    assert len(steps) == 5
    assert steps[0].trigger_reason == "NO_ACTIVE_ACTIVITY"
    assert all(step.trigger_reason == "ACTION_REJECTED" for step in steps[1:])
    assert day.activity_metrics["decision_burst_count"] == 3
    assert day.activity_metrics["same_state_decision_count"] >= 3
    assert day.activity_metrics["trigger_reason_counts"]["ACTION_REJECTED"] == 4


def test_failed_first_provider_attempt_is_audited_without_fake_tick(tmp_path) -> None:
    class FailingClient:
        provider_request_count = 0

        async def complete(self, system_prompt, user_prompt):
            self.provider_request_count += 1
            raise DecisionClientError("offline failure")

    day = asyncio.run(DailyEpisodeRunner(
        FailingClient(), output_dir=tmp_path, write_artifacts=False,
    ).run_episode(1))
    assert day.observed_ticks == 0
    assert day.activity_metrics["decision_attempts"] == 1
    assert day.activity_metrics["trigger_reason_counts"]["NO_ACTIVE_ACTIVITY"] == 1
    assert day.activity_metrics["decisions_per_sim_hour"] is None
    assert day.activity_metrics["ticks_per_decision"] == 0
    assert not day.day_completed
