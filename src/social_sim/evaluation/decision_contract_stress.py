"""World-free, single-attempt Neutral-Day decision output contract pilot.

Prepared local observations flow through the production ContextCompiler and
PromptBuilder. No rule, reducer, environment model, or world transition runs.
Only assistant final visible text can enter the bounded, redacted excerpt.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import re
import time
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from statistics import mean
from typing import Any

import httpx

from social_sim.context import C3Recent3Policy, ContextCompiler
from social_sim.daily.persona import NeutralPersona
from social_sim.daily.runner import DAILY_ACTIONS, DAILY_TARGETS
from social_sim.decision.client import (
    DecisionClientError, DecisionModelClient, DecisionReply,
    DecisionResponseMetadata, ProviderContractError,
)
from social_sim.decision.parser import DecisionParser
from social_sim.decision.prompt import MAX_CONTEXT_CHARS, DecisionPrompt, build_decision_prompt
from social_sim.evaluation.provider_reliability import _percentile, _safe_model
from social_sim.world.observation import LocalObservation


STRESS_REPEATS = 3
STRESS_CASE_COUNT = 12
STRESS_REQUESTS = STRESS_CASE_COUNT * STRESS_REPEATS
STRESS_SCHEMA_VERSION = "0.1"
WORK_WINDOW = "09:00-17:00"
ALLOWED_REPAIRS = frozenset({"STRIP_CODE_FENCE", "EXTRACT_SINGLE_JSON", "ADD_NULL_TARGET"})
_SAFE_ATOM = re.compile(r"[A-Za-z0-9_.:/-]{1,128}\Z")
_TOKEN_LIKE = re.compile(r"(?i)(?:ark|sk)-[A-Za-z0-9-]{12,}")
_BEARER = re.compile(r"(?i)\bbearer\s+\S+")
_SENSITIVE_LABEL = re.compile(r"(?i)authorization|api[_-]?key|reasoning[_-]?content")
_THINK = re.compile(r"(?i)<\s*think\b")


@dataclass(frozen=True)
class StressCase:
    case_id: str
    time: str
    location: str
    hunger: float
    energy: float
    inventory_meals: int | None = None
    feedback: str | None = None
    work_due: bool = False

    def observation(self) -> LocalObservation:
        offers = {"meal": {"price": 20.0, "available": True}} if self.location == "restaurant" else {}
        inventory = {"meal": self.inventory_meals} if self.inventory_meals is not None else {}
        return LocalObservation(
            agent_id=1,
            time=f"2026-01-01T{self.time}:00+00:00",
            location=self.location,
            money=100.0,
            hunger=self.hunger,
            inventory=inventory,
            offers=offers,
            energy=self.energy,
        )


STRESS_CASES = (
    StressCase("D1_0600_HOME", "06:00", "home", .30, .80),
    StressCase("D2_0830_HOME", "08:30", "home", .55, .80, work_due=True),
    StressCase("D3_0900_OFFICE", "09:00", "office", .48, .75, work_due=True),
    StressCase("D4_1200_OFFICE_HUNGRY", "12:00", "office", .82, .60, work_due=True),
    StressCase("D5_1230_RESTAURANT_NO_MEAL", "12:30", "restaurant", .85, .56, inventory_meals=0, work_due=True),
    StressCase("D6_1300_RESTAURANT_ONE_MEAL", "13:00", "restaurant", .88, .53, inventory_meals=1, work_due=True),
    StressCase("D7_1730_OFFICE", "17:30", "office", .55, .50),
    StressCase("D8_2230_HOME", "22:30", "home", .30, .20),
    StressCase("F1_NOT_AT_SELLER", "12:00", "office", .82, .60, feedback="ACTION_REJECTED:NOT_AT_SELLER", work_due=True),
    StressCase("F2_WORK_COMPLETED", "17:30", "office", .55, .50, feedback="WORK_COMPLETED"),
    StressCase("F3_LEISURE_COMPLETED", "22:30", "home", .30, .20, feedback="LEISURE_COMPLETED"),
    StressCase("F4_NOT_AT_WORKPLACE", "09:00", "home", .50, .77, feedback="ACTION_REJECTED:NOT_AT_WORKPLACE", work_due=True),
)


@dataclass(frozen=True)
class ScheduledRequest:
    request_index: int
    round_index: int
    case_id: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def stress_schedule() -> tuple[ScheduledRequest, ...]:
    """Three distinct rotations; case repeats never occur back-to-back."""
    if len(STRESS_CASES) != STRESS_CASE_COUNT or len({case.case_id for case in STRESS_CASES}) != STRESS_CASE_COUNT:
        raise AssertionError("Stress cases must be twelve unique fixed cases")
    rows: list[ScheduledRequest] = []
    for round_index, offset in enumerate((0, 4, 8), start=1):
        rotated = STRESS_CASES[offset:] + STRESS_CASES[:offset]
        for case in rotated:
            rows.append(ScheduledRequest(len(rows) + 1, round_index, case.case_id))
    assert len(rows) == STRESS_REQUESTS
    assert all(left.case_id != right.case_id for left, right in zip(rows, rows[1:]))
    return tuple(rows)


def prepare_stress_prompt(case: StressCase) -> tuple[str, DecisionPrompt]:
    """Use the actual B0 context/prompt pipeline, without a provider request."""
    observation = case.observation()
    profile = NeutralPersona().profile()
    history = (case.feedback,) if case.feedback else ()
    selected_events = C3Recent3Policy().select_events(history, observation, profile["goal"])
    context = ContextCompiler(max_chars=MAX_CONTEXT_CHARS).compile(
        profile, observation,
        available_actions=[action.value for action in DAILY_ACTIONS],
        available_targets=DAILY_TARGETS,
        events=selected_events,
        daily_mode=True,
        work_window=WORK_WINDOW,
        behavior_hints=(),
    )
    return context, build_decision_prompt(context, daily_mode=True)


def _prompt_hash(prompt: DecisionPrompt) -> str:
    return hashlib.sha256(json.dumps(
        [prompt.system, prompt.user], ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def sanitize_visible_output(value: object, *, secrets: Sequence[str] = ()) -> str | None:
    """Bounded final-visible excerpt; never permit visible chain-of-thought leaks."""
    if not isinstance(value, str):
        return None
    # Treat even an unclosed visible think tag as unsafe from its first byte.
    matches = tuple(match for match in (_THINK.search(value), _SENSITIVE_LABEL.search(value)) if match)
    if matches:
        value = value[:min(match.start() for match in matches)] + "[REDACTED_SENSITIVE_VISIBLE_CONTENT]"
    for secret in secrets:
        if isinstance(secret, str) and secret:
            value = value.replace(secret, "[REDACTED]")
    value = _TOKEN_LIKE.sub("[REDACTED]", value)
    value = _BEARER.sub("[REDACTED]", value)
    return value[:500]


def _safe_atom(value: object, *, secret: object = None) -> str | None:
    if not isinstance(value, str) or not _SAFE_ATOM.fullmatch(value):
        return None
    if "//" in value or _TOKEN_LIKE.fullmatch(value):
        return None
    if isinstance(secret, str) and secret and secret in value:
        return None
    return value


def _provider_failure_type(error: Exception) -> str:
    if isinstance(error, (httpx.TimeoutException, TimeoutError)):
        return "TIMEOUT"
    if isinstance(error, ProviderContractError):
        return {
            "EMPTY_FINAL_CONTENT": "EMPTY_CONTENT",
            "EMPTY_FINAL_CONTENT_WITH_REASONING": "EMPTY_CONTENT",
        }.get(error.category, error.category if error.category in {
            "PROVIDER_REFUSAL", "TOOL_CALL_INSTEAD_OF_TEXT", "NO_CHOICES",
            "OUTPUT_BUDGET_EXHAUSTED", "PROVIDER_SCHEMA_MISMATCH",
        } else "PROVIDER_SCHEMA_MISMATCH")
    if isinstance(error, httpx.HTTPStatusError):
        return "HTTP_ERROR"
    if isinstance(error, DecisionClientError):
        return "HTTP_ERROR" if str(error).startswith("Provider returned HTTP ") else "PROVIDER_ERROR"
    if isinstance(error, httpx.HTTPError):
        return "NETWORK_ERROR"
    return "CLIENT_ERROR"


@dataclass(frozen=True)
class StressRequestResult:
    case_id: str
    request_index: int
    round_index: int
    started_at: str
    ended_at: str
    context_chars: int
    prompt_chars: int
    prompt_hash: str
    provider_success: bool
    provider_failure_type: str | None
    http_status: int | None
    provider_model: str | None
    finish_reason: str | None
    content_exists: bool | None
    content_chars: int | None
    reasoning_field_exists: bool | None
    reasoning_chars: int | None
    refusal_exists: bool | None
    tool_calls_count: int | None
    input_tokens: int | None
    output_tokens: int | None
    reasoning_tokens: int | None
    sanitized_visible_output: str | None
    strict_valid: bool
    recoverable_valid: bool
    failure_type: str | None
    failure_category: str | None
    repair_applied: str | None
    json_object_count: int | None
    latency_seconds: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class DecisionContractStressResult:
    requests: tuple[StressRequestResult, ...]

    def summary(self) -> dict[str, object]:
        rows = self.requests
        total = len(rows)
        success = sum(row.provider_success for row in rows)
        strict = sum(row.strict_valid for row in rows)
        recoverable = sum(row.recoverable_valid for row in rows)
        semantic = sum(
            row.failure_category == "SEMANTIC_FAILURE" and not row.recoverable_valid
            for row in rows
        )
        format_failed = sum(row.failure_category == "FORMAT_FAILURE" for row in rows)
        latencies = [row.latency_seconds for row in rows]
        models = Counter(row.provider_model for row in rows if row.provider_model)
        counts = Counter(row.failure_type for row in rows if row.failure_type)
        repairs = Counter(row.repair_applied for row in rows if row.repair_applied)
        by_case = {}
        for case in STRESS_CASES:
            case_rows = [row for row in rows if row.case_id == case.case_id]
            by_case[case.case_id] = {
                "requests": len(case_rows),
                "strict_valid": sum(row.strict_valid for row in case_rows),
                "recoverable_valid": sum(row.recoverable_valid for row in case_rows),
                "semantic_invalid": sum(
                    row.failure_category == "SEMANTIC_FAILURE" and not row.recoverable_valid
                    for row in case_rows
                ),
                "avg_latency": float(mean(row.latency_seconds for row in case_rows)) if case_rows else None,
            }
        gate = (
            total == STRESS_REQUESTS
            and success / total >= .95
            and recoverable / total >= .95
            and semantic / total <= .05
        ) if total else False
        repair_components = {part for repair in repairs for part in repair.split("+")}
        allowed_repair_types = repair_components.issubset(ALLOWED_REPAIRS)
        return {
            "schema_version": STRESS_SCHEMA_VERSION,
            "experiment_type": "decision_output_contract_stress",
            "requests_total": total,
            "provider_success_count": success,
            "provider_failure_count": total - success,
            "provider_success_rate": success / total if total else None,
            "strict_valid_count": strict,
            "strict_valid_rate": strict / total if total else None,
            "recoverable_valid_count": recoverable,
            "recoverable_valid_rate": recoverable / total if total else None,
            "semantic_invalid_count": semantic,
            "semantic_invalid_rate": semantic / total if total else None,
            "format_failure_count": format_failed,
            "format_failure_rate": format_failed / total if total else None,
            "failure_type_counts": dict(sorted(counts.items())),
            "repair_applied_counts": dict(sorted(repairs.items())),
            "case_metrics": by_case,
            "avg_latency": float(mean(latencies)) if latencies else None,
            "p50_latency": _percentile(latencies, .50),
            "p95_latency": _percentile(latencies, .95),
            "provider_model_counts": dict(sorted(models.items())),
            "model_backend_stable": "UNKNOWN" if not models else "YES" if len(models) == 1 else "NO",
            "input_tokens": sum(row.input_tokens for row in rows if row.input_tokens is not None) if any(row.input_tokens is not None for row in rows) else None,
            "output_tokens": sum(row.output_tokens for row in rows if row.output_tokens is not None) if any(row.output_tokens is not None for row in rows) else None,
            "reasoning_tokens": sum(row.reasoning_tokens for row in rows if row.reasoning_tokens is not None) if any(row.reasoning_tokens is not None for row in rows) else None,
            "input_tokens_observed_requests": sum(row.input_tokens is not None for row in rows),
            "output_tokens_observed_requests": sum(row.output_tokens is not None for row in rows),
            "reasoning_tokens_observed_requests": sum(row.reasoning_tokens is not None for row in rows),
            "engineering_gate_pass": gate,
            "recovery_recommended_for_full_day": gate and strict < recoverable and allowed_repair_types,
            "repairs_within_allowed_list": allowed_repair_types,
            "gate_note": "Engineering pilot gate only; 36 sequential requests do not establish statistical significance.",
        }


async def run_decision_contract_stress(
    client: DecisionModelClient,
    *,
    schedule: Sequence[ScheduledRequest] | None = None,
    secrets: Sequence[str] = (),
    on_result: Callable[[StressRequestResult], Any] | None = None,
) -> DecisionContractStressResult:
    """One complete() call per scheduled item; no retry or world execution."""
    items = tuple(schedule if schedule is not None else stress_schedule())
    if not items or any(item.case_id not in {case.case_id for case in STRESS_CASES} for item in items):
        raise ValueError("schedule must contain known cases")
    cases = {case.case_id: case for case in STRESS_CASES}
    parser = DecisionParser()
    rows: list[StressRequestResult] = []
    redaction_secrets = tuple(secrets) + (getattr(client, "_redaction_secret", ""),)
    for item in items:
        context, prompt = prepare_stress_prompt(cases[item.case_id])
        started_at = datetime.now(timezone.utc).isoformat()
        started = time.perf_counter()
        metadata_before = getattr(client, "last_metadata", None)
        reply: DecisionReply | None = None
        error: Exception | None = None
        try:
            reply = await client.complete(prompt.system, prompt.user)
        except Exception as caught:
            error = caught
        latency = time.perf_counter() - started
        ended_at = datetime.now(timezone.utc).isoformat()
        current_metadata = getattr(client, "last_metadata", None)
        metadata = getattr(error, "metadata", None) if error else None
        if metadata is None and current_metadata is not metadata_before:
            metadata = current_metadata
        metadata = metadata if isinstance(metadata, DecisionResponseMetadata) else None
        raw = reply.raw_text if isinstance(reply, DecisionReply) else None
        provider_failure = _provider_failure_type(error) if error is not None else None
        # A malformed client reply is a provider-side envelope failure, never a parser failure.
        if error is None and not isinstance(reply, DecisionReply):
            provider_failure = "PROVIDER_SCHEMA_MISMATCH"
        if error is None and isinstance(reply, DecisionReply) and not isinstance(raw, str):
            provider_failure = "PROVIDER_SCHEMA_MISMATCH"
        if error is None and isinstance(raw, str) and not raw.strip():
            provider_failure = "EMPTY_CONTENT"
        provider_success = provider_failure is None
        parse = parser.evaluate(raw, available_actions=DAILY_ACTIONS, available_targets=DAILY_TARGETS) if provider_success else None
        rows.append(StressRequestResult(
            case_id=item.case_id,
            request_index=item.request_index,
            round_index=item.round_index,
            started_at=started_at,
            ended_at=ended_at,
            context_chars=len(context),
            prompt_chars=prompt.prompt_chars,
            prompt_hash=_prompt_hash(prompt),
            provider_success=provider_success,
            provider_failure_type=provider_failure,
            http_status=metadata.http_status if metadata else None,
            provider_model=_safe_model(
                reply.provider_model if isinstance(reply, DecisionReply) and reply.provider_model else metadata.provider_model if metadata else None,
                secret=getattr(client, "_redaction_secret", None),
            ),
            finish_reason=_safe_atom(metadata.finish_reason, secret=getattr(client, "_redaction_secret", None)) if metadata else None,
            content_exists=isinstance(raw, str) if isinstance(reply, DecisionReply) else (
                not metadata.content_is_none if metadata and metadata.content_is_none is not None else None
            ),
            content_chars=len(raw) if isinstance(raw, str) else metadata.content_chars if metadata else None,
            reasoning_field_exists=metadata.reasoning_field_exists if metadata else None,
            reasoning_chars=metadata.reasoning_chars if metadata else None,
            refusal_exists=metadata.refusal_field_exists if metadata else None,
            tool_calls_count=metadata.tool_calls_count if metadata else None,
            input_tokens=reply.input_tokens if isinstance(reply, DecisionReply) else metadata.input_tokens if metadata else None,
            output_tokens=reply.output_tokens if isinstance(reply, DecisionReply) else metadata.output_tokens if metadata else None,
            reasoning_tokens=reply.reasoning_tokens if isinstance(reply, DecisionReply) else metadata.reasoning_tokens if metadata else None,
            sanitized_visible_output=sanitize_visible_output(raw, secrets=redaction_secrets),
            strict_valid=parse.strict_valid if parse and provider_success else False,
            recoverable_valid=parse.recoverable_valid if parse and provider_success else False,
            failure_type=provider_failure or (parse.failure_type if parse else None),
            failure_category="PROVIDER_FAILURE" if provider_failure else parse.failure_category if parse else None,
            repair_applied=parse.repair_applied if parse and provider_success else None,
            json_object_count=parse.json_object_count if parse and provider_success else None,
            latency_seconds=latency,
        ))
        if on_result is not None:
            callback = on_result(rows[-1])
            if inspect.isawaitable(callback):
                await callback
    return DecisionContractStressResult(tuple(rows))
