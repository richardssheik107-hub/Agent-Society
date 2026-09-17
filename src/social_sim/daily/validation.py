"""Validate the tick timeline that bridges consecutive model decisions."""

from __future__ import annotations

from datetime import datetime, timedelta

from social_sim.evaluation.models import world_snapshot
from social_sim.evaluation.validation import validate_trajectory
from social_sim.world import OfferState, PersonWorldState, WorldState

from .models import DayOutcome, DailyEpisodeResult, DailyTerminationReason
from .time import advance_daily_tick


def _world_from_snapshot(snapshot: dict[str, object]) -> WorldState:
    """Rebuild only objective state so replay checks the actual tick reducer."""
    people = {
        int(agent_id): PersonWorldState(
            agent_id=int(agent_id),
            location=person["location"],
            money=person["money"],
            hunger=person["hunger"],
            inventory=person["inventory"],
            energy=person.get("energy"),
            activity=person.get("activity"),
            activity_end_time=person.get("activity_end_time"),
        )
        for agent_id, person in snapshot["people"].items()
    }
    venues = {
        location: {
            item_id: OfferState(item_id, offer["price"], offer["stock"])
            for item_id, offer in offers.items()
        }
        for location, offers in snapshot["venues"].items()
    }
    return WorldState(
        time=datetime.fromisoformat(snapshot["time"]), people=people,
        locations=snapshot["locations"], venues=venues,
    )


