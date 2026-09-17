"""Sequential, objective episodes built from the existing closed-loop step."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from social_sim.closed_loop import ClosedLoopStep
from social_sim.context import ContextPolicy
from social_sim.decision import (
    ActionType,
    CompactDecisionService,
    DecisionClientError,
    DecisionParseError,
    ProviderContractError,
)
from social_sim.decision.client import DecisionModelClient, DecisionReply
from social_sim.events import EventLog
from social_sim.world import OfferState, PersonWorldState, WorldState

from .models import (
    EpisodeResult,
    StepTrajectory,
    TerminationReason,
    effects_snapshots,
    event_snapshot,
    intent_snapshot,
    observation_snapshot,
    proposal_snapshot,
    world_snapshot,
)
from .recorder import TrajectoryRecorder
from .validation import validate_trajectory

if TYPE_CHECKING:
    from .ablation_scenarios import PreludeSetup


LUNCH_ACTIONS = (ActionType.MOVE, ActionType.BUY, ActionType.EAT)
LUNCH_TARGETS = ("home", "meal", "park", "restaurant")


def lunch_initial_world() -> WorldState:
    """A new immutable world for every episode, independent of previous results."""
    return WorldState(
        time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        people={1: PersonWorldState(1, "home", 100.0, 0.8)},
        venues={"restaurant": {"meal": OfferState("meal", 20.0, 10)}},
    )


def lunch_goal(world: WorldState) -> bool:
    person = world.get_person(1)
    return person.hunger <= 0.2 and person.inventory.get("meal", 0) == 0


@dataclass(frozen=True)
class ScenarioConfig:
    scenario_name: str
    max_decisions: int
    initial_world_factory: Callable[[], WorldState]
    goal: Callable[[WorldState], bool]
    available_actions: tuple[ActionType, ...]
    target_candidates: tuple[str, ...]
    actor_id: int = 1
    profile: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        if not self.scenario_name or not self.scenario_name.replace("-", "").isalnum():
            raise ValueError("scenario_name must be a nonempty ID")
        if isinstance(self.max_decisions, bool) or not 1 <= self.max_decisions <= 5:
            raise ValueError("max_decisions must be between 1 and 5")
        if not self.available_actions or len(set(self.available_actions)) != len(self.available_actions):
            raise ValueError("available_actions must be nonempty and unique")
        if not set(self.available_actions).issubset(set(LUNCH_ACTIONS)):
            raise ValueError("Phase 7 supports MOVE, BUY, and EAT only")
        if not self.target_candidates or len(set(self.target_candidates)) != len(self.target_candidates):
            raise ValueError("target_candidates must be nonempty and unique")
        if self.profile is None:
            object.__setattr__(
                self, "profile", {"name": "Alice", "goal": "reduce hunger by obtaining and eating a meal"}
            )


class LunchBenchmarkScenario(ScenarioConfig):
    """Frozen v0.1 lunch benchmark; only the injected decision client varies."""

    def __init__(self) -> None:
        super().__init__(
            scenario_name="lunch",
            max_decisions=5,
            initial_world_factory=lunch_initial_world,
            goal=lunch_goal,
            available_actions=LUNCH_ACTIONS,
            target_candidates=LUNCH_TARGETS,
        )


class ScriptedDecisionClient:
    """One deterministic proposal per call, resetting the script each episode."""

    def __init__(self, script: Sequence[tuple[ActionType | str, str | None]]) -> None:
        if not script:
            raise ValueError("script must contain at least one decision")
        self.script = tuple((ActionType(action), target) for action, target in script)
        self.call_count = 0
        self._index = 0

    def start_episode(self) -> None:
        self._index = 0

    async def complete(self, system_prompt: str, user_prompt: str) -> DecisionReply:
        if self._index >= len(self.script):
            raise RuntimeError("Script exhausted before episode terminated")
        action, target = self.script[self._index]
        self._index += 1
        self.call_count += 1
        return DecisionReply(json.dumps({"action": action.value, "target": target}))


_INVALID_ACTION_MARKERS = (
    "Unknown action",
    "Proposed action",
    "requires a nonempty string target",
    "requires target=None",
)


class EpisodeRunner:
    """Run fresh worlds sequentially; recording is an observer of completed steps."""

    def __init__(
        self,
        scenario: ScenarioConfig,
        decision_client: DecisionModelClient,
        *,
        output_dir: Path | str = Path("run/evaluation"),
        record_prompt: bool = False,
        decision_policy_name: str = "unknown",
        model_name: str | None = None,
        context_policy_name: str = "baseline_compact",
        context_policy: ContextPolicy | None = None,
        write_artifacts: bool = True,
    ) -> None:
        self.scenario = scenario
        self.decision_client = decision_client
        self.output_dir = Path(output_dir)
        self.record_prompt = record_prompt
        self.decision_policy_name = decision_policy_name
        self.model_name = model_name
        self.context_policy_name = context_policy_name
        self.context_policy = context_policy
        self.write_artifacts = write_artifacts

    async def run_episode(
        self,
        number: int,
        *,
        episode_id: str | None = None,
        setup: PreludeSetup | None = None,
        experiment_config_hash: str | None = None,
    ) -> EpisodeResult:
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            raise ValueError("episode number must be a positive integer")
        start_episode = getattr(self.decision_client, "start_episode", None)
        if callable(start_episode):
            start_episode()
        episode_id = episode_id or f"{self.scenario.scenario_name}-{number:06d}"
        world = setup.world if setup is not None else self.scenario.initial_world_factory()
        if not isinstance(world, WorldState):
            raise TypeError("initial_world_factory must return WorldState")
        world.get_person(self.scenario.actor_id)
        recorder = TrajectoryRecorder(
            episode_id, output_dir=self.output_dir, record_prompt=self.record_prompt
        )
        if setup is not None and world_snapshot(world) != setup.model_start_state:
            raise RuntimeError("Prelude model-start state does not match its world")
        service = CompactDecisionService(
            self.decision_client, context_policy=self.context_policy
        )
        stepper = ClosedLoopStep(service, setup.event_log if setup is not None else EventLog())
        provider_start = getattr(self.decision_client, "provider_request_count", None)
        termination = TerminationReason.GOAL_REACHED if self.scenario.goal(world) else None
        invalid_outputs = 0
        provider_errors = 0

        for step_index in range(1, self.scenario.max_decisions + 1):
            if termination is not None:
                break
            before = world
            try:
                completed = await stepper.run(
                    before,
                    self.scenario.actor_id,
                    self.scenario.profile or {},
                    available_actions=self.scenario.available_actions,
                    available_targets=self.scenario.target_candidates,
                )
            except DecisionParseError as error:
                if str(error).startswith(_INVALID_ACTION_MARKERS) or "target is not currently available" in str(error):
                    termination = TerminationReason.INVALID_ACTION
                else:
                    termination = TerminationReason.INVALID_MODEL_OUTPUT
                invalid_outputs = 1
                break
            except ProviderContractError:
                termination = TerminationReason.INVALID_MODEL_OUTPUT
                invalid_outputs = 1
                break
            except (httpx.TimeoutException, asyncio.TimeoutError):
                termination = TerminationReason.TIMEOUT
                break
            except (DecisionClientError, httpx.HTTPError):
                termination = TerminationReason.PROVIDER_ERROR
                provider_errors = 1
                break

            if completed.context_chars >= 2000 or completed.prompt_chars >= 3000:
                raise ValueError("Decision prompt exceeded the frozen hard budget")
            outcome = completed.outcome
            if len(outcome.events) != 1:
                raise RuntimeError("Exactly one domain event is required per decision")
            step = StepTrajectory(
                episode_id=episode_id,
                step_index=step_index,
                state_before=world_snapshot(before),
                observation=observation_snapshot(completed.observation_before),
                context=completed.context,
                proposal=proposal_snapshot(completed.proposal),
                intent=intent_snapshot(completed.intent),
                rule_allowed=outcome.allowed,
                rule_reason_code=outcome.reason_code,
                effects=effects_snapshots(outcome.effects),
                event=event_snapshot(outcome.events[0]),
                state_after=world_snapshot(completed.world_after),
                decision_call_count=1,
                provider_request_count=completed.provider_request_count,
                context_chars=completed.context_chars,
                prompt_chars=completed.prompt_chars,
                decision_latency_seconds=completed.decision_latency_seconds,
                input_tokens=completed.input_tokens,
                output_tokens=completed.output_tokens,
                reasoning_tokens=completed.reasoning_tokens,
                visible_content_chars=completed.raw_output_chars,
                provider_model=completed.provider_model,
                prompt=(completed.system_prompt + "\n" + completed.user_prompt)
                if self.record_prompt else None,
            )
            recorder.append_step(step)
            world = completed.world_after
            if self.scenario.goal(world):
                termination = TerminationReason.GOAL_REACHED
                break

        if termination is None:
            termination = TerminationReason.MAX_DECISIONS
        provider_end = getattr(self.decision_client, "provider_request_count", None)
        provider_requests = (
            provider_end - provider_start
            if isinstance(provider_start, int) and isinstance(provider_end, int)
            else sum(step.provider_request_count for step in recorder.steps)
        )
        result = recorder.finish_episode(
            success=termination is TerminationReason.GOAL_REACHED,
            termination_reason=termination,
            final_state=world_snapshot(world),
            decision_count=service.decision_call_count,
            invalid_outputs=invalid_outputs,
            provider_errors=provider_errors,
            total_provider_requests=provider_requests,
            scenario_name=self.scenario.scenario_name,
            context_policy_name=self.context_policy_name,
            decision_policy_name=self.decision_policy_name,
            model_name=self.model_name,
            scenario_variant=setup.variant.value if setup is not None else None,
            prelude_events=setup.prelude_events if setup is not None else (),
            prelude_action_count=setup.prelude_action_count if setup is not None else 0,
            prelude_rejection_count=setup.prelude_rejection_count if setup is not None else 0,
            model_start_state=setup.model_start_state if setup is not None else None,
            experiment_config_hash=experiment_config_hash,
        )
        validate_trajectory(result)
        if self.write_artifacts:
            recorder.write_episode(result)
        return result

    async def run_benchmark(self, episodes: int) -> list[EpisodeResult]:
        if isinstance(episodes, bool) or not isinstance(episodes, int) or episodes < 1:
            raise ValueError("episodes must be a positive integer")
        results: list[EpisodeResult] = []
        for number in range(1, episodes + 1):
            results.append(await self.run_episode(number))
        return results
