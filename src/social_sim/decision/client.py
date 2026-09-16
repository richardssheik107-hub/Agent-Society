"""Replaceable single-request client for an OpenAI-compatible chat endpoint."""

from __future__ import annotations

import re
import time
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Protocol

import httpx


@dataclass(frozen=True)
class DecisionReply:
    raw_text: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    provider_model: str | None = None
    provider_request_count: int = 0


class DecisionModelClient(Protocol):
    async def complete(self, system_prompt: str, user_prompt: str) -> DecisionReply:
        """Return one raw completion; callers never request a model repair."""
        ...


class DecisionClientError(RuntimeError):
    """A single provider request failed or returned an unusable wire response."""


@dataclass(frozen=True)
class DecisionResponseMetadata:
    """Safe response-envelope facts; never contains final or reasoning text."""

    http_status: int | None = None
    http_error_code: str | None = None
    http_error_type: str | None = None
    http_error_param: str | None = None
    request_id: str | None = None
    sanitized_error_message: str | None = None
    response_id_present: bool | None = None
    provider_model: str | None = None
    choices_count: int | None = None
    finish_reason: str | None = None
    content_is_none: bool | None = None
    content_type: str | None = None
    content_chars: int | None = None
    reasoning_field_exists: bool | None = None
    reasoning_chars: int | None = None
    refusal_field_exists: bool | None = None
    refusal_chars: int | None = None
    tool_calls_count: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    reasoning_tokens: int | None = None

    def safe_dict(self) -> dict[str, object]:
        return asdict(self)


class ProviderContractError(DecisionClientError):
    """A provider response violated the final-text decision contract."""

    def __init__(self, category: str, metadata: DecisionResponseMetadata) -> None:
        self.category = category
        self.metadata = metadata
        super().__init__(category)


class FakeDecisionClient:
    """A no-network response source for deterministic pipeline tests."""

    def __init__(self, raw_text: str) -> None:
        self.raw_text = raw_text
        self.call_count = 0

    async def complete(self, system_prompt: str, user_prompt: str) -> DecisionReply:
        self.call_count += 1
        return DecisionReply(self.raw_text)


def _token(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _safe_error_atom(value: object) -> str | None:
    """Keep only short enum-like error identifiers, never provider messages."""
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", value):
        return value
    return None


def _safe_request_id(value: object) -> str | None:
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value):
        return value
    return None


def _sanitized_error_message(value: object, api_key: str) -> str | None:
    if not isinstance(value, str):
        return None
    # An error message must never become an accidental reasoning-text log.
    if re.search(r"(?i)\b(?:private|reasoning|reasoning_content)\b|<think", value):
        return "[REDACTED]"
    cleaned = value.replace(api_key, "[REDACTED]")
    cleaned = re.sub(r"(?i)Bearer\s+\S+", "Bearer [REDACTED]", cleaned)
    cleaned = re.sub(r"(?i)(?:ark|sk)-[A-Za-z0-9-]{12,}", "[REDACTED]", cleaned)
    return cleaned[:160]


def inspect_chat_completion(
    payload: object, *, http_status: int | None = None
) -> tuple[str, DecisionResponseMetadata]:
    """Extract only assistant final content from one Chat Completions choice.

    Reasoning and refusal text are counted, never returned or retained.
    """
    base = DecisionResponseMetadata(http_status=http_status)
    if not isinstance(payload, Mapping):
        raise ProviderContractError("PROVIDER_SCHEMA_MISMATCH", base)

    usage = payload.get("usage")
    usage = usage if isinstance(usage, Mapping) else {}
    details = usage.get("completion_tokens_details")
    details = details if isinstance(details, Mapping) else {}
    common = dict(
        http_status=http_status,
        response_id_present=isinstance(payload.get("id"), str) and bool(payload.get("id")),
        provider_model=payload.get("model") if isinstance(payload.get("model"), str) else None,
        input_tokens=_token(usage.get("prompt_tokens")),
        output_tokens=_token(usage.get("completion_tokens")),
        total_tokens=_token(usage.get("total_tokens")),
        reasoning_tokens=_token(details.get("reasoning_tokens")),
    )
    choices = payload.get("choices")
    if not isinstance(choices, list):
        raise ProviderContractError(
            "PROVIDER_SCHEMA_MISMATCH", DecisionResponseMetadata(**common)
        )
    common["choices_count"] = len(choices)
    if not choices:
        raise ProviderContractError("NO_CHOICES", DecisionResponseMetadata(**common))
    if len(choices) != 1 or not isinstance(choices[0], Mapping):
        raise ProviderContractError(
            "PROVIDER_SCHEMA_MISMATCH", DecisionResponseMetadata(**common)
        )

    choice = choices[0]
    common["finish_reason"] = (
        choice.get("finish_reason") if isinstance(choice.get("finish_reason"), str) else None
    )
    message = choice.get("message")
    if not isinstance(message, Mapping):
        raise ProviderContractError(
            "PROVIDER_SCHEMA_MISMATCH", DecisionResponseMetadata(**common)
        )

    content = message.get("content")
    reasoning_fields = ("reasoning_content", "reasoning", "think")
    reasoning_values = [message[key] for key in reasoning_fields if key in message]
    refusal = message.get("refusal")
    tool_calls = message.get("tool_calls")
    common.update(
        content_is_none=content is None,
        content_type=type(content).__name__,
        content_chars=len(content) if isinstance(content, str) else 0,
        reasoning_field_exists=bool(reasoning_values),
        reasoning_chars=sum(len(value) for value in reasoning_values if isinstance(value, str)),
        refusal_field_exists="refusal" in message,
        refusal_chars=len(refusal) if isinstance(refusal, str) else 0,
        tool_calls_count=len(tool_calls) if isinstance(tool_calls, list) else 0,
    )
    metadata = DecisionResponseMetadata(**common)
    if isinstance(content, str) and content.strip():
        return content, metadata
    if content is not None and not isinstance(content, str):
        raise ProviderContractError("PROVIDER_SCHEMA_MISMATCH", metadata)
    if metadata.finish_reason == "length":
        category = "OUTPUT_BUDGET_EXHAUSTED"
    elif metadata.refusal_chars:
        category = "PROVIDER_REFUSAL"
    elif metadata.tool_calls_count:
        category = "TOOL_CALL_INSTEAD_OF_TEXT"
    elif metadata.reasoning_chars:
        category = "EMPTY_FINAL_CONTENT_WITH_REASONING"
    elif "content" not in message:
        category = "PROVIDER_SCHEMA_MISMATCH"
    else:
        category = "EMPTY_FINAL_CONTENT"
    raise ProviderContractError(category, metadata)


