"""Deterministic Phase 8A prelude variants over the frozen lunch world.

The prelude is scenario setup, not model behavior: it uses the existing
ActionExecutor, never makes a decision request, and never enters trajectory
steps or model decision counts.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from social_sim.actions import ActionIntent
from social_sim.decision import ActionType
from social_sim.events import EventLog
from social_sim.execution import ActionExecutor
from social_sim.world import WorldState

from .models import event_snapshot, world_snapshot


class ScenarioVariant(str, Enum):
    S0_BASELINE = "S0_BASELINE"
    S1_LAST_REJECTION = "S1_LAST_REJECTION"
    S2_BURIED_REJECTION = "S2_BURIED_REJECTION"
    S3_NOISE_ONLY = "S3_NOISE_ONLY"


SCENARIO_VARIANTS = tuple(ScenarioVariant)

_REJECT_BUY = (ActionType.BUY, "meal")
_MOVE_PARK = (ActionType.MOVE, "park")
_MOVE_HOME = (ActionType.MOVE, "home")
_PRELUDE_ACTIONS: dict[ScenarioVariant, tuple[tuple[ActionType, str], ...]] = {
    ScenarioVariant.S0_BASELINE: (),
    ScenarioVariant.S1_LAST_REJECTION: (_REJECT_BUY,),
    ScenarioVariant.S2_BURIED_REJECTION: (
        _REJECT_BUY, _MOVE_PARK, _MOVE_HOME, _MOVE_PARK, _MOVE_HOME,
    ),
    ScenarioVariant.S3_NOISE_ONLY: (
        _MOVE_PARK, _MOVE_HOME, _MOVE_PARK, _MOVE_HOME,
    ),
}


@dataclass(frozen=True)
class PreludeSetup:
    """Fresh model-start world/log plus separate, audit-ready setup metadata."""

    variant: ScenarioVariant
    world: WorldState
    event_log: EventLog
    prelude_events: tuple[dict[str, object], ...]
    prelude_action_count: int
    prelude_rejection_count: int
    model_start_state: dict[str, object]

    @property
    def prelude_rejection_present(self) -> bool:
        return self.prelude_rejection_count > 0

    def metadata(self) -> dict[str, object]:
        """Return only JSON-friendly prelude facts, not mutable runtime objects."""
        return {
            "scenario_variant": self.variant.value,
            "prelude_events": [dict(event) for event in self.prelude_events],
            "prelude_action_count": self.prelude_action_count,
            "prelude_rejection_count": self.prelude_rejection_count,
            "prelude_rejection_present": self.prelude_rejection_present,
            "model_start_state": world_snapshot(self.world),
        }


def prepare_ablation_scenario(
    variant: ScenarioVariant | str,
    *,
    initial_world_factory: Callable[[], WorldState] | None = None,
) -> PreludeSetup:
    """Run a fixed prelude, then assert the model-start state stayed identical.

    Every call creates a fresh WorldState and EventLog. The returned log includes
    prelude events, which the injected ContextPolicy may select from later.
    """
    variant = ScenarioVariant(variant)
    if initial_world_factory is None:
        # Lazy import lets EpisodeRunner import this module without a cycle.
        from .runner import lunch_initial_world

        initial_world_factory = lunch_initial_world
    world = initial_world_factory()
    if not isinstance(world, WorldState):
        raise TypeError("initial_world_factory must return WorldState")
    initial_state = world_snapshot(world)
    event_log = EventLog()
    executor = ActionExecutor()
    prelude_events: list[dict[str, object]] = []
    rejection_count = 0

    for action, target in _PRELUDE_ACTIONS[variant]:
        intent = ActionIntent(
            actor_id=1,
            action=action,
            target=target,
            params={"quantity": 1} if action is ActionType.BUY else {},
        )
        outcome = executor.execute(world, intent, event_id=event_log.next_event_id())
        if len(outcome.events) != 1:
            raise RuntimeError("A prelude action must emit exactly one event")
        event = outcome.events[0]
        if action is ActionType.BUY and (outcome.allowed or outcome.reason_code != "NOT_AT_SELLER"):
            raise RuntimeError("Prelude BUY at home must reject with NOT_AT_SELLER")
        if action is ActionType.MOVE and not outcome.allowed:
            raise RuntimeError("Prelude MOVE must be accepted")
        event_log.append(event)
        prelude_events.append(event_snapshot(event))
        rejection_count += not outcome.allowed
        world = outcome.new_world

    final_state = world_snapshot(world)
    if final_state != initial_state:
        raise RuntimeError("Scenario prelude changed the model-start WorldState")
    return PreludeSetup(
        variant=variant,
        world=world,
        event_log=event_log,
        prelude_events=tuple(prelude_events),
        prelude_action_count=len(_PRELUDE_ACTIONS[variant]),
        prelude_rejection_count=rejection_count,
        model_start_state=final_state,
    )
