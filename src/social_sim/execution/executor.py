"""Thin deterministic action execution boundary."""

from __future__ import annotations

from dataclasses import dataclass

from social_sim.actions.models import ActionIntent
from social_sim.effects.models import Effect
from social_sim.events import DomainEvent, EventType
from social_sim.reducer import StateReducer
from social_sim.rules import RuleEngine
from social_sim.world.state import WorldState


@dataclass(frozen=True)
class ExecutionOutcome:
    intent: ActionIntent
    allowed: bool
    reason_code: str
    effects: tuple[Effect, ...]
    events: tuple[DomainEvent, ...]
    new_world: WorldState


class ActionExecutor:
    """Evaluate an intent, reduce approved effects, then describe the result."""

    _SUCCESS_EVENTS = {
        "MOVE": EventType.MOVED,
        "BUY": EventType.PURCHASED,
        "EAT": EventType.ATE,
    }

    def __init__(
        self,
        rule_engine: RuleEngine | None = None,
        reducer: StateReducer | None = None,
    ) -> None:
        self._rule_engine = rule_engine if rule_engine is not None else RuleEngine()
        self._reducer = reducer if reducer is not None else StateReducer()

    def execute(
        self, world: WorldState, intent: ActionIntent, *, event_id: str
    ) -> ExecutionOutcome:
        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("event_id must be a nonempty string")
        judgment = self._rule_engine.evaluate(world, intent)
        reason_code = judgment.reason_code.value
        if not judgment.allowed:
            event = DomainEvent(
                event_id=event_id,
                actor_id=intent.actor_id,
                event_type=EventType.ACTION_REJECTED,
                action=intent.action,
                target=intent.target,
                success=False,
                reason_code=reason_code,
            )
            return ExecutionOutcome(
                intent=intent,
                allowed=False,
                reason_code=reason_code,
                effects=(),
                events=(event,),
                new_world=world,
            )

        event_type = self._SUCCESS_EVENTS.get(intent.action.value)
        if event_type is None:
            raise ValueError(f"No event type for accepted action: {intent.action.value}")
        new_world = self._reducer.apply(world, judgment.effects)
        event = DomainEvent(
            event_id=event_id,
            actor_id=intent.actor_id,
            event_type=event_type,
            action=intent.action,
            target=intent.target,
            success=True,
            reason_code=reason_code,
        )
        return ExecutionOutcome(
            intent=intent,
            allowed=True,
            reason_code=reason_code,
            effects=judgment.effects,
            events=(event,),
            new_world=new_world,
        )
