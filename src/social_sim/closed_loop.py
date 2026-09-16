"""One-person domain orchestration; AgentSociety remains the simulation runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

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
    context_chars: int
    prompt_chars: int


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
    ) -> StepResult:
        observation = ObservationBuilder(world).build(actor_id)
        recent_events = tuple(
            event.compact() for event in self.event_log.recent_for_agent(actor_id, limit=3)
        )
        target_ids = tuple(
            sorted(
                set(world.locations)
                | {
                    item_id
                    for offers in world.venues.values()
                    for item_id in offers
                }
            )
        )
        calls_before = self.decision_service.decision_call_count
        decision = await self.decision_service.decide(
            profile,
            observation,
            available_actions=available_actions,
            available_targets=target_ids,
            recent_events=recent_events,
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
            context_chars=decision.context_chars,
            prompt_chars=decision.prompt_chars,
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
        for _ in range(self.max_decisions):
            result = await self.step.run(current, actor_id, profile)
            steps.append(result)
            current = result.world_after
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
