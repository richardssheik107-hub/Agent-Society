"""One-person domain orchestration; AgentSociety remains the simulation runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from social_sim.actions import ActionIntent, proposal_to_intent
from social_sim.decision import ActionType, CompactDecisionService, DecisionProposal
from social_sim.events import DomainEvent, EventLog
from social_sim.execution import ActionExecutor, ExecutionOutcome
from social_sim.world import LocalObservation, ObservationBuilder, WorldState


@dataclass(frozen=True)
class StepResult:
    proposal: DecisionProposal
    intent: ActionIntent
    outcome: ExecutionOutcome
    world_after: WorldState
    observation_before: LocalObservation
    context: str
    system_prompt: str
    user_prompt: str
    context_chars: int
    prompt_chars: int
    decision_latency_seconds: float
    input_tokens: int | None
    output_tokens: int | None
    raw_output_chars: int
    reasoning_tokens: int | None
    provider_model: str | None
    provider_request_count: int


class ClosedLoopStep:
    """One observation, one decision call, deterministic execution, then one event."""

    def __init__(
        self,
        decision_service: CompactDecisionService,
        event_log: EventLog,
        executor: ActionExecutor | None = None,
    ) -> None:
        self.decision_service = decision_service
        self.event_log = event_log
        self.executor = executor or ActionExecutor()

    async def run(
        self,
        world: WorldState,
        actor_id: int,
        profile: Mapping[str, object],
        *,
        available_actions: Sequence[ActionType] = (
            ActionType.MOVE,
            ActionType.BUY,
            ActionType.EAT,
        ),
        available_targets: Sequence[str] | None = None,
        daily_mode: bool = False,
        work_window: str | None = None,
        behavior_hints: Sequence[str] | None = None,
    ) -> StepResult:
        observation = ObservationBuilder(world).build(actor_id)
        # Explicit Phase 8A policies select from the full history. Preserve
        # Phase 7's bounded recent-three contract for the default service.
        actor_events = (
            event for event in self.event_log.all() if event.actor_id == actor_id
        )
        recent_events = tuple(event.compact() for event in actor_events)
        if not self.decision_service.accepts_full_event_history:
            recent_events = recent_events[-3:]
        target_ids = (
            tuple(available_targets)
            if available_targets is not None
            else tuple(
                sorted(
                    set(world.locations)
                    | {
                        item_id
                        for offers in world.venues.values()
                        for item_id in offers
                    }
                )
            )
        )
        calls_before = self.decision_service.decision_call_count
        decision = await self.decision_service.decide(
            profile,
            observation,
            available_actions=available_actions,
            available_targets=target_ids,
            recent_events=recent_events,
            daily_mode=daily_mode,
            work_window=work_window,
            behavior_hints=behavior_hints,
        )
        if self.decision_service.decision_call_count != calls_before + 1:
            raise RuntimeError("One closed-loop step must use exactly one decision call")
        intent = proposal_to_intent(actor_id, decision.proposal)
        outcome = self.executor.execute(
            world, intent, event_id=self.event_log.next_event_id()
        )
        for event in outcome.events:
            self.event_log.append(event)
        return StepResult(
            proposal=decision.proposal,
            intent=intent,
            outcome=outcome,
            world_after=outcome.new_world,
            observation_before=observation,
            context=decision.context,
            system_prompt=decision.system_prompt,
            user_prompt=decision.user_prompt,
            context_chars=decision.context_chars,
            prompt_chars=decision.prompt_chars,
            decision_latency_seconds=decision.latency_seconds,
            input_tokens=decision.input_tokens,
            output_tokens=decision.output_tokens,
            raw_output_chars=decision.raw_output_chars,
            reasoning_tokens=decision.reasoning_tokens,
            provider_model=decision.provider_model,
            provider_request_count=decision.provider_request_count,
        )


class ScenarioIncompleteError(RuntimeError):
    """The bounded scripted run did not reach its objective."""


@dataclass(frozen=True)
class LunchRunResult:
    steps: tuple[StepResult, ...]
    world_after: WorldState
    final_observation: LocalObservation
    events: tuple[DomainEvent, ...]


class LunchScenarioRunner:
    """At most five one-step decisions; no simulation scheduler or model retry."""

    def __init__(self, step: ClosedLoopStep, max_decisions: int = 5) -> None:
        if isinstance(max_decisions, bool) or not 1 <= max_decisions <= 5:
            raise ValueError("max_decisions must be between 1 and 5")
        self.step = step
        self.max_decisions = max_decisions

    async def run(
        self,
        world: WorldState,
        actor_id: int,
        profile: Mapping[str, object],
        *,
        available_actions: Sequence[ActionType] = (
            ActionType.MOVE,
            ActionType.BUY,
            ActionType.EAT,
        ),
        on_step: Callable[[int, StepResult], None] | None = None,
    ) -> LunchRunResult:
        current = world
        steps: list[StepResult] = []
        person = current.get_person(actor_id)
        if person.hunger <= 0.2 and person.inventory.get("meal", 0) == 0:
            return LunchRunResult(
                steps=(),
                world_after=current,
                final_observation=ObservationBuilder(current).build(actor_id),
                events=(),
            )
        for decision_number in range(1, self.max_decisions + 1):
            result = await self.step.run(
                current, actor_id, profile, available_actions=available_actions
            )
            steps.append(result)
            current = result.world_after
            if on_step is not None:
                on_step(decision_number, result)
            person = current.get_person(actor_id)
            if person.hunger <= 0.2 and person.inventory.get("meal", 0) == 0:
                return LunchRunResult(
                    steps=tuple(steps),
                    world_after=current,
                    final_observation=ObservationBuilder(current).build(actor_id),
                    events=tuple(
                        event for step in steps for event in step.outcome.events
                    ),
                )
        raise ScenarioIncompleteError(
            f"Lunch objective not reached within {self.max_decisions} decisions"
        )
