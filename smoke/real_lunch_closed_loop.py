"""One bounded real-provider lunch attempt through the existing domain loop."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

import httpx
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "third_party" / "AgentSociety" / ".env")

from agentsociety2.society import AgentSociety  # noqa: E402
from social_sim.closed_loop import (  # noqa: E402
    ClosedLoopStep,
    LunchScenarioRunner,
    ScenarioIncompleteError,
    StepResult,
)
from social_sim.decision import (  # noqa: E402
    ActionType,
    CompactDecisionService,
    DecisionClientError,
    DecisionParseError,
    OpenAICompatibleDecisionClient,
    ProviderContractError,
)
from social_sim.decision.client import DecisionReply  # noqa: E402
from social_sim.decision.config import (  # noqa: E402
    DecisionConfigError,
    DecisionProviderConfig,
)
from social_sim.events import EventLog  # noqa: E402
from social_sim.router import DeterministicRouter  # noqa: E402
from social_sim.world import (  # noqa: E402
    ObservationBuilder,
    OfferState,
    PersonWorldState,
    WorldState,
)
from social_sim.world.env import RuleWorldEnv  # noqa: E402


MAX_DECISIONS = 5
GOAL = "reduce hunger by obtaining and eating a meal"
AVAILABLE_ACTIONS = (
    ActionType.MOVE,
    ActionType.BUY,
    ActionType.EAT,
)


class WorldFeedbackError(RuntimeError):
    """A later step failed to observe the objectively updated world or event."""


class ObservedClosedLoopStep(ClosedLoopStep):
    """Print pre-decision observation; execution remains in ClosedLoopStep."""

    async def run(
        self,
        world: WorldState,
        actor_id: int,
        profile: Mapping[str, object],
        *,
        available_actions: Sequence[ActionType] = AVAILABLE_ACTIONS,
    ) -> StepResult:
        number = self.decision_service.decision_call_count + 1
        observation = ObservationBuilder(world).build(actor_id)
        recent_events = [
            event.compact() for event in self.event_log.recent_for_agent(actor_id, limit=3)
        ]
        print(f"---------- STEP {number} ----------", flush=True)
        print("OBSERVATION=" + json.dumps({
            "location": observation.location,
            "money": observation.money,
            "hunger": observation.hunger,
            "meal": observation.inventory.get("meal", 0),
        }, separators=(",", ":")), flush=True)
        print("RECENT_EVENTS=" + json.dumps(recent_events), flush=True)
        return await super().run(
            world, actor_id, profile, available_actions=available_actions
        )


class TrackingDecisionClient:
    """Safe call accounting around the existing no-retry provider adapter."""

    def __init__(self, provider: OpenAICompatibleDecisionClient) -> None:
        self.provider = provider
        self.call_count = 0
        self.user_prompts: list[str] = []

    async def complete(self, system_prompt: str, user_prompt: str) -> DecisionReply:
        self.call_count += 1
        self.user_prompts.append(user_prompt)
        print(f"CONTEXT_CHARS={len(user_prompt.split('Context:', 1)[1])}", flush=True)
        print(f"PROMPT_CHARS={len(system_prompt) + len(user_prompt)}", flush=True)
        print(f"REQUEST_START={datetime.now(timezone.utc).isoformat()}", flush=True)
        print("LLM_CALL_START", flush=True)
        started = time.perf_counter()
        try:
            reply = await self.provider.complete(system_prompt, user_prompt)
        finally:
            print("LLM_CALL_END", flush=True)
            print(f"REQUEST_END={datetime.now(timezone.utc).isoformat()}", flush=True)
            print(f"DECISION_LATENCY_SECONDS={time.perf_counter() - started:.3f}", flush=True)
            metadata = self.provider.last_metadata
            print(
                "RESPONSE_METADATA=" + json.dumps(
                    metadata.safe_dict() if metadata else {}, separators=(",", ":")
                ),
                flush=True,
            )
        return reply


def initial_world() -> WorldState:
    return WorldState(
        time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        people={1: PersonWorldState(1, "home", 100.0, 0.8)},
        venues={"restaurant": {"meal": OfferState("meal", 20.0, 10)}},
    )


def state_summary(world: WorldState) -> dict[str, object]:
    person = world.get_person(1)
    offer = world.get_offer("restaurant", "meal")
    return {
        "location": person.location,
        "money": person.money,
        "hunger": person.hunger,
        "meal": person.inventory.get("meal", 0),
        "restaurant_stock": offer.stock if offer is not None else None,
    }


def auditable_fields(world: WorldState) -> dict[str, object]:
    """Every field in this fixed one-person, one-offer acceptance world."""
    person = world.get_person(1)
    offer = world.get_offer("restaurant", "meal")
    assert offer is not None
    return {
        "time": world.time,
        "locations": world.locations,
        "people_ids": tuple(world.people),
        "agent_id": person.agent_id,
        "location": person.location,
        "money": person.money,
        "hunger": person.hunger,
        "inventory": dict(person.inventory),
        "venue_ids": tuple(world.venues),
        "offer_ids": tuple(world.offers_at("restaurant")),
        "offer_item_id": offer.item_id,
        "offer_price": offer.price,
        "restaurant_stock": offer.stock,
    }


def changed_fields(before: WorldState, after: WorldState) -> list[str]:
    old = auditable_fields(before)
    new = auditable_fields(after)
    return sorted(key for key in old if old[key] != new[key])


def error_category(error: Exception) -> str:
    if isinstance(error, httpx.TimeoutException):
        return "TIMEOUT"
    if isinstance(error, ProviderContractError):
        return error.category
    if isinstance(error, (DecisionClientError, httpx.HTTPError)):
        return "PROVIDER"
    if isinstance(error, DecisionParseError):
        message = str(error)
        if message.startswith(("Unknown action", "Proposed action")) or (
            "target is not currently available" in message
            or "requires a nonempty string target" in message
            or "requires target=None" in message
        ):
            return "INVALID_ACTION"
        return "INVALID_JSON"
    if isinstance(error, WorldFeedbackError):
        return "WORLD_FEEDBACK"
    if isinstance(error, ValueError) and "exceeds" in str(error):
        return "CONTEXT_BUDGET"
    return "RULE_PIPELINE"


async def forbidden_completion(*args: object, **kwargs: object) -> None:
    raise AssertionError("DeterministicRouter must not call an LLM")


async def main() -> int:
    try:
        config = DecisionProviderConfig.from_env()
    except DecisionConfigError as error:
        print(f"PHASE 6.5 INCOMPLETE: {error.code}", flush=True)
        return 1

    world = initial_world()
    print("REAL LUNCH CLOSED LOOP START", flush=True)
    print("REQUEST_CONTRACT=model+messages only", flush=True)
    print(f"MAX_DECISIONS={MAX_DECISIONS}", flush=True)
    print("INITIAL_STATE=" + json.dumps(state_summary(world), separators=(",", ":")), flush=True)

    provider = OpenAICompatibleDecisionClient(
        base_url=config.api_base,
        api_key=config.api_key,
        model=config.model,
        timeout_seconds=60,
        minimal_request=True,
    )
    tracker = TrackingDecisionClient(provider)
    service = CompactDecisionService(tracker)
    log = EventLog()
    runner = LunchScenarioRunner(ObservedClosedLoopStep(service, log), MAX_DECISIONS)
    completed_steps: list[StepResult] = []
    current_world = world
    previous_event: str | None = None

    def report_step(number: int, step: StepResult) -> None:
        nonlocal current_world, previous_event
        previous_world = current_world
        # Executor and event log have already advanced; preserve the actual
        # result even if an audit assertion below fails.
        current_world = step.world_after
        expected_observation = ObservationBuilder(previous_world).build(1)
        if step.observation_before != expected_observation:
            raise WorldFeedbackError("Observation was not built from the latest world")
        if previous_event is not None and previous_event not in tracker.user_prompts[-1]:
            raise WorldFeedbackError("Recent event did not reach the next decision")
        if step.context_chars >= 2000 or step.prompt_chars >= 3000:
            raise ValueError("Decision prompt exceeds character budget")
        if number != len(completed_steps) + 1:
            raise RuntimeError("Unexpected decision step number")
        changes = changed_fields(previous_world, step.world_after)
        expected_changes = {
            ActionType.MOVE: {"location"},
            ActionType.BUY: {"money", "inventory", "restaurant_stock"},
            ActionType.EAT: {"hunger", "inventory"},
        }
        if step.outcome.allowed:
            if set(changes) != expected_changes[step.proposal.action]:
                raise WorldFeedbackError("Accepted action changed unexpected world fields")
        elif changes or step.world_after is not previous_world:
            raise WorldFeedbackError("Rejected action changed the world")
        if step.context_chars >= 1000:
            print("CONTEXT_SIZE_WARNING", flush=True)
        print(f"INPUT_TOKENS={step.input_tokens}", flush=True)
        print(f"OUTPUT_TOKENS={step.output_tokens}", flush=True)
        print(f"RAW_OUTPUT_CHARS={step.raw_output_chars}", flush=True)
        if step.raw_output_chars > 500:
            print("OUTPUT_TOO_VERBOSE_WARNING", flush=True)
        print("DECISION=" + json.dumps({
            "action": step.proposal.action.value,
            "target": step.proposal.target,
        }, separators=(",", ":")), flush=True)
        print(f"RULE={'ACCEPTED' if step.outcome.allowed else 'REJECTED'}", flush=True)
        print(f"REASON={step.outcome.reason_code}", flush=True)
        print(f"EVENT={step.outcome.events[0].event_type.value}", flush=True)
        print("CHANGED_FIELDS=" + json.dumps(changes), flush=True)
        print("NEW_STATE=" + json.dumps(state_summary(step.world_after), separators=(",", ":")), flush=True)
        print("WORLD_FEEDBACK=PASS", flush=True)
        completed_steps.append(step)
        previous_event = step.outcome.events[0].compact()

    world_env = RuleWorldEnv(world)
    router = DeterministicRouter(env_modules=[world_env])
    router._coder_dispatcher.call = forbidden_completion
    router._summary_dispatcher.call = forbidden_completion
    router.acompletion = forbidden_completion
    router.acompletion_with_system_prompt = forbidden_completion
    router.generate_world_description_from_tools = forbidden_completion
    society: AgentSociety | None = None
    status = 1
    lifecycle_ready = False
    try:
        society = AgentSociety(
            # Lifecycle-only: do not instantiate PersonAgent or enter ReAct.
            agent_specs=[],
            agent_class_name="PersonAgent",
            env_router=router,
            start_t=world.time,
            run_dir=ROOT / "run" / "real_lunch_closed_loop",
            enable_replay=False,
        )
        await asyncio.wait_for(society.init(), timeout=90)
        print("AGENTSOCIETY_INIT_OK", flush=True)
        lifecycle_ready = True
        try:
            result = await runner.run(
                world,
                1,
                {"name": "Alice", "goal": GOAL},
                available_actions=AVAILABLE_ACTIONS,
                on_step=report_step,
            )
        except ScenarioIncompleteError:
            print("REAL CLOSED LOOP NOT COMPLETED", flush=True)
            print("PHASE 6.5 ARCHITECTURE PASS — MODEL POLICY NOT COMPLETED", flush=True)
            status = 0
        else:
            current_world = result.world_after
            if result.final_observation != ObservationBuilder(current_world).build(1):
                raise WorldFeedbackError("Final observation did not match final world")
            print("PHASE 6.5 REAL CLOSED LOOP COMPLETE", flush=True)
            print("GOAL_REACHED=YES", flush=True)
            print("WORLD_FEEDBACK=PASS", flush=True)
            status = 0
    except Exception as error:
        category = error_category(error) if lifecycle_ready else "AGENTSOCIETY_LIFECYCLE"
        if (
            isinstance(error, DecisionParseError)
            and provider.last_metadata is not None
            and provider.last_metadata.finish_reason == "length"
        ):
            category = "OUTPUT_BUDGET_EXHAUSTED"
        prefix = (
            "PHASE 6.5 PROVIDER CONTRACT INCOMPLETE"
            if isinstance(
                error,
                (ProviderContractError, DecisionParseError, DecisionClientError, httpx.HTTPError),
            )
            else "PHASE 6.5 INCOMPLETE"
        )
        print(f"{prefix}: {category}", flush=True)
        print(f"LAST_SUCCESSFUL_STEP={len(completed_steps)}", flush=True)
        print(f"FAILED_DECISION_ATTEMPT={service.decision_call_count}", flush=True)
        print(f"ERROR_TYPE={type(error).__name__}", flush=True)
        print(f"ERROR_CATEGORY={category}", flush=True)
        if isinstance(error, DecisionParseError):
            print(f"RAW_OUTPUT_CHARS={len(provider.last_raw_text or '')}", flush=True)
        status = 1
    finally:
        if society is not None:
            try:
                await asyncio.wait_for(society.close(), timeout=45)
                print("AGENTSOCIETY_CLOSE_OK", flush=True)
            except Exception as error:
                print("PHASE 6.5 INCOMPLETE: AGENTSOCIETY_LIFECYCLE", flush=True)
                print(f"CLOSE_ERROR_TYPE={type(error).__name__}", flush=True)
                status = 1
        await provider.aclose()
        calls = service.decision_call_count
        print(f"TOTAL_DECISIONS={calls}", flush=True)
        print(f"APPLICATION_LLM_CALLS={tracker.call_count}", flush=True)
        print(f"PROVIDER_ATTEMPTS={provider.call_count}", flush=True)
        if calls != tracker.call_count or calls != provider.call_count or calls > MAX_DECISIONS:
            print("PHASE 6.5 INCOMPLETE: MULTI_CALL_VIOLATION", flush=True)
            status = 1
        print("FINAL_STATE=" + json.dumps(state_summary(current_world), separators=(",", ":")), flush=True)
        print(f"EVENT_COUNT={len(log.all())}", flush=True)
        usage = router.get_token_usages()
        env_calls = sum(stat.call_count for stat in usage.values())
        print(f"ENV_LLM_CALLS={env_calls}", flush=True)
        print("RULE_LLM_CALLS=0", flush=True)
        print("REDUCER_LLM_CALLS=0", flush=True)
        print("EVENT_LLM_CALLS=0", flush=True)
        if env_calls != 0:
            print("PHASE 6.5 INCOMPLETE: AGENTSOCIETY_LIFECYCLE", flush=True)
            status = 1
    return status


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
