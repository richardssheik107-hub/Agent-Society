"""Pure-Python, 15-minute idle and behavioral-stagnation measurements.

All thresholds here are uncalibrated benchmark mechanics. A qualifying streak
counts *all* of its elapsed minutes once it reaches the threshold, not only the
minutes above the threshold. Repeated invalid actions count extra repetitions
beyond the first rejected action; a behavior loop counts once per streak.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any


TICK_MINUTES = 15
IDLE_NO_ACTIVITY_MINUTES = 30
UNRESOLVED_NEED_MINUTES = 90
STALLED_STATE_MINUTES = 60
HUNGER_HIGH_THRESHOLD = 0.8
DEFAULT_BEHAVIOR_LOOP_ACTIONS = 3


@dataclass(frozen=True)
class IdleTick:
    """Facts for one completed simulation interval, beginning at ``time_minute``.

    ``state_before``/``state_after`` should contain only the core person state
    (location, activity, money, inventory, hunger, energy), not simulation time.
    ``action_state_unchanged`` may describe the *instantaneous* action outcome;
    this avoids treating deterministic needs drift during the tick as progress
    from an otherwise rejected action.
    """

    time_minute: int
    activity: str | None = None
    valid_activity_started: bool = False
    state_before: Any = None
    state_after: Any = None
    hunger: float | None = None
    food_progress: bool = False
    action: str | None = None
    target: str | None = None
    rejection_reason: str | None = None
    action_accepted: bool | None = None
    goal_progress: bool = False
    action_state_unchanged: bool | None = None
    duration_minutes: int = TICK_MINUTES

    def __post_init__(self) -> None:
        if isinstance(self.time_minute, bool) or not isinstance(self.time_minute, int) or self.time_minute < 0:
            raise ValueError("time_minute must be a non-negative integer")
        if self.duration_minutes != TICK_MINUTES or isinstance(self.duration_minutes, bool):
            raise ValueError("daily idle ticks must span exactly 15 simulation minutes")
        if self.hunger is not None and (
            isinstance(self.hunger, bool)
            or not isinstance(self.hunger, (int, float))
            or not math.isfinite(self.hunger)
            or not 0 <= self.hunger <= 1
        ):
            raise ValueError("hunger must be in [0, 1] or None")
        if self.activity is not None and not isinstance(self.activity, str):
            raise TypeError("activity must be a string or None")
        if self.action is not None and not isinstance(self.action, str):
            raise TypeError("action must be a string or None")
        if self.target is not None and not isinstance(self.target, str):
            raise TypeError("target must be a string or None")
        if self.rejection_reason is not None and not isinstance(self.rejection_reason, str):
            raise TypeError("rejection_reason must be a string or None")
        if self.action_accepted is not None and not isinstance(self.action_accepted, bool):
            raise TypeError("action_accepted must be a boolean or None")
        if self.rejection_reason and self.action_accepted is True:
            raise ValueError("an accepted action cannot have a rejection_reason")
        if self.action_state_unchanged is not None and not isinstance(self.action_state_unchanged, bool):
            raise TypeError("action_state_unchanged must be a boolean or None")

    @property
    def state_unchanged(self) -> bool:
        return (
            self.state_before is not None
            and self.state_after is not None
            and self.state_before == self.state_after
        )

    @property
    def action_unchanged(self) -> bool:
        if self.action_state_unchanged is not None:
            return self.action_state_unchanged
        if self.rejection_reason and self.action_accepted is False:
            # Rules reject without effects. Needs can still drift over the tick.
            return True
        return self.state_unchanged


@dataclass(frozen=True)
class IdleSummary:
    observed_minutes: int
    tick_count: int
    idle_minutes: int
    idle_ratio: float
    max_idle_streak_minutes: int
    idle_episode_count: int
    repeated_invalid_count: int
    behavior_loop_count: int
    unresolved_need_minutes: int
    stalled_state_minutes: int
    current_repeated_invalid_streak: int
    max_repeated_invalid_streak: int
    flags: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["flags"] = list(self.flags)
        return result


class IdleDetector:
    """Record sequential ticks and compute objective, model-free idle metrics."""

    def __init__(self, *, behavior_loop_actions: int = DEFAULT_BEHAVIOR_LOOP_ACTIONS) -> None:
        if isinstance(behavior_loop_actions, bool) or not isinstance(behavior_loop_actions, int) or behavior_loop_actions < 2:
            raise ValueError("behavior_loop_actions must be an integer >= 2")
        self.behavior_loop_actions = behavior_loop_actions
        self._ticks: list[IdleTick] = []

    @property
    def ticks(self) -> tuple[IdleTick, ...]:
        return tuple(self._ticks)

    def record_tick(self, tick: IdleTick) -> IdleSummary:
        if not isinstance(tick, IdleTick):
            raise TypeError("tick must be an IdleTick")
        if self._ticks and tick.time_minute != self._ticks[-1].time_minute + TICK_MINUTES:
            raise ValueError("idle ticks must be contiguous 15-minute intervals")
        self._ticks.append(tick)
        return self.summary()

    def summary(self) -> IdleSummary:
        idle_minutes = 0
        idle_episodes = 0
        max_idle_streak = 0
        no_activity_streak = 0
        unresolved_minutes = 0
        high_hunger_streak = 0
        stalled_minutes = 0
        unchanged_streak = 0
        repeated_invalid = 0
        invalid_signature: tuple[str, str | None, str] | None = None
        invalid_streak = 0
        max_invalid_streak = 0
        behavior_loops = 0
        no_progress_action: tuple[str, str | None] | None = None
        no_progress_streak = 0

        def finish_no_activity() -> None:
            nonlocal idle_minutes, idle_episodes, max_idle_streak, no_activity_streak
            if no_activity_streak >= IDLE_NO_ACTIVITY_MINUTES:
                idle_minutes += no_activity_streak
                idle_episodes += 1
                max_idle_streak = max(max_idle_streak, no_activity_streak)
            no_activity_streak = 0

        def finish_high_hunger() -> None:
            nonlocal unresolved_minutes, high_hunger_streak
            if high_hunger_streak >= UNRESOLVED_NEED_MINUTES:
                unresolved_minutes += high_hunger_streak
            high_hunger_streak = 0

        def finish_unchanged() -> None:
            nonlocal stalled_minutes, unchanged_streak
            if unchanged_streak >= STALLED_STATE_MINUTES:
                stalled_minutes += unchanged_streak
            unchanged_streak = 0

        for tick in self._ticks:
            active = bool(tick.activity)
            meaningful_progress = tick.goal_progress or tick.valid_activity_started

            if not active and not tick.valid_activity_started:
                no_activity_streak += tick.duration_minutes
            else:
                finish_no_activity()

            if tick.hunger is not None and tick.hunger >= HUNGER_HIGH_THRESHOLD and not tick.food_progress:
                high_hunger_streak += tick.duration_minutes
            else:
                finish_high_hunger()

            if not active and not meaningful_progress and tick.state_unchanged:
                unchanged_streak += tick.duration_minutes
            else:
                finish_unchanged()

            action = tick.action.upper() if tick.action else None
            reason = tick.rejection_reason
            if action is not None:
                signature = (action, tick.target, reason) if reason else None
                if signature is not None and tick.action_unchanged:
                    invalid_streak = invalid_streak + 1 if signature == invalid_signature else 1
                    if invalid_streak >= 2:
                        repeated_invalid += 1
                    invalid_signature = signature
                    max_invalid_streak = max(max_invalid_streak, invalid_streak)
                else:
                    invalid_signature = None
                    invalid_streak = 0

                if tick.action_unchanged and not meaningful_progress:
                    proposal = (action, tick.target)
                    no_progress_streak = no_progress_streak + 1 if proposal == no_progress_action else 1
                    if no_progress_streak == self.behavior_loop_actions:
                        behavior_loops += 1
                    no_progress_action = proposal
                else:
                    no_progress_action = None
                    no_progress_streak = 0
            elif active or meaningful_progress or not tick.state_unchanged:
                invalid_signature = None
                invalid_streak = 0
                no_progress_action = None
                no_progress_streak = 0

        finish_no_activity()
        finish_high_hunger()
        finish_unchanged()
        observed = len(self._ticks) * TICK_MINUTES
        flags = tuple(name for condition, name in (
            (idle_episodes > 0, "IDLE_NO_ACTIVITY"),
            (repeated_invalid > 0, "REPEATED_INVALID_ACTION"),
            (behavior_loops > 0, "REPEATED_SAME_ACTION_NO_PROGRESS"),
            (unresolved_minutes > 0, "UNRESOLVED_NEED"),
            (stalled_minutes > 0, "STALLED_STATE"),
        ) if condition)
        return IdleSummary(
            observed_minutes=observed,
            tick_count=len(self._ticks),
            idle_minutes=idle_minutes,
            idle_ratio=idle_minutes / observed if observed else 0.0,
            max_idle_streak_minutes=max_idle_streak,
            idle_episode_count=idle_episodes,
            repeated_invalid_count=repeated_invalid,
            behavior_loop_count=behavior_loops,
            unresolved_need_minutes=unresolved_minutes,
            stalled_state_minutes=stalled_minutes,
            current_repeated_invalid_streak=invalid_streak,
            max_repeated_invalid_streak=max_invalid_streak,
            flags=flags,
        )