def validate_daily_trajectory(result: DailyEpisodeResult) -> bool:
    """Check 15-minute tick and decision continuity without an evaluator model."""
    if not isinstance(result, DailyEpisodeResult):
        raise TypeError("result must be DailyEpisodeResult")
    validate_trajectory(result.trajectory)
    steps = result.trajectory.steps
    tick_steps = []
    seen_event_ids = {step.event["event_id"] for step in steps}
    previous = None
    for index, tick in enumerate(result.ticks, start=1):
        if tick.tick_index != index:
            raise ValueError("daily tick indices must start at 1 and be contiguous")
        start = datetime.fromisoformat(tick.simulation_time)
        end = datetime.fromisoformat(tick.end_time)
        if end - start != timedelta(minutes=15):
            raise ValueError("daily ticks must advance by exactly 15 minutes")
        if tick.world_before.get("time") != tick.simulation_time:
            raise ValueError("tick world_before time disagrees with simulation_time")
        if tick.world_after_decision.get("time") != tick.simulation_time:
            raise ValueError("decisions cannot advance simulation time")
        if tick.world_after.get("time") != tick.end_time:
            raise ValueError("tick world_after time disagrees with end_time")
        replayed, completions = advance_daily_tick(_world_from_snapshot(tick.world_after_decision))
        if world_snapshot(replayed) != tick.world_after:
            raise ValueError("daily tick world_after differs from deterministic replay")
        if tick.completed_activities != tuple(action.value for _, action in completions):
            raise ValueError("daily completion activities differ from deterministic replay")
        if len(tick.completion_events) != len(completions):
            raise ValueError("daily completion event count disagrees with replay")
        for event, (actor_id, action) in zip(tick.completion_events, completions):
            if (
                event.get("actor_id") != actor_id
                or event.get("action") != action.value
                or event.get("event_type") != f"{action.value}_COMPLETED"
                or event.get("success") is not True
                or event.get("reason_code") != "ACCEPTED"
            ):
                raise ValueError("daily completion event differs from deterministic replay")
            event_id = event.get("event_id")
            if not isinstance(event_id, str) or not event_id or event_id in seen_event_ids:
                raise ValueError("daily completion event ID missing or repeated")
            seen_event_ids.add(event_id)
        if previous is not None and tick.world_before != previous.world_after:
            raise ValueError("daily world continuity broken between ticks")
        before_person = tick.world_before["people"]["1"]
        active_end = before_person.get("activity_end_time")
        if (
            before_person.get("activity") is not None
            and active_end is not None
            and datetime.fromisoformat(active_end) > start
            and tick.decision_step_index is not None
        ):
            raise ValueError("model called during an active activity")
        if tick.decision_step_index is None:
            if tick.world_after_decision != tick.world_before:
                raise ValueError("world changed before a tick without a decision")
            if tick.trigger_reason is not None:
                raise ValueError("tick without a decision cannot have a trigger reason")
        else:
            if tick.decision_step_index < 1 or tick.decision_step_index > len(steps):
                raise ValueError("daily tick references an unknown model step")
            step = steps[tick.decision_step_index - 1]
            if step.state_before != tick.world_before:
                raise ValueError("model step state_before differs from daily tick")
            if step.state_after != tick.world_after_decision:
                raise ValueError("model step state_after differs from daily tick")
            if step.simulation_time != tick.simulation_time:
                raise ValueError("model step simulation_time differs from daily tick")
            if step.trigger_reason != tick.trigger_reason or not tick.trigger_reason:
                raise ValueError("model step trigger reason differs from daily tick")
            tick_steps.append(tick.decision_step_index)
        previous = tick
    if tick_steps != list(range(1, len(steps) + 1)):
        raise ValueError("daily ticks do not reference all model steps exactly once")
    final = result.ticks[-1].world_after if result.ticks else result.trajectory.final_state
    if result.trajectory.final_state != final:
        raise ValueError("daily final_state does not match final tick")
    if result.simulated_minutes != 15 * len(result.ticks):
        raise ValueError("simulated minutes do not match ticks")
    if result.observed_minutes != result.simulated_minutes or result.observed_ticks != len(result.ticks):
        raise ValueError("observed window must equal completed ticks")
    completed = result.termination_reason is DailyTerminationReason.DAY_END
    if result.day_completed is not completed or result.behavior_metrics_valid is not completed:
        raise ValueError("behavior metrics are valid only for a completed day")
    expected_outcome = (
        DayOutcome.DAY_COMPLETED if completed else
        DayOutcome.DAY_TRUNCATED_PROVIDER if result.termination_reason in (
            DailyTerminationReason.PROVIDER_ERROR, DailyTerminationReason.TIMEOUT,
        ) else
        DayOutcome.DAY_TRUNCATED_MODEL_OUTPUT if result.termination_reason is DailyTerminationReason.INVALID_MODEL_OUTPUT else
        DayOutcome.DAY_TRUNCATED_ARCHITECTURE if result.termination_reason is DailyTerminationReason.ARCHITECTURE_ERROR else
        DayOutcome.DAY_TRUNCATED_BEHAVIOR
    )
    if result.day_outcome is not expected_outcome:
        raise ValueError("daily outcome disagrees with termination")
    if completed:
        if result.truncation_reason is not None or result.full_day_behavior_metrics is None or result.partial_window_metrics is not None:
            raise ValueError("completed day must have full-day metrics only")
        expected_full = {
            "idle_ratio": result.idle_metrics["idle_ratio"],
            "idle_minutes": result.idle_metrics["idle_minutes"],
            "max_idle_streak_minutes": result.idle_metrics["max_idle_streak_minutes"],
            "unique_activity_types": result.unique_activity_types,
            "repeated_invalid_count": result.idle_metrics["repeated_invalid_count"],
            "unresolved_need_minutes": result.idle_metrics["unresolved_need_minutes"],
            "sleep_minutes": result.activity_metrics["sleep_minutes"],
            "work_minutes": result.activity_metrics["work_minutes"],
            "leisure_minutes": result.activity_metrics["leisure_minutes"],
            "meal_count": result.activity_metrics["meal_count"],
            "activity_counts": result.activity_counts,
        }
        if result.full_day_behavior_metrics != expected_full:
            raise ValueError("full-day metrics disagree with completed episode")
    else:
        if result.truncation_reason != expected_outcome.value or result.full_day_behavior_metrics is not None:
            raise ValueError("truncated day cannot have full-day metrics")
        partial = result.partial_window_metrics
        expected_partial = {
            "observed_minutes": result.observed_minutes,
            "observed_ticks": result.observed_ticks,
            "partial_idle_minutes": result.idle_metrics["idle_minutes"],
            "partial_idle_ratio": (
                result.idle_metrics["idle_ratio"] if result.observed_ticks else None
            ),
            "partial_activity_counts": result.activity_counts,
            "partial_decisions": result.decision_count,
        }
        if partial != expected_partial:
            raise ValueError("truncated day must have matching partial metrics")
    if result.day_outcome is DayOutcome.DAY_TRUNCATED_PROVIDER and len(result.provider_failures) != 1:
        raise ValueError("provider-truncated day requires one failure record")
    if result.day_outcome is not DayOutcome.DAY_TRUNCATED_PROVIDER and result.provider_failures:
        raise ValueError("non-provider termination cannot carry provider failures")
    if result.termination_reason is DailyTerminationReason.INVALID_MODEL_OUTPUT:
        if len(result.output_failures) != 1:
            raise ValueError("model-output-truncated day requires one output failure record")
    elif result.output_failures:
        raise ValueError("non-model-output termination cannot carry output failures")
    if result.decision_count != result.trajectory.decision_count:
        raise ValueError("daily decision counts disagree")
    if result.provider_request_count != result.trajectory.total_provider_requests:
        raise ValueError("daily provider request counts disagree")
    if result.termination_reason is DailyTerminationReason.DAY_END:
        if len(result.ticks) != result.window_minutes // 15 or (
            result.window_minutes == 1080 and datetime.fromisoformat(final["time"]).hour != 0
        ):
            raise ValueError("DAY_END must complete the configured window")
    return True
