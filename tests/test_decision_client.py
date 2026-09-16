"""One application call and one transport request, with no retry loop."""

import asyncio
import json

import httpx
import pytest

from social_sim.decision import (
    CompactDecisionService,
    DecisionParseError,
    FakeDecisionClient,
    OpenAICompatibleDecisionClient,
)
from social_sim.world.observation import LocalObservation


def observation() -> LocalObservation:
    return LocalObservation(1, "2026-01-01T00:00:00+00:00", "home", 100.0, 0.8)


def test_one_fake_call_returns_proposal() -> None:
    client = FakeDecisionClient('{"action":"REST","target":null}')
    service = CompactDecisionService(client)

    result = asyncio.run(service.decide({"name": "Alice"}, observation()))

    assert result.proposal.action.value == "REST"
    assert client.call_count == service.decision_call_count == 1
    assert result.context_chars < 1000
    assert result.prompt_chars < 1500


def test_parse_failure_never_calls_model_again() -> None:
    client = FakeDecisionClient("not JSON")
    service = CompactDecisionService(client)

    with pytest.raises(DecisionParseError):
        asyncio.run(service.decide({"name": "Alice"}, observation()))
    assert client.call_count == service.decision_call_count == 1


def test_unavailable_move_target_rejected_after_one_call() -> None:
    client = FakeDecisionClient('{"action":"MOVE","target":"unlisted"}')
    service = CompactDecisionService(client)

    with pytest.raises(DecisionParseError, match="not currently available"):
        asyncio.run(
            service.decide(
                {"name": "Alice"}, observation(), available_targets=["park"]
            )
        )
    assert client.call_count == service.decision_call_count == 1


def test_scalar_targets_fail_before_model_call() -> None:
    client = FakeDecisionClient('{"action":"WAIT","target":null}')
    service = CompactDecisionService(client)

    with pytest.raises(TypeError, match="available_targets"):
        asyncio.run(
            service.decide(
                {"name": "Alice"}, observation(), available_targets="park"
            )
        )
    assert client.call_count == service.decision_call_count == 0


def test_provider_adapter_makes_one_http_request() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.path == "/api/coding/v3/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-only-key"
        payload = json.loads(request.content)
        assert payload["max_tokens"] == 64
        assert payload["temperature"] == 0.0
        assert payload["stream"] is False
        assert payload["n"] == 1
        assert len(payload["messages"]) == 2
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": '{"action":"WAIT","target":null}'}}
                ],
                "usage": {"prompt_tokens": 35, "completion_tokens": 12},
            },
        )

    client = OpenAICompatibleDecisionClient(
        base_url="https://example.invalid/api/coding/v3",
        api_key="test-only-key",
        model="test-model",
        transport=httpx.MockTransport(handler),
    )
    service = CompactDecisionService(client)

    async def run() -> None:
        try:
            result = await service.decide({"name": "Alice"}, observation())
            assert result.proposal.action.value == "WAIT"
            assert result.input_tokens == 35
            assert result.output_tokens == 12
        finally:
            await client.aclose()

    asyncio.run(run())
    assert len(requests) == client.call_count == service.decision_call_count == 1


def test_provider_transport_failure_is_not_retried() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectTimeout("test timeout")

    client = OpenAICompatibleDecisionClient(
        base_url="https://example.invalid/v3",
        api_key="test-only-key",
        model="test-model",
        transport=httpx.MockTransport(handler),
    )
    service = CompactDecisionService(client)

    async def run() -> None:
        try:
            with pytest.raises(httpx.ConnectTimeout):
                await service.decide({"name": "Alice"}, observation())
        finally:
            await client.aclose()

    asyncio.run(run())
    assert attempts == client.call_count == service.decision_call_count == 1
