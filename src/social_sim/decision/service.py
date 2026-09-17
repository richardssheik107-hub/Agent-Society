"""One compact decision call; a proposal is never applied to the world."""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Mapping, Sequence

from social_sim.context import C3Recent3Policy, ContextCompiler, ContextPolicy
from social_sim.world.observation import LocalObservation

from .client import DecisionModelClient
from .models import ActionType, DecisionProposal
from .parser import DecisionParseError, DecisionParser
from .prompt import MAX_CONTEXT_CHARS, build_decision_prompt


@dataclass(frozen=True)
class DecisionResult:
    proposal: DecisionProposal
    context: str
    system_prompt: str
    user_prompt: str
    context_chars: int
    prompt_chars: int
    raw_output_chars: int
    latency_seconds: float
    input_tokens: int | None
    output_tokens: int | None
    reasoning_tokens: int | None
    provider_model: str | None
    provider_request_count: int
    strict_valid: bool | None = None
    recoverable_valid: bool | None = None
    failure_type: str | None = None
    repair_applied: str | None = None
    repair_available: str | None = None
    output_recovered: bool = False
    legacy_non_strict_acceptance: bool = False
    response_diagnostics: dict[str, object] | None = None


_SAFE_IDENTIFIER = re.compile(r"[A-Za-z0-9_.:/-]{1,128}\Z")


def _safe_identifier(value: object, secret: object = None) -> str | None:
    if not isinstance(value, str) or not _SAFE_IDENTIFIER.fullmatch(value):
        return None
    if isinstance(secret, str) and secret and secret in value:
        return None
    if "://" in value or re.fullmatch(r"(?:ark|sk)-[A-Za-z0-9-]{12,}", value):
        return None
    return value


def _recovery_flag() -> bool:
    value = os.getenv("ALLOW_DETERMINISTIC_OUTPUT_RECOVERY", "false").strip().lower()
    if value in {"1", "true", "yes"}:
        return True
    if value in {"0", "false", "no", ""}:
        return False
    raise ValueError("ALLOW_DETERMINISTIC_OUTPUT_RECOVERY must be a boolean")


