"""MOVE preconditions and effect declaration without world mutation."""

from __future__ import annotations

from social_sim.actions.models import ActionIntent
from social_sim.decision.models import ActionType
from social_sim.effects.models import MoveEffect
from social_sim.rules.base import ReasonCode, RuleResult
from social_sim.world.state import WorldState


class MoveRule:
    action_type = ActionType.MOVE

    def evaluate(self, world: WorldState, intent: ActionIntent) -> RuleResult:
        if intent.action is not ActionType.MOVE:
            return self._reject(intent, ReasonCode.UNSUPPORTED_ACTION)

        person = world.people.get(intent.actor_id)
        if person is None:
            return self._reject(intent, ReasonCode.ACTOR_NOT_FOUND)

        target = intent.target
        if not isinstance(target, str) or not target.strip():
            return self._reject(intent, ReasonCode.MISSING_TARGET)
        if target not in world.locations:
            return self._reject(intent, ReasonCode.UNKNOWN_DESTINATION)
        if target == person.location:
            return self._reject(intent, ReasonCode.ALREADY_AT_DESTINATION)

        return RuleResult(
            actor_id=intent.actor_id,
            action=intent.action,
            allowed=True,
            reason_code=ReasonCode.ACCEPTED,
            effects=(
                MoveEffect(
                    agent_id=intent.actor_id,
                    from_location=person.location,
                    to_location=target,
                ),
            ),
        )

    @staticmethod
    def _reject(intent: ActionIntent, reason_code: ReasonCode) -> RuleResult:
        return RuleResult(
            actor_id=intent.actor_id,
            action=intent.action,
            allowed=False,
            reason_code=reason_code,
        )
