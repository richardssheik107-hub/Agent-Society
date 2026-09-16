"""Offline Chat Completions envelope checks for Phase 6.5A."""

import asyncio
import json

import httpx
import pytest

from social_sim.decision.client import (
    DecisionClientError,
    OpenAICompatibleDecisionClient,
    ProviderContractError,
)


FINAL = '{"action":"WAIT","target":null}'
REASONING_SECRET = "private reasoning sentinel: never log this"
REFUSAL_SECRET = "private refusal sentinel: never log this"


def envelope(
    message: dict[str, object], *, finish_reason: str = "stop"
) -> dict[str, object]:
    return {
        "id": "completion-123",
        "model": "test-model",
        "choices": [{"finish_reason": finish_reason, "message": message}],
        "usage": {
            "prompt_tokens": 31,
            "completion_tokens": 18,
            "total_tokens": 49,
            "completion_tokens_details": {"reasoning_tokens": 7},
        },
    }


def complete_once(payload: object, *, thinking_disabled: bool = False):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=payload)

    client = OpenAICompatibleDecisionClient(
        base_url="https://example.invalid/api/coding/v3",
        api_key="test-only-key",
        model="test-model",
        timeout_seconds=60,
        max_tokens=128,
        temperature=0,
        thinking_disabled=thinking_disabled,
        transport=httpx.MockTransport(handler),
    )

    async def run():
        try:
            return await client.complete("system", "user")
        finally:
            await client.aclose()

    return client, requests, run


def assert_one_request(client, requests) -> None:
    assert client.call_count == len(requests) == 1
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/api/coding/v3/chat/completions"


def test_valid_final_json_and_safe_metadata() -> None:
    client, requests, run = complete_once(envelope({"content": FINAL}))

    reply = asyncio.run(run())

    assert_one_request(client, requests)
    assert reply.raw_text == client.last_raw_text == FINAL
    assert (reply.input_tokens, reply.output_tokens) == (31, 18)
    metadata = client.last_metadata
    assert metadata is not None
    assert metadata.http_status == 200
    assert metadata.response_id_present is True
    assert metadata.provider_model == "test-model"
    assert metadata.choices_count == 1
    assert metadata.finish_reason == "stop"
    assert metadata.content_is_none is False
    assert metadata.content_type == "str"
    assert metadata.content_chars == len(FINAL)
    assert metadata.reasoning_field_exists is False
    assert metadata.reasoning_chars == 0
    assert metadata.refusal_field_exists is False
    assert metadata.tool_calls_count == 0
    assert metadata.total_tokens == 49
    assert metadata.reasoning_tokens == 7
    assert "raw_text" not in metadata.safe_dict()


@pytest.mark.parametrize(
    ("payload", "category", "expected"),
    [
        (
            envelope({"content": "", "reasoning_content": REASONING_SECRET}),
            "EMPTY_FINAL_CONTENT_WITH_REASONING",
            {"reasoning_field_exists": True, "reasoning_chars": len(REASONING_SECRET)},
        ),
        (
            envelope({"content": "", "reasoning_content": REASONING_SECRET}, finish_reason="length"),
            "OUTPUT_BUDGET_EXHAUSTED",
            {"finish_reason": "length", "reasoning_chars": len(REASONING_SECRET)},
        ),
        (
            {"id": "completion-123", "model": "test-model", "choices": []},
            "NO_CHOICES",
            {"choices_count": 0},
        ),
        (
            envelope({"content": None, "refusal": REFUSAL_SECRET}),
            "PROVIDER_REFUSAL",
            {"refusal_field_exists": True, "refusal_chars": len(REFUSAL_SECRET)},
        ),
        (
            envelope({"content": None, "tool_calls": [{"id": "call-1"}]}),
            "TOOL_CALL_INSTEAD_OF_TEXT",
            {"tool_calls_count": 1},
        ),
        (
            envelope({"content": [{"type": "text", "text": FINAL}]}),
            "PROVIDER_SCHEMA_MISMATCH",
            {"content_type": "list"},
        ),
    ],
    ids=["empty-reasoning", "length", "no-choices", "refusal", "tool-calls", "content-schema"],
)
def test_unusable_envelopes_fail_once_without_leaking_text(
    payload: object, category: str, expected: dict[str, object]
) -> None:
    client, requests, run = complete_once(payload)

    with pytest.raises(ProviderContractError) as raised:
        asyncio.run(run())

    assert_one_request(client, requests)
    assert raised.value.category == category
    assert client.last_raw_text is None
    assert client.last_metadata == raised.value.metadata
    for field, value in expected.items():
        assert getattr(raised.value.metadata, field) == value
    safe_output = json.dumps(raised.value.metadata.safe_dict()) + str(raised.value)
    assert REASONING_SECRET not in safe_output
    assert REFUSAL_SECRET not in safe_output
    assert FINAL not in safe_output


def test_thinking_disabled_is_wire_only_and_output_budget_is_128() -> None:
    client, requests, run = complete_once(
        envelope({"content": FINAL}), thinking_disabled=True
    )

    asyncio.run(run())

    assert_one_request(client, requests)
    body = json.loads(requests[0].content)
    assert body["thinking"] == {"type": "disabled"}
    assert body["max_tokens"] == 128
    assert body["n"] == 1
    assert body["stream"] is False
    assert body["temperature"] == 0


def test_http_error_keeps_only_safe_identifiers_not_message() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(400, json={"error": {
            "code": "unsupported_parameter",
            "type": "invalid_request_error",
            "param": "thinking.type",
            "message": REASONING_SECRET,
        }})

    client = OpenAICompatibleDecisionClient(
        base_url="https://example.invalid/api/coding/v3",
        api_key="test-only-key",
        model="test-model",
        transport=httpx.MockTransport(handler),
    )

    async def run() -> None:
        try:
            with pytest.raises(DecisionClientError, match="HTTP 400"):
                await client.complete("system", "user")
        finally:
            await client.aclose()

    asyncio.run(run())
    assert_one_request(client, requests)
    metadata = client.last_metadata
    assert metadata is not None
    assert metadata.http_error_code == "unsupported_parameter"
    assert metadata.http_error_type == "invalid_request_error"
    assert metadata.http_error_param == "thinking.type"
    assert metadata.choices_count is None
    assert metadata.reasoning_field_exists is None
    assert REASONING_SECRET not in json.dumps(metadata.safe_dict())