class CompactDecisionService:
    """Compile local facts, make exactly one model call, and parse its proposal."""

    def __init__(
        self,
        client: DecisionModelClient,
        compiler: ContextCompiler | None = None,
        parser: DecisionParser | None = None,
        context_policy: ContextPolicy | None = None,
        allow_deterministic_output_recovery: bool | None = None,
    ) -> None:
        self.client = client
        self.compiler = compiler or ContextCompiler(max_chars=MAX_CONTEXT_CHARS)
        self.parser = parser or DecisionParser()
        # Legacy direct callers pass an already bounded recent-three list.
        # An explicitly injected policy instead receives the complete log and
        # performs its own selection (needed to rescue a buried rejection).
        self.accepts_full_event_history = context_policy is not None
        self.context_policy = context_policy or C3Recent3Policy()
        if allow_deterministic_output_recovery is not None and not isinstance(
            allow_deterministic_output_recovery, bool
        ):
            raise TypeError("allow_deterministic_output_recovery must be a bool")
        self.allow_deterministic_output_recovery = (
            _recovery_flag() if allow_deterministic_output_recovery is None
            else allow_deterministic_output_recovery
        )
        self.decision_call_count = 0
        self.last_output_diagnostic: dict[str, object] | None = None

    async def decide(
        self,
        profile: Mapping[str, object],
        observation: LocalObservation,
        *,
        available_actions: Sequence[ActionType | str] = (
            ActionType.WAIT,
            ActionType.REST,
            ActionType.MOVE,
        ),
        available_targets: Sequence[str] = (),
        recent_events: Sequence[str] | None = None,
        daily_mode: bool = False,
        work_window: str | None = None,
        behavior_hints: Sequence[str] | None = None,
    ) -> DecisionResult:
        actions = tuple(ActionType(action) for action in available_actions)
        if not actions or len(set(actions)) != len(actions):
            raise ValueError("available_actions must be nonempty and unique")
        if isinstance(available_targets, (str, bytes)):
            raise TypeError("available_targets must be a sequence of target IDs")
        targets = tuple(available_targets)
        if any(
            not isinstance(target, str)
            or not target.strip()
            or len(target) > ContextCompiler.MAX_ACTION_STRING_CHARS
            for target in targets
        ):
            raise ValueError("available_targets must contain short nonempty IDs")
        if len(set(targets)) != len(targets):
            raise ValueError("available_targets must be unique")

        if isinstance(recent_events, (str, bytes)):
            raise TypeError("recent_events must be a sequence of compact strings")
        history = tuple(recent_events) if recent_events is not None else ()
        if not self.accepts_full_event_history and len(history) > ContextCompiler.MAX_EVENTS:
            raise ValueError("recent_events exceeds maximum item count")
        goal = profile.get("goal")
        selected_events = self.context_policy.select_events(
            history, observation, goal if isinstance(goal, str) else ""
        )

        context = self.compiler.compile(
            profile,
            observation,
            available_actions=[action.value for action in actions],
            available_targets=targets,
            events=selected_events,
            daily_mode=daily_mode,
            work_window=work_window,
            behavior_hints=behavior_hints,
        )
        prompt = build_decision_prompt(context, daily_mode=daily_mode)
        self.decision_call_count += 1
        self.last_output_diagnostic = None
        start = time.perf_counter()
        reply = await self.client.complete(prompt.system, prompt.user)
        latency = time.perf_counter() - start
        # Capture the response envelope before parsing, including for malformed
        # output. No visible or hidden text is copied into this diagnostic.
        metadata = getattr(self.client, "last_metadata", None)
        secret = getattr(self.client, "_redaction_secret", None)
        diagnostic: dict[str, object] = {
            "latency_seconds": latency,
            "provider_model": _safe_identifier(
                getattr(metadata, "provider_model", None) or reply.provider_model, secret
            ),
            "finish_reason": _safe_identifier(getattr(metadata, "finish_reason", None), secret),
            "content_exists": bool(reply.raw_text),
            "content_chars": len(reply.raw_text),
            "reasoning_field_exists": getattr(metadata, "reasoning_field_exists", None),
            "reasoning_chars": getattr(metadata, "reasoning_chars", None),
            "input_tokens": reply.input_tokens,
            "output_tokens": reply.output_tokens,
            "reasoning_tokens": reply.reasoning_tokens,
            "refusal_exists": getattr(metadata, "refusal_field_exists", None),
            "tool_calls_count": getattr(metadata, "tool_calls_count", None),
        }
        self.last_output_diagnostic = diagnostic
        parsed = self.parser.evaluate(
            reply.raw_text, available_actions=actions, available_targets=targets
        )
        diagnostic.update(
            strict_valid=parsed.strict_valid,
            recoverable_valid=parsed.recoverable_valid,
            failure_type=parsed.failure_type,
            failure_category=parsed.failure_category,
            repair_available=parsed.repair_applied,
            repair_applied=(
                parsed.repair_applied if self.allow_deterministic_output_recovery else None
            ),
            json_object_count=parsed.json_object_count,
        )
        if self.allow_deterministic_output_recovery:
            if not parsed.recoverable_valid or parsed.proposal is None:
                raise DecisionParseError(parsed.failure_type or "INVALID_MODEL_OUTPUT")
            proposal = parsed.proposal
        else:
            # Preserve the frozen production acceptance semantics until the
            # separately gated full-day rerun opts into deterministic recovery.
            proposal = self.parser.parse(reply.raw_text)
        if proposal.action not in actions:
            raise DecisionParseError("ACTION_NOT_AVAILABLE_FOR_PROFILE")
        if proposal.action in (ActionType.MOVE, ActionType.BUY, ActionType.EAT):
            if proposal.target not in targets:
                raise DecisionParseError(
                    f"{proposal.action.value} target is not currently available"
                )
        legacy_non_strict_acceptance = (
            not self.allow_deterministic_output_recovery and not parsed.strict_valid
        )
        diagnostic["legacy_non_strict_acceptance"] = legacy_non_strict_acceptance
        return DecisionResult(
            proposal=proposal,
            context=context,
            system_prompt=prompt.system,
            user_prompt=prompt.user,
            context_chars=prompt.context_chars,
            prompt_chars=prompt.prompt_chars,
            raw_output_chars=len(reply.raw_text),
            latency_seconds=latency,
            input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens,
            reasoning_tokens=reply.reasoning_tokens,
            provider_model=diagnostic["provider_model"],
            provider_request_count=reply.provider_request_count,
            strict_valid=parsed.strict_valid,
            recoverable_valid=parsed.recoverable_valid,
            failure_type=parsed.failure_type,
            repair_applied=diagnostic["repair_applied"],
            repair_available=parsed.repair_applied,
            output_recovered=self.allow_deterministic_output_recovery and bool(parsed.repair_applied),
            legacy_non_strict_acceptance=legacy_non_strict_acceptance,
            response_diagnostics=dict(diagnostic),
        )
