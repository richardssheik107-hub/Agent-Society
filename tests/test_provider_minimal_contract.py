"""Offline checks for the minimal Chat Completions request and HTTP errors."""

import asyncio
import json

import httpx
import pytest

from social_sim.decision.client import (
    DecisionClientError,
    OpenAICompatibleDecisionClient,
)


API_KEY = "test-only-secret-key"
BASE_URL = "https://example.invalid/api/coding/v3"


def test_minimal_request_sends_only_model_and_messages() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"action":"WAIT","target":null}'}}]},
        )

    client = OpenAICompatibleDecisionClient(
        base_url=BASE_URL,
        api_key=API_KEY,
        model="test-model",
        max_tokens=128,
        temperature=0.2,
        thinking_disabled=True,
        minimal_request=True,
        transport=httpx.MockTransport(handler),
    )

    async def run() -> None:
        try:
            reply = await client.complete("system prompt", "user prompt")
            assert reply.raw_text == '{"action":"WAIT","target":null}'
        finally:
            await client.aclose()

    asyncio.run(run())

    assert client.call_count == len(requests) == 1
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/api/coding/v3/chat/completions"
    assert requests[0].headers["Authorization"] == f"Bearer {API_KEY}"
    assert json.loads(requests[0].content) == {
        "model": "test-model",
        "messages": [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "user prompt"},
        ],
    }


def test_http_400_exposes_only_bounded_redacted_error_metadata() -> None:
    requests: list[httpx.Request] = []
    provider_message = (
        f"Invalid request for Bearer {API_KEY}; key {API_KEY}; "
        "provider key sk-abcdefghijklmnopqrstuvwxyz012345; "
        + "details " * 40
    )

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            400,
            headers={"x-request-id": "req-header-123"},
            json={
                "error": {
                    "type": "invalid_request_error",
                    "code": "unsupported_parameter",
                    "param": "max_tokens",
                    "request_id": "req-body-456",
                    "message": provider_message,
                }
            },
        )

    client = OpenAICompatibleDecisionClient(
        base_url=BASE_URL,
        api_key=API_KEY,
        model="test-model",
        minimal_request=True,
        transport=httpx.MockTransport(handler),
    )

    async def run() -> None:
        try:
            with pytest.raises(DecisionClientError, match="HTTP 400") as raised:
                await client.complete("system", "user")
            assert provider_message not in str(raised.value)
            assert API_KEY not in str(raised.value)
        finally:
            await client.aclose()

    asyncio.run(run())

    assert client.call_count == len(requests) == 1
    assert requests[0].method == "POST"
    assert json.loads(requests[0].content).keys() == {"model", "messages"}
    assert client.last_raw_text is None
    metadata = client.last_metadata
    assert metadata is not None
    assert metadata.http_status == 400
    assert metadata.http_error_type == "invalid_request_error"
    assert metadata.http_error_code == "unsupported_parameter"
    assert metadata.http_error_param == "max_tokens"
    assert metadata.request_id == "req-body-456"
    assert metadata.sanitized_error_message is not None
    assert len(metadata.sanitized_error_message) <= 160
    assert API_KEY not in metadata.sanitized_error_message
    assert "sk-abcdefghijklmnopqrstuvwxyz012345" not in metadata.sanitized_error_message
    assert "Bearer test-only-secret-key" not in metadata.sanitized_error_message
    assert API_KEY not in json.dumps(metadata.safe_dict())
