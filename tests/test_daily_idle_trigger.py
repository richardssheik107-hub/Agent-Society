"""Network-free A1 trigger and idle detector tests."""

from datetime import datetime, timedelta
import json

import pytest

from social_sim.daily import DecisionTrigger, IdleDetector, IdleTick


CORE = ("home", None, 100.0, (), 0.3, 0.8)


def tick(n: int, **overrides: object) -> IdleTick:
    facts = {"time_minute": 360 + 15 * n, "state_before": CORE, "state_after": CORE, "hunger": 0.3}
    facts.update(overrides)
    return IdleTick(**facts)


def test_trigger_suppresses_active_activity_and_resumes_at_completion() -> None:
    start = datetime(2026, 9, 17, 6)
    end = start + timedelta(hours=1)
    trigger = DecisionTrigger()
    assert not trigger.should_decide(start, "WORK", end.isoformat())
    assert not trigger.should_decide(start + timedelta(minutes=45), "WORK", end)
    assert trigger.should_decide(end, "WORK", end.isoformat())
    assert trigger.should_decide(start, None, None)
    assert trigger.should_decide(start, "WORK", end, rejected=True)
    assert trigger.should_decide(start, "WORK", end, world_event_interrupt=True)
    # In A1, a schedule boundary alone does not interrupt an active activity.
    assert not trigger.should_decide(start, "WORK", end, obligation_boundary=True)


def test_trigger_accepts_integer_simulation_minutes_without_wall_clock() -> None:
    trigger = DecisionTrigger()
    assert not trigger.should_decide(360, "SLEEP", 375)
    assert trigger.should_decide(375, "SLEEP", 375)
    with pytest.raises(TypeError):
        trigger.should_decide(360, "SLEEP", datetime(2026, 9, 17, 6, 15))


def test_two_15_minute_no_activity_ticks_count_whole_idle_episode() -> None:
    detector = IdleDetector()
    assert detector.record_tick(tick(0)).idle_minutes == 0
    summary = detector.record_tick(tick(1))
    assert summary.observed_minutes == 30
    assert summary.idle_minutes == summary.max_idle_streak_minutes == 30
    assert summary.idle_ratio == 1
    assert summary.idle_episode_count == 1
    assert "IDLE_NO_ACTIVITY" in summary.flags
    assert summary.to_dict()["idle_minutes"] == 30
    assert json.loads(json.dumps(summary.to_dict()))["flags"] == ["IDLE_NO_ACTIVITY"]


@pytest.mark.parametrize("activity", ("WORK", "SLEEP", "LEISURE"))
def test_sustained_valid_activity_is_not_idle_or_stalled(activity: str) -> None:
    detector = IdleDetector()
    for i in range(6):
        detector.record_tick(tick(i, activity=activity))
    summary = detector.summary()
    assert summary.idle_minutes == 0
    assert summary.stalled_state_minutes == 0
    assert summary.flags == ()


def test_valid_instantaneous_action_breaks_idle_streak() -> None:
    detector = IdleDetector()
    detector.record_tick(tick(0))
    detector.record_tick(tick(1, valid_activity_started=True, action="MOVE", action_accepted=True))
    detector.record_tick(tick(2))
    assert detector.summary().idle_episode_count == 0
    assert detector.summary().idle_minutes == 0


def test_repeated_rejected_buy_and_behavior_loop_are_detected() -> None:
    detector = IdleDetector()
    for i in range(3):
        detector.record_tick(tick(
            i, action="BUY", target="meal", rejection_reason="NOT_AT_SELLER",
            action_accepted=False,
            # Needs may drift while the rejection itself leaves state unchanged.
            state_after=("home", None, 100.0, (), 0.3 + 0.01 * i, 0.8),
        ))
    summary = detector.summary()
    assert summary.repeated_invalid_count == 2
    assert summary.current_repeated_invalid_streak == 3
    assert summary.max_repeated_invalid_streak == 3
    assert summary.behavior_loop_count == 1
    assert "REPEATED_INVALID_ACTION" in summary.flags
    assert "REPEATED_SAME_ACTION_NO_PROGRESS" in summary.flags


def test_different_target_or_reason_breaks_rejected_action_streak() -> None:
    detector = IdleDetector()
    detector.record_tick(tick(0, action="BUY", target="meal", rejection_reason="NOT_AT_SELLER", action_accepted=False))
    detector.record_tick(tick(1, action="BUY", target="water", rejection_reason="NOT_AT_SELLER", action_accepted=False))
    detector.record_tick(tick(2, action="BUY", target="water", rejection_reason="OUT_OF_STOCK", action_accepted=False))
    assert detector.summary().repeated_invalid_count == 0
    assert detector.summary().current_repeated_invalid_streak == 1


def test_different_targets_do_not_form_identical_proposal_loop() -> None:
    detector = IdleDetector()
    for index, target in enumerate(("meal", "water", "bread")):
        detector.record_tick(tick(
            index, action="BUY", target=target,
            rejection_reason="NOT_AT_SELLER", action_accepted=False,
        ))
    assert detector.summary().behavior_loop_count == 0


def test_high_hunger_without_effective_food_action_is_unresolved_after_90_minutes() -> None:
    detector = IdleDetector()
    for i in range(6):
        summary = detector.record_tick(tick(i, hunger=0.85))
    assert summary.unresolved_need_minutes == 90
    assert "UNRESOLVED_NEED" in summary.flags
    detector.record_tick(tick(6, hunger=0.9, food_progress=True, action="EAT", action_accepted=True))
    assert detector.summary().unresolved_need_minutes == 90


def test_unchanged_core_state_without_activity_is_stalled_after_60_minutes() -> None:
    detector = IdleDetector()
    for i in range(4):
        summary = detector.record_tick(tick(i))
    assert summary.stalled_state_minutes == 60
    assert "STALLED_STATE" in summary.flags


def test_15_minute_intervals_must_be_contiguous() -> None:
    detector = IdleDetector()
    detector.record_tick(tick(0))
    with pytest.raises(ValueError, match="contiguous"):
        detector.record_tick(tick(2))
    with pytest.raises(ValueError, match="15 simulation minutes"):
        IdleTick(time_minute=360, duration_minutes=10)
