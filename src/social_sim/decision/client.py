"""Replaceable single-request client for an OpenAI-compatible chat endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx


@dataclass(frozen=True)
class DecisionReply:
    raw_text: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class DecisionModelClient(Protocol):
    async def complete(self, system_prompt: str, user_prompt: str) -> DecisionReply:
        """Return one raw completion; callers never request a model repair."""
        ...


class DecisionClientError(RuntimeError):
    """A single provider request failed or returned an unusable wire response."""


class FakeDecisionClient:
    """A no-network response source for deterministic pipeline tests."""

    def __init__(self, raw_text: str) -> None:
        self.raw_text = raw_text
        self.call_count = 0

    async def complete(self, system_prompt: str, user_prompt: str) -> DecisionReply:
        self.call_count += 1
        return DecisionReply(self.raw_text)


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
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not base_url or not api_key or not model:
            raise ValueError("base_url, api_key, and model are required")
        if not 0 < timeout_seconds <= 60:
            raise ValueError("timeout_seconds must be within (0, 60]")
        if not 0 < max_tokens <= 96:
            raise ValueError("max_tokens must be within (0, 96]")
        if not 0 <= temperature <= 0.2:
            raise ValueError("temperature must be within [0, 0.2]")
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._http = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
            transport=transport or httpx.AsyncHTTPTransport(retries=0),
        )
        self.call_count = 0
        self.last_raw_text: str | None = None

    async def complete(self, system_prompt: str, user_prompt: str) -> DecisionReply:
        self.call_count += 1
        response = await self._http.post(
            self._url,
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": self._max_tokens,
                "temperature": self._temperature,
                "stream": False,
                "n": 1,
            },
        )
        if response.status_code >= 400:
            raise DecisionClientError(f"Provider returned HTTP {response.status_code}")
        try:
            payload = response.json()
            raw_text = payload["choices"][0]["message"]["content"]
            if not isinstance(raw_text, str):
                raise TypeError("message.content is not a string")
            usage = payload.get("usage") or {}
            input_tokens = usage.get("prompt_tokens")
            output_tokens = usage.get("completion_tokens")
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise DecisionClientError("Provider response lacks a text completion") from exc
        self.last_raw_text = raw_text
        return DecisionReply(raw_text, input_tokens, output_tokens)

    async def aclose(self) -> None:
        await self._http.aclose()
