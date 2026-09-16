"""JSON-friendly, secret-conscious evaluation trajectory schema.

Evaluation records are observations of a deterministic run, never inputs to it.
Only parsed decisions and numeric usage statistics are retained; hidden reasoning
and provider credentials are not part of this schema.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from social_sim.actions import ActionIntent
from social_sim.decision import DecisionProposal
from social_sim.effects.models import EatEffect, Effect, MoveEffect, PurchaseEffect
from social_sim.events import DomainEvent
from social_sim.world import LocalObservation, WorldState


TRAJECTORY_SCHEMA_VERSION = "0.1"
trajectory_schema_version = TRAJECTORY_SCHEMA_VERSION


class TerminationReason(str, Enum):
    GOAL_REACHED = "GOAL_REACHED"
    MAX_DECISIONS = "MAX_DECISIONS"
    INVALID_MODEL_OUTPUT = "INVALID_MODEL_OUTPUT"
    INVALID_ACTION = "INVALID_ACTION"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    TIMEOUT = "TIMEOUT"
    ARCHITECTURE_ERROR = "ARCHITECTURE_ERROR"


_SENSITIVE_KEY = re.compile(
    r"^(?:reasoning|reasoning_content|hidden_reasoning|think|api[_-]?key|"
    r"authorization|access[_-]?token|refresh[_-]?token|password|secret)$",
    re.IGNORECASE,
)
_SECRET_TEXT = (
    re.compile(r"(?i)\bBearer\s+\S+"),
    re.compile(r"(?i)\b(?:sk|ark)-[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(?:api[_-]?key|authorization|password|secret)\s*[:=]\s*[^\s,}\"']+"),
)


def _safe_text(value: str) -> str:
    for pattern in _SECRET_TEXT:
        value = pattern.sub("[REDACTED]", value)
    return value


def _json_copy(value: object) -> object:
    """Detach nested mutable inputs and reject non-JSON or sensitive fields."""
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("trajectory numbers must be finite")
        return value
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, Mapping):
        copy: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("trajectory mapping keys must be strings")
            if _SENSITIVE_KEY.fullmatch(key):
                raise ValueError(f"sensitive field is not allowed in trajectory: {key}")
            copy[_safe_text(key)] = _json_copy(item)
        return copy
    if isinstance(value, (tuple, list)):
        return [_json_copy(item) for item in value]
    raise TypeError(f"trajectory value is not JSON-friendly: {type(value).__name__}")


def _snapshot(value: Mapping[str, object], field_name: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    result = _json_copy(value)
    assert isinstance(result, dict)
    return result


def world_snapshot(world: WorldState) -> dict[str, object]:
    """Capture objective world facts, not a dataclass repr or live reference."""
    if not isinstance(world, WorldState):
        raise TypeError("world must be a WorldState")
    return {
        "time": world.time.isoformat(),
        "locations": list(world.locations),
        "people": {
            str(agent_id): {
                "location": person.location,
                "money": person.money,
                "hunger": person.hunger,
                "inventory": dict(person.inventory),
            }
            for agent_id, person in sorted(world.people.items())
        },
        "venues": {
            location_id: {
                item_id: {"price": offer.price, "stock": offer.stock}
                for item_id, offer in sorted(offers.items())
            }
            for location_id, offers in sorted(world.venues.items())
        },
    }


def observation_snapshot(observation: LocalObservation) -> dict[str, object]:
    """Record only the LocalObservation shown to this agent."""
    if not isinstance(observation, LocalObservation):
        raise TypeError("observation must be a LocalObservation")
    return {
        "agent_id": observation.agent_id,
        "time": observation.time,
        "location": observation.location,
        "money": observation.money,
        "hunger": observation.hunger,
        "inventory": dict(observation.inventory),
        "offers": {item_id: dict(offer) for item_id, offer in observation.offers.items()},
    }


def proposal_snapshot(proposal: DecisionProposal) -> dict[str, object]:
    if not isinstance(proposal, DecisionProposal):
        raise TypeError("proposal must be a DecisionProposal")
    return {"action": proposal.action.value, "target": proposal.target}


def intent_snapshot(intent: ActionIntent) -> dict[str, object]:
    if not isinstance(intent, ActionIntent):
        raise TypeError("intent must be an ActionIntent")
    return {
        "actor_id": intent.actor_id,
        "action": intent.action.value,
        "target": intent.target,
        "params": dict(intent.params),
    }


def effect_snapshot(effect: Effect) -> dict[str, object]:
    if isinstance(effect, MoveEffect):
        return {
            "type": "MOVE",
            "agent_id": effect.agent_id,
            "from": effect.from_location,
            "to": effect.to_location,
        }
    if isinstance(effect, PurchaseEffect):
        return {
            "type": "BUY",
            "agent_id": effect.agent_id,
            "location_id": effect.location_id,
            "item_id": effect.item_id,
            "quantity": effect.quantity,
            "unit_price": effect.unit_price,
            "expected_money_before": effect.expected_money_before,
            "expected_stock_before": effect.expected_stock_before,
            "expected_inventory_before": effect.expected_inventory_before,
        }
    if isinstance(effect, EatEffect):
        return {
            "type": "EAT",
            "agent_id": effect.agent_id,
            "item_id": effect.item_id,
            "quantity": effect.quantity,
            "expected_inventory_before": effect.expected_inventory_before,
            "expected_hunger_before": effect.expected_hunger_before,
            "new_hunger": effect.new_hunger,
        }
    raise TypeError(f"Unsupported effect: {type(effect).__name__}")


def effects_snapshots(effects: tuple[Effect, ...]) -> tuple[dict[str, object], ...]:
    return tuple(effect_snapshot(effect) for effect in effects)


def event_snapshot(event: DomainEvent) -> dict[str, object]:
    if not isinstance(event, DomainEvent):
        raise TypeError("event must be a DomainEvent")
    return {
        "event_id": event.event_id,
        "event_type": event.event_type.value,
        "actor_id": event.actor_id,
        "action": event.action.value,
        "target": event.target,
        "success": event.success,
        "reason_code": event.reason_code,
    }


def _count(value: int | None, field_name: str, *, nullable: bool = False) -> None:
    if value is None and nullable:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")


@dataclass(frozen=True)
class StepTrajectory:
    """One complete decision and deterministic execution step."""

    episode_id: str
    step_index: int
    state_before: dict[str, object]
    observation: dict[str, object]
    context: str
    proposal: dict[str, object]
    intent: dict[str, object]
    rule_allowed: bool
    rule_reason_code: str
    effects: tuple[dict[str, object], ...]
    event: dict[str, object]
    state_after: dict[str, object]
    decision_call_count: int
    provider_request_count: int
    context_chars: int
    prompt_chars: int
    decision_latency_seconds: float
    input_tokens: int | None
    output_tokens: int | None
    reasoning_tokens: int | None
    visible_content_chars: int
    provider_model: str | None
    prompt: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.episode_id, str) or not self.episode_id:
            raise ValueError("episode_id must be a nonempty string")
        _count(self.step_index, "step_index")
        if self.step_index == 0:
            raise ValueError("step_index starts at 1")
        for field_name in (
            "decision_call_count", "provider_request_count", "context_chars",
            "prompt_chars", "visible_content_chars",
        ):
            _count(getattr(self, field_name), field_name)
        for field_name in ("input_tokens", "output_tokens", "reasoning_tokens"):
            _count(getattr(self, field_name), field_name, nullable=True)
        if (
            isinstance(self.decision_latency_seconds, bool)
            or not isinstance(self.decision_latency_seconds, (int, float))
            or not math.isfinite(self.decision_latency_seconds)
            or self.decision_latency_seconds < 0
        ):
            raise ValueError("decision_latency_seconds must be finite and non-negative")
        if not isinstance(self.rule_allowed, bool):
            raise TypeError("rule_allowed must be a bool")
        if not isinstance(self.rule_reason_code, str) or not self.rule_reason_code:
            raise ValueError("rule_reason_code must be a nonempty string")
        if not isinstance(self.context, str):
            raise TypeError("context must be a string")
        if self.prompt is not None and not isinstance(self.prompt, str):
            raise TypeError("prompt must be a string or None")
        for field_name in (
            "state_before", "observation", "proposal", "intent", "event", "state_after",
        ):
            object.__setattr__(self, field_name, _snapshot(getattr(self, field_name), field_name))
        if not isinstance(self.effects, tuple):
            raise TypeError("effects must be a tuple")
        object.__setattr__(self, "effects", tuple(_snapshot(effect, "effect") for effect in self.effects))
        for field_name in ("context", "rule_reason_code", "prompt"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _safe_text(value))
        if self.provider_model is not None:
            if not isinstance(self.provider_model, str):
                raise TypeError("provider_model must be a string or None")
            object.__setattr__(self, "provider_model", _safe_text(self.provider_model))

    def to_dict(self) -> dict[str, object]:
        """Return a fresh JSON tree; do not expose mutable nested storage."""
        return {
            "schema_version": TRAJECTORY_SCHEMA_VERSION,
            "episode_id": self.episode_id,
            "step_index": self.step_index,
            "state_before": _json_copy(self.state_before),
            "observation": _json_copy(self.observation),
            "context": self.context,
            "proposal": _json_copy(self.proposal),
            "intent": _json_copy(self.intent),
            "rule_allowed": self.rule_allowed,
            "rule_reason_code": self.rule_reason_code,
            "effects": _json_copy(self.effects),
            "event": _json_copy(self.event),
            "state_after": _json_copy(self.state_after),
            "decision_call_count": self.decision_call_count,
            "provider_request_count": self.provider_request_count,
            "context_chars": self.context_chars,
            "prompt_chars": self.prompt_chars,
            "decision_latency_seconds": self.decision_latency_seconds,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "visible_content_chars": self.visible_content_chars,
            "provider_model": self.provider_model,
            **({"prompt": self.prompt} if self.prompt is not None else {}),
        }


@dataclass(frozen=True)
class EpisodeResult:
    episode_id: str
    success: bool
    termination_reason: TerminationReason
    decision_count: int
    accepted_actions: int
    rejected_actions: int
    invalid_outputs: int
    provider_errors: int
    total_provider_requests: int
    final_state: dict[str, object]
    events: tuple[dict[str, object], ...]
    steps: tuple[StepTrajectory, ...]
    total_input_tokens: int
    total_output_tokens: int
    total_reasoning_tokens: int
    total_latency_seconds: float
    max_context_chars: int
    max_prompt_chars: int
    scenario_name: str = "lunch"
    context_policy_name: str = "baseline_compact"
    decision_policy_name: str = "unknown"
    model_name: str | None = None
    seed: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.episode_id, str) or not self.episode_id:
            raise ValueError("episode_id must be a nonempty string")
        if not isinstance(self.success, bool):
            raise TypeError("success must be a bool")
        if isinstance(self.termination_reason, str):
            object.__setattr__(self, "termination_reason", TerminationReason(self.termination_reason))
        elif not isinstance(self.termination_reason, TerminationReason):
            raise TypeError("termination_reason must be a TerminationReason")
        for field_name in (
            "decision_count", "accepted_actions", "rejected_actions", "invalid_outputs",
            "provider_errors", "total_provider_requests", "total_input_tokens",
            "total_output_tokens", "total_reasoning_tokens", "max_context_chars",
            "max_prompt_chars",
        ):
            _count(getattr(self, field_name), field_name)
        if (
            isinstance(self.total_latency_seconds, bool)
            or not isinstance(self.total_latency_seconds, (int, float))
            or not math.isfinite(self.total_latency_seconds)
            or self.total_latency_seconds < 0
        ):
            raise ValueError("total_latency_seconds must be finite and non-negative")
        if not isinstance(self.steps, tuple) or any(not isinstance(step, StepTrajectory) for step in self.steps):
            raise TypeError("steps must be a tuple of StepTrajectory")
        if not isinstance(self.events, tuple):
            raise TypeError("events must be a tuple")
        object.__setattr__(self, "final_state", _snapshot(self.final_state, "final_state"))
        object.__setattr__(self, "events", tuple(_snapshot(event, "event") for event in self.events))
        for field_name in ("scenario_name", "context_policy_name", "decision_policy_name"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{field_name} must be a nonempty string")
            object.__setattr__(self, field_name, _safe_text(value))
        if self.model_name is not None:
            if not isinstance(self.model_name, str):
                raise TypeError("model_name must be a string or None")
            object.__setattr__(self, "model_name", _safe_text(self.model_name))
        if self.seed is not None and (isinstance(self.seed, bool) or not isinstance(self.seed, int)):
            raise TypeError("seed must be an integer or None")

    def to_dict(self) -> dict[str, object]:
        payload = {
            "schema_version": TRAJECTORY_SCHEMA_VERSION,
            "episode_id": self.episode_id,
            "success": self.success,
            "termination_reason": self.termination_reason.value,
            "decision_count": self.decision_count,
            "accepted_actions": self.accepted_actions,
            "rejected_actions": self.rejected_actions,
            "invalid_outputs": self.invalid_outputs,
            "provider_errors": self.provider_errors,
            "total_provider_requests": self.total_provider_requests,
            "final_state": _json_copy(self.final_state),
            "events": _json_copy(self.events),
            "steps": [step.to_dict() for step in self.steps],
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_reasoning_tokens": self.total_reasoning_tokens,
            "total_latency_seconds": self.total_latency_seconds,
            "max_context_chars": self.max_context_chars,
            "max_prompt_chars": self.max_prompt_chars,
            "scenario_name": self.scenario_name,
            "context_policy_name": self.context_policy_name,
            "decision_policy_name": self.decision_policy_name,
            "model_name": self.model_name,
            "seed": self.seed,
        }
        # Catch any accidental non-JSON extension at the serialization boundary.
        json.dumps(payload, ensure_ascii=False, allow_nan=False)
        return payload
