"""Auditable Q4 context and prompt construction."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from .models import ResourceProjection, ResourceScenario


RESOURCE_SYSTEM = "Choose one next action for a simulated person. Return JSON only. Do not explain."
RESOURCE_USER_PREFIX = (
    "Context contains current objective facts and a visible personal-resource block. "
    "Return exactly an object with action and target. "
    "For MOVE, BUY, or EAT use one listed target; otherwise use target:null.\n"
)


@dataclass(frozen=True)
class ResourcePrompt:
    system: str
    user: str
    context: str

    @property
    def context_chars(self) -> int:
        return len(self.context)

    @property
    def prompt_chars(self) -> int:
        return len(self.system) + len(self.user)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_resource_context(scenario: ResourceScenario, projection: ResourceProjection) -> str:
    """Serialize fixed context plus exactly one visible resource projection."""
    context = {
        "p": {"name": "Alex", "goal": "handle current needs and obligations"},
        "s": {
            "t": scenario.time,
            "loc": scenario.location,
            "prev": scenario.previous_activity,
            "events": list(scenario.recent_events),
        },
        "prior": list(scenario.behavior_prior),
        "a": [action.value for action in scenario.available_actions],
        "targets": list(scenario.available_targets),
        "objects": dict(scenario.world_facts),
        "r": dict(projection.values),
    }
    return _json(context)


def context_without_resources(context: str) -> str:
    payload = json.loads(context)
    if not isinstance(payload, dict) or "r" not in payload:
        raise ValueError("resource context must contain exactly one r block")
    del payload["r"]
    return _json(payload)


def build_resource_prompt(scenario: ResourceScenario, projection: ResourceProjection) -> ResourcePrompt:
    context = build_resource_context(scenario, projection)
    return ResourcePrompt(RESOURCE_SYSTEM, RESOURCE_USER_PREFIX + "Context:" + context, context)


def prompt_without_resources(prompt: ResourcePrompt) -> str:
    return prompt.system + "\n" + RESOURCE_USER_PREFIX + "Context:" + context_without_resources(prompt.context)


def prompt_hash(prompt: ResourcePrompt) -> str:
    return hashlib.sha256((prompt.system + prompt.user).encode("utf-8")).hexdigest()


def fixed_context_signature(scenario: ResourceScenario) -> str:
    """Stable signature for everything that must be common across arms."""
    payload = {
        "time": scenario.time,
        "location": scenario.location,
        "previous_activity": scenario.previous_activity,
        "recent_events": scenario.recent_events,
        "behavior_prior": scenario.behavior_prior,
        "world_facts": scenario.world_facts,
        "available_actions": tuple(action.value for action in scenario.available_actions),
        "available_targets": scenario.available_targets,
    }
    return hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()
