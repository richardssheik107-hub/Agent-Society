"""Minimal location/time preconditions for three timed activities."""

from __future__ import annotations

from datetime import timedelta

from social_sim.actions.models import ActionIntent
from social_sim.daily.time import (
    ACTIVITY_DURATIONS_MINUTES, WORK_END, WORK_START,
)
from social_sim.decision.models import ActionType
from social_sim.effects.models import StartActivityEffect
from social_sim.rules.base import ReasonCode, RuleResult
from social_sim.world.state import WorldState


class ActivityRule:
    def __init__(self, action_type: ActionType) -> None:
        if action_type not in ACTIVITY_DURATIONS_MINUTES:
            raise ValueError("ActivityRule needs SLEEP, WORK, or LEISURE")
        self.action_type = action_type

    def evaluate(self, world: WorldState, intent: ActionIntent) -> RuleResult:
        if intent.action is not self.action_type:
            return self._reject(intent, ReasonCode.UNSUPPORTED_ACTION)
        person = world.people.get(intent.actor_id)
        if person is None:
            return self._reject(intent, ReasonCode.ACTOR_NOT_FOUND)
        if person.activity is not None:
            return self._reject(intent, ReasonCode.ACTIVITY_IN_PROGRESS)
        if self.action_type is ActionType.WORK:
            if person.location != "office":
                return self._reject(intent, ReasonCode.NOT_AT_ACTIVITY_LOCATION)
            if not WORK_START <= world.time.strftime("%H:%M") < WORK_END:
                return self._reject(intent, ReasonCode.OUTSIDE_WORK_WINDOW)
        elif self.action_type is ActionType.SLEEP:
            if person.location != "home":
                return self._reject(intent, ReasonCode.NOT_AT_ACTIVITY_LOCATION)
        elif person.location not in ("home", "park"):
            return self._reject(intent, ReasonCode.NOT_AT_ACTIVITY_LOCATION)
        return RuleResult(
            actor_id=intent.actor_id,
            action=intent.action,
            allowed=True,
            reason_code=ReasonCode.ACCEPTED,
            effects=(StartActivityEffect(
                agent_id=intent.actor_id,
                action=intent.action,
                expected_location=person.location,
                expected_time=world.time.isoformat(),
                end_time=(
                    world.time + timedelta(minutes=ACTIVITY_DURATIONS_MINUTES[intent.action])
                ).isoformat(),
            ),),
        )

    @staticmethod
    def _reject(intent: ActionIntent, reason_code: ReasonCode) -> RuleResult:
        return RuleResult(
            actor_id=intent.actor_id,
            action=intent.action,
            allowed=False,
            reason_code=reason_code,
        )
