"""Independent one-request G2 decisions at eight frozen world states."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from social_sim.behavior_prior import format_prior
from social_sim.behavior_prior.index import BehaviorPriorIndex
from social_sim.behavior_prior.models import CORE7
from social_sim.behavior_prior.query import PriorQuery, previous_activity_from_events
from social_sim.behavior_prior.validation import feasible_prior_count
from social_sim.closed_loop import ClosedLoopStep
from social_sim.context import ContextCompiler
from social_sim.daily.persona import NeutralPersona
from social_sim.daily.profiles import ExperimentBehaviorProfile
from social_sim.daily.runner import DAILY_TARGETS
from social_sim.decision import ActionType, CompactDecisionService, DecisionClientError, DecisionParseError, ProviderContractError
from social_sim.decision.prompt import MAX_CONTEXT_CHARS, build_decision_prompt
from social_sim.events import DomainEvent, EventLog, EventType
from social_sim.execution import ActionExecutor
from social_sim.evaluation.models import world_snapshot
from social_sim.rules import RuleEngine
from social_sim.world import ObservationBuilder, OfferState, PersonWorldState, WorldState

from .corpus import HeldoutScorer


@dataclass(frozen=True)
class FixedState:
    state_id: str
    title: str
    hour: int
    minute: int
    location: str
    hunger: float
    energy: float
    previous_activity: str | None

    def world(self) -> WorldState:
        return WorldState(
            time=datetime(2026, 1, 1, self.hour, self.minute, tzinfo=timezone.utc),
            people={1: PersonWorldState(1, self.location, 100.0, self.hunger, energy=self.energy)},
            locations=("home", "office", "restaurant", "park"),
            venues={"restaurant": {"meal": OfferState("meal", 20.0, 10)}},
        )

    def event_log(self) -> EventLog:
        log = EventLog()
        if self.previous_activity is not None:
            action = ActionType(self.previous_activity)
            if action is ActionType.MOVE:
                event_type, target = EventType.MOVED, self.location
            elif action is ActionType.EAT:
                event_type, target = EventType.ATE, "meal"
            else:
                event_type, target = EventType(f"{action.value}_COMPLETED"), None
            log.append(DomainEvent(log.next_event_id(), 1, event_type, action, target, True, "ACCEPTED"))
        if previous_activity_from_events(log.all()) != self.previous_activity:
            raise RuntimeError("PREVIOUS_ACTIVITY_EVENT_MISMATCH")
        return log


STATES = (
    FixedState("S1", "Morning start", 6, 30, "home", 0.30, 0.80, None),
    FixedState("S2", "Morning after sleep", 7, 30, "home", 0.35, 0.80, "SLEEP"),
    FixedState("S3", "Work arrival", 9, 15, "office", 0.40, 0.70, "MOVE"),
    FixedState("S4", "Late morning", 11, 30, "office", 0.55, 0.60, "WORK"),
    FixedState("S5", "Midday hungry", 12, 30, "office", 0.80, 0.55, "WORK"),
    FixedState("S6", "Evening arrival home", 18, 30, "home", 0.40, 0.45, "MOVE"),
    FixedState("S7", "Evening after meal", 19, 30, "home", 0.20, 0.40, "EAT"),
    FixedState("S8", "Late evening", 21, 30, "home", 0.30, 0.25, "LEISURE"),
)


@dataclass(frozen=True)
class PanelCondition:
    name: str
    corpus: str | None
    prior_k: int


CONDITIONS = (
    PanelCondition("C0", None, 0), PanelCondition("C1", "B100", 1),
    PanelCondition("C2", "B1000", 1), PanelCondition("C3", "BTRAIN_ALL", 1),
    PanelCondition("C4", "BTRAIN_ALL", 3),
)


def panel_schedule() -> list[dict[str, object]]:
    result = []
    for repetition in (1, 2):
        for state_index, state in enumerate(STATES):
            offset = (state_index + (repetition - 1) * 2) % len(CONDITIONS)
            positions = tuple((offset + step) % len(CONDITIONS) for step in range(len(CONDITIONS)))
            for position in positions:
                result.append({"case_id": f"A{len(result) + 1:03d}", "state_id": state.state_id,
                               "repetition": repetition, "condition": CONDITIONS[position].name})
    assert len(result) == 80
    return result


def _engine(profile: ExperimentBehaviorProfile) -> RuleEngine:
    return RuleEngine(
        duration_overrides={ActionType(name): duration for name, duration in profile.duration_overrides.items()},
        experimental_actions_enabled=profile.experimental_actions_enabled,
    )


def _safe_backend(value: object) -> str | None:
    if isinstance(value, str) and len(value) <= 128 and all(
        char.isalnum() or char in "_.:/-" for char in value
    ) and "://" not in value and not value.startswith(("ark-", "sk-")):
        return value
    return None


class FixedStateDecisionBenchmark:
    def __init__(self, client: object, profile: ExperimentBehaviorProfile,
                 indices: dict[str, BehaviorPriorIndex], scorer: HeldoutScorer) -> None:
        self.client, self.profile, self.indices, self.scorer = client, profile, indices, scorer

    def preview(self, state: FixedState, condition: PanelCondition) -> dict[str, object]:
        world = state.world()
        log = state.event_log()
        query = PriorQuery.at(world.time, state.previous_activity)
        prior = self.indices[condition.corpus].query(query, limit=condition.prior_k) if condition.corpus else None
        hints = (format_prior(prior),) if prior else ()
        events = tuple(event.compact() for event in log.all())
        context = ContextCompiler(max_chars=MAX_CONTEXT_CHARS).compile(
            NeutralPersona(goal="live through this period while handling your basic needs and obligations").profile(),
            ObservationBuilder(world).build(1),
            available_actions=[action.value for action in self.profile.available_actions],
            available_targets=DAILY_TARGETS, events=events[-3:], daily_mode=True,
            work_window="09:00-17:00", behavior_hints=hints,
        )
        prompt = build_decision_prompt(context, daily_mode=True)
        distribution = self.scorer.distribution(query)
        return {
            "world": world, "log": log, "query": query, "prior": prior, "hints": hints,
            "context": context, "prompt": prompt, "distribution": distribution,
            "state_hash": hashlib.sha256(json.dumps(
                {"world": world_snapshot(world), "events": events},
                sort_keys=True, separators=(",", ":"),
            ).encode()).hexdigest(),
        }

    async def run(self, case: dict[str, object]) -> dict[str, object]:
        state = next(state for state in STATES if state.state_id == case["state_id"])
        condition = next(condition for condition in CONDITIONS if condition.name == case["condition"])
        preview = self.preview(state, condition)
        world, log, prior = preview["world"], preview["log"], preview["prior"]
        service = CompactDecisionService(self.client, allow_deterministic_output_recovery=True)
        stepper = ClosedLoopStep(service, log, executor=ActionExecutor(_engine(self.profile)))
        provider_before = getattr(self.client, "provider_request_count", None)
        started = time.perf_counter()
        result = None
        status = "SUCCESS"
        try:
            result = await stepper.run(
                world, 1, NeutralPersona(goal="live through this period while handling your basic needs and obligations").profile(),
                available_actions=self.profile.available_actions,
                available_targets=DAILY_TARGETS, daily_mode=True,
                work_window="09:00-17:00", behavior_hints=preview["hints"],
            )
        except DecisionParseError:
            status = "INVALID_MODEL_OUTPUT"
        except (httpx.TimeoutException, asyncio.TimeoutError):
            status = "TIMEOUT"
        except (DecisionClientError, ProviderContractError, httpx.HTTPError):
            status = "PROVIDER_ERROR"
        elapsed = time.perf_counter() - started
        provider_after = getattr(self.client, "provider_request_count", None)
        request_count = (provider_after - provider_before
                         if isinstance(provider_before, int) and isinstance(provider_after, int)
                         else result.provider_request_count if result else service.decision_call_count)
        real_counter = isinstance(provider_before, int) and isinstance(provider_after, int)
        if (real_counter and request_count != 1) or service.decision_call_count != 1:
            raise RuntimeError("ONE_REQUEST_PER_CASE_VIOLATION")
        if result is not None and (result.context != preview["context"] or
                                   (real_counter and result.provider_request_count != 1)):
            raise RuntimeError("FIXED_STATE_CONTEXT_OR_REQUEST_MISMATCH")
        context, prompt = preview["context"], preview["prompt"]
        if len(context) >= 2000 or prompt.prompt_chars >= 3000:
            raise RuntimeError("PANEL_CONTEXT_BUDGET_EXCEEDED")
        metadata = getattr(self.client, "last_metadata", None)
        diagnostic = service.last_output_diagnostic or {}
        action = result.proposal.action.value if result else None
        distribution = preview["distribution"]
        scored = distribution.score(action) if action else {}
        row = {
            **case, "corpus_size": self.indices[condition.corpus].corpus_size if condition.corpus else 0,
            "corpus": condition.corpus or "B0", "prior_k": condition.prior_k,
            "state_hash": preview["state_hash"],
            "prior_activities": list(prior.activities) if prior else [],
            "fallback_level": prior.fallback_level if prior else None,
            "support_count": prior.support_count if prior else None,
            "prior_feasible_count": feasible_prior_count(prior, world, _engine(self.profile)) if prior else 0,
            "context_chars": len(context), "prompt_chars": prompt.prompt_chars,
            "prompt_sha256": hashlib.sha256((prompt.system + prompt.user).encode()).hexdigest(),
            "provider_status": status, "provider_request_count": request_count,
            "http_status": getattr(metadata, "http_status", None),
            "actual_backend": _safe_backend(result.provider_model if result else diagnostic.get("provider_model")),
            "action": action, "target": result.proposal.target if result else None,
            "parse_valid": result is not None, "strict_valid": result.strict_valid if result else diagnostic.get("strict_valid"),
            "output_recovered": result.output_recovered if result else False,
            "action_available": result is not None,
            "rule_executable": result.outcome.allowed if result else None,
            "rule_reason_code": result.outcome.reason_code if result else None,
            "prior_follow": action in prior.activities if action and prior else None,
            "latency_seconds": result.decision_latency_seconds if result else elapsed,
            "input_tokens": result.input_tokens if result else diagnostic.get("input_tokens"),
            "output_tokens": result.output_tokens if result else diagnostic.get("output_tokens"),
            "reasoning_tokens": result.reasoning_tokens if result else diagnostic.get("reasoning_tokens"),
            "eval_fallback_level": distribution.fallback_level,
            "eval_support_count": distribution.support_count,
            "eval_other_mass": distribution.other_mass,
            **{"heldout_action_share": None, "heldout_rank": None,
               "heldout_top1_match": None, "heldout_top3_match": None},
            **scored,
        }
        if action is not None and action not in CORE7:
            raise RuntimeError("NON_CORE7_MODEL_ACTION")
        return row
