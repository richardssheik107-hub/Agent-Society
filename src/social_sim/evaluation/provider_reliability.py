"""Fixed-prompt, single-attempt DecisionClient reliability pilot.

This benchmark intentionally has no world, rules, simulation, or model repair.
Only safe envelope facts and token counts are retained; neither the raw final
answer nor hidden reasoning enters any result or artifact.
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
from pathlib import Path
from statistics import mean
from typing import Any

import httpx

from social_sim.decision.client import (
    DecisionClientError,
    DecisionModelClient,
    DecisionReply,
    DecisionResponseMetadata,
    ProviderContractError,
)
from social_sim.decision.config import DecisionProviderConfig
from social_sim.decision.parser import DecisionParseError, DecisionParser


RELIABILITY_REQUESTS = 30
RELIABILITY_SYSTEM_PROMPT = "Return JSON only."
RELIABILITY_USER_PROMPT = 'Return exactly:\n{"action":"MOVE","target":"home"}'
RELIABILITY_PROMPT_CHARS = len(RELIABILITY_SYSTEM_PROMPT) + len(RELIABILITY_USER_PROMPT)
RELIABILITY_PROMPT_HASH = hashlib.sha256(
    json.dumps(
        [RELIABILITY_SYSTEM_PROMPT, RELIABILITY_USER_PROMPT],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()
RELIABILITY_SCHEMA_VERSION = "0.1"
_SAFE_MODEL = re.compile(r"[A-Za-z0-9_.:/-]{1,128}\Z")


def _safe_model(value: object, *, secret: object = None) -> str | None:
    if not isinstance(value, str) or not _SAFE_MODEL.fullmatch(value):
        return None
    if "://" in value or re.fullmatch(r"(?:ark|sk)-[A-Za-z0-9-]{12,}", value):
        return None
    if isinstance(secret, str) and secret and secret in value:
        return None
    return value


def decision_client_config_hash(
    config: DecisionProviderConfig,
    *,
    timeout_seconds: float = 60.0,
    request_mode: str = "MODEL_MESSAGES_ONLY",
    max_retries: int = 0,
) -> str:
    """Hash non-secret contract facts, never the key or literal endpoint URL."""
    if timeout_seconds <= 0 or max_retries < 0:
        raise ValueError("Invalid timeout or retry policy")
    if request_mode != "MODEL_MESSAGES_ONLY":
        raise ValueError("Reliability requires model+messages-only requests")
    descriptor = {
        "provider_base_category": config.base_url_category,
        "model_alias": config.model,
        "request_mode": request_mode,
        "timeout_seconds": float(timeout_seconds),
        "max_retries": max_retries,
    }
    return hashlib.sha256(
        json.dumps(descriptor, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class ProviderRequestResult:
    request_index: int
    success: bool
    failure_type: str | None
    http_status: int | None
    latency_seconds: float
    provider_model: str | None
    finish_reason: str | None
    content_chars: int | None
    input_tokens: int | None
    output_tokens: int | None
    reasoning_tokens: int | None
    started_at: str
    ended_at: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ProviderReliabilityResult:
    requests: tuple[ProviderRequestResult, ...]
    decision_client_config_hash: str | None

    @property
    def reliability_ok(self) -> bool:
        if len(self.requests) != RELIABILITY_REQUESTS:
            return False
        success_rate = sum(item.success for item in self.requests) / len(self.requests)
        timeout_rate = sum(item.failure_type == "TIMEOUT" for item in self.requests) / len(self.requests)
        return success_rate >= 0.95 and timeout_rate <= 0.05

    def summary(self) -> dict[str, object]:
        rows = self.requests
        total = len(rows)
        successes = sum(item.success for item in rows)
        failures = Counter(item.failure_type for item in rows if item.failure_type)
        latencies = [item.latency_seconds for item in rows]
        models = Counter(item.provider_model for item in rows if item.provider_model)
        inputs = [item.input_tokens for item in rows if item.input_tokens is not None]
        outputs = [item.output_tokens for item in rows if item.output_tokens is not None]
        reasoning = [item.reasoning_tokens for item in rows if item.reasoning_tokens is not None]
        return {
            "schema_version": RELIABILITY_SCHEMA_VERSION,
            "experiment_type": "decision_provider_reliability",
            "decision_client_config_hash": self.decision_client_config_hash,
            "request_mode": "MODEL_MESSAGES_ONLY",
            "retry_policy": 0,
            "prompt_chars": RELIABILITY_PROMPT_CHARS,
            "prompt_hash": RELIABILITY_PROMPT_HASH,
            "requests_total": total,
            "requests_success": successes,
            "success_rate": successes / total if total else None,
            "timeout_count": failures["TIMEOUT"],
            "timeout_rate": failures["TIMEOUT"] / total if total else None,
            "http_error_count": failures["HTTP_ERROR"],
            "empty_content_count": failures["EMPTY_CONTENT"],
            "invalid_provider_envelope_count": failures["INVALID_PROVIDER_ENVELOPE"],
            "invalid_json_count": failures["INVALID_JSON"],
            "invalid_action_count": failures["INVALID_ACTION"],
            "failure_type_counts": dict(sorted(failures.items())),
            "avg_latency": float(mean(latencies)) if latencies else None,
            "p50_latency": _percentile(latencies, 0.50),
            "p95_latency": _percentile(latencies, 0.95),
            "max_latency": max(latencies, default=None),
            "input_tokens": sum(inputs) if inputs else None,
            "output_tokens": sum(outputs) if outputs else None,
            "reasoning_tokens": sum(reasoning) if reasoning else None,
            "input_tokens_observed_requests": len(inputs),
            "output_tokens_observed_requests": len(outputs),
            "reasoning_tokens_observed_requests": len(reasoning),
            "provider_model_counts": dict(sorted(models.items())),
            "provider_model_unknown_count": total - sum(models.values()),
            "model_backend_stable": (
                "UNKNOWN" if not models else "NO" if len(models) > 1 else "YES"
            ),
            "reliability_result": "RELIABILITY_OK" if self.reliability_ok else "RELIABILITY_UNSTABLE",
            "reliability_ok": self.reliability_ok,
            "gate_note": "Engineering entry gate only; not a provider SLA or statistical guarantee.",
        }


def _percentile(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return float(ordered[low] + (ordered[high] - ordered[low]) * (position - low))


def _failure_type(error: Exception, metadata: DecisionResponseMetadata | None) -> str:
    if isinstance(error, (httpx.TimeoutException, TimeoutError)):
        return "TIMEOUT"
    if metadata is not None and metadata.http_status is not None and metadata.http_status != 200:
        return "HTTP_ERROR"
    if isinstance(error, ProviderContractError):
        if error.category in (
            "EMPTY_FINAL_CONTENT",
            "EMPTY_FINAL_CONTENT_WITH_REASONING",
            "OUTPUT_BUDGET_EXHAUSTED",
        ):
            return "EMPTY_CONTENT"
        return "INVALID_PROVIDER_ENVELOPE"
    if isinstance(error, DecisionClientError):
        return "PROVIDER_ERROR"
    if isinstance(error, httpx.HTTPError):
        return "NETWORK_ERROR"
    return "CLIENT_ERROR"


def _reply_failure(reply: DecisionReply) -> str | None:
    raw = reply.raw_text
    if not isinstance(raw, str) or not raw.strip():
        return "EMPTY_CONTENT"
    try:
        json.loads(raw)
    except (TypeError, ValueError):
        return "INVALID_JSON"
    try:
        proposal = DecisionParser().parse(raw)
    except DecisionParseError:
        return "INVALID_ACTION"
    if proposal.action.value != "MOVE" or proposal.target != "home":
        return "INVALID_ACTION"
    return None


async def run_provider_reliability(
    client: DecisionModelClient,
    *,
    requests: int = RELIABILITY_REQUESTS,
    config_hash: str | None = None,
    on_result: Callable[[ProviderRequestResult], Any] | None = None,
) -> ProviderReliabilityResult:
    """Run sequential requests, one ``complete`` call per indexed attempt.

    A callback can durably append each safe result before the next attempt. A
    callback failure is an artifact failure and deliberately propagates.
    """
    if requests <= 0:
        raise ValueError("requests must be positive")
    rows: list[ProviderRequestResult] = []
    for index in range(1, requests + 1):
        start_utc = datetime.now(timezone.utc).isoformat()
        started = time.perf_counter()
        reply: DecisionReply | None = None
        error: Exception | None = None
        try:
            reply = await client.complete(RELIABILITY_SYSTEM_PROMPT, RELIABILITY_USER_PROMPT)
        except Exception as caught:  # failures are observations, never prompt/secret logs
            error = caught
        ended = datetime.now(timezone.utc).isoformat()
        # The enclosing measurement includes timed-out attempts and cannot be
        # stale if a client fails before setting its own latency field.
        latency = time.perf_counter() - started
        metadata = getattr(client, "last_metadata", None)
        metadata = metadata if isinstance(metadata, DecisionResponseMetadata) else None
        redaction_secret = getattr(client, "_redaction_secret", None)
        failure = (
            _failure_type(error, metadata) if error is not None else
            _reply_failure(reply) if isinstance(reply, DecisionReply) else
            "INVALID_PROVIDER_ENVELOPE"
        )
        rows.append(
            ProviderRequestResult(
                request_index=index,
                success=failure is None,
                failure_type=failure,
                http_status=metadata.http_status if metadata else None,
                latency_seconds=latency,
                provider_model=_safe_model(
                    reply.provider_model if reply and reply.provider_model else
                    metadata.provider_model if metadata else None,
                    secret=redaction_secret,
                ),
                finish_reason=_safe_model(metadata.finish_reason, secret=redaction_secret) if metadata else None,
                content_chars=(
                    len(reply.raw_text) if reply and isinstance(reply.raw_text, str) else
                    metadata.content_chars if metadata else None
                ),
                input_tokens=(reply.input_tokens if reply else metadata.input_tokens if metadata else None),
                output_tokens=(reply.output_tokens if reply else metadata.output_tokens if metadata else None),
                reasoning_tokens=(reply.reasoning_tokens if reply else metadata.reasoning_tokens if metadata else None),
                started_at=start_utc,
                ended_at=ended,
            )
        )
        if on_result is not None:
            callback_result = on_result(rows[-1])
            if inspect.isawaitable(callback_result):
                await callback_result
    return ProviderReliabilityResult(tuple(rows), config_hash)


def write_provider_reliability_report(
    result: ProviderReliabilityResult, output_dir: Path
) -> tuple[Path, Path]:
    """Write aggregate facts only. Per-request JSONL is caller-controlled."""
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = result.summary()
    json_path = output_dir / "provider_reliability_summary.json"
    md_path = output_dir / "provider_reliability_summary.md"
    with json_path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    lines = [
        "# Decision Provider Reliability Benchmark", "",
        f"Result: {summary['reliability_result']}",
        "Engineering gate: success rate ≥ 0.95 and timeout rate ≤ 0.05 across 30 sequential, single-attempt requests.",
        "This is not a provider SLA or statistical guarantee.",
        "No world, RuleEngine, or Neutral-Day simulation ran in this benchmark.",
        "No prompt body, response body, or reasoning text is stored.", "",
        f"Requests: {summary['requests_total']}",
        f"Successful: {summary['requests_success']}",
        f"Success rate: {summary['success_rate']}",
        f"Timeouts: {summary['timeout_count']}",
        f"Timeout rate: {summary['timeout_rate']}",
        f"HTTP errors: {summary['http_error_count']}",
        f"Empty content: {summary['empty_content_count']}",
        f"Invalid provider envelope: {summary['invalid_provider_envelope_count']}",
        f"Invalid JSON: {summary['invalid_json_count']}",
        f"Invalid action: {summary['invalid_action_count']}",
        f"Latency avg / p50 / p95 / max (seconds): {summary['avg_latency']} / {summary['p50_latency']} / {summary['p95_latency']} / {summary['max_latency']}",
        f"Observed input / output / reasoning tokens: {summary['input_tokens']} / {summary['output_tokens']} / {summary['reasoning_tokens']}",
        f"Provider models: {json.dumps(summary['provider_model_counts'], sort_keys=True)}",
        f"MODEL_BACKEND_STABLE={summary['model_backend_stable']}",
        f"Decision client config hash: {summary['decision_client_config_hash']}",
    ]
    with md_path.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")
    return json_path, md_path