class OpenAICompatibleDecisionClient:
    """One Chat Completions POST, with no application or transport retries."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 60.0,
        max_tokens: int = 64,
        temperature: float = 0.0,
        thinking_disabled: bool = False,
        minimal_request: bool = False,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not base_url or not api_key or not model:
            raise ValueError("base_url, api_key, and model are required")
        if not 0 < timeout_seconds <= 60:
            raise ValueError("timeout_seconds must be within (0, 60]")
        if not 0 < max_tokens <= 128:
            raise ValueError("max_tokens must be within (0, 128]")
        if not 0 <= temperature <= 0.2:
            raise ValueError("temperature must be within [0, 0.2]")
        if not isinstance(thinking_disabled, bool):
            raise TypeError("thinking_disabled must be a bool")
        if not isinstance(minimal_request, bool):
            raise TypeError("minimal_request must be a bool")
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._thinking_disabled = thinking_disabled
        self._minimal_request = minimal_request
        self._redaction_secret = api_key
        self._http = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
            transport=transport or httpx.AsyncHTTPTransport(retries=0),
        )
        self.call_count = 0
        self.provider_request_count = 0
        self.last_raw_text: str | None = None
        self.last_metadata: DecisionResponseMetadata | None = None
        self.last_latency_seconds: float | None = None

    async def complete(self, system_prompt: str, user_prompt: str) -> DecisionReply:
        self.call_count += 1
        self.last_raw_text = None
        self.last_metadata = None
        request_body: dict[str, object] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if not self._minimal_request:
            request_body.update(
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                stream=False,
                n=1,
            )
            if self._thinking_disabled:
                # Provider-specific wire option; never enters domain context.
                request_body["thinking"] = {"type": "disabled"}
        started = time.perf_counter()
        try:
            self.provider_request_count += 1
            response = await self._http.post(self._url, json=request_body)
        finally:
            self.last_latency_seconds = time.perf_counter() - started
        if response.status_code != 200:
            try:
                error_payload = response.json()
                error_obj = error_payload.get("error") if isinstance(error_payload, Mapping) else None
                error_obj = error_obj if isinstance(error_obj, Mapping) else {}
            except ValueError:
                error_payload = {}
                error_obj = {}
            request_id = (
                error_obj.get("request_id")
                or (error_payload.get("request_id") if isinstance(error_payload, Mapping) else None)
                or response.headers.get("x-tt-logid")
                or response.headers.get("x-request-id")
            )
            self.last_metadata = DecisionResponseMetadata(
                http_status=response.status_code,
                http_error_code=_safe_error_atom(error_obj.get("code")),
                http_error_type=_safe_error_atom(error_obj.get("type")),
                http_error_param=_safe_error_atom(error_obj.get("param")),
                request_id=_safe_request_id(request_id),
                sanitized_error_message=_sanitized_error_message(
                    error_obj.get("message"), self._redaction_secret
                ),
            )
            raise DecisionClientError(f"Provider returned HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            self.last_metadata = DecisionResponseMetadata(http_status=response.status_code)
            raise ProviderContractError("PROVIDER_SCHEMA_MISMATCH", self.last_metadata) from exc
        try:
            raw_text, metadata = inspect_chat_completion(
                payload, http_status=response.status_code
            )
        except ProviderContractError as exc:
            self.last_metadata = exc.metadata
            raise
        self.last_metadata = metadata
        self.last_raw_text = raw_text
        return DecisionReply(
            raw_text,
            metadata.input_tokens,
            metadata.output_tokens,
            metadata.reasoning_tokens,
            metadata.provider_model,
            1,
        )

    async def aclose(self) -> None:
        await self._http.aclose()
