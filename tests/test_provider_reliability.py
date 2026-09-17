"""Offline contract tests for the world-free reliability benchmark."""

from __future__ import annotations

import asyncio
import json

import httpx

from social_sim.decision.client import DecisionReply, FakeDecisionClient, OpenAICompatibleDecisionClient
from social_sim.decision.config import DecisionProviderConfig
from social_sim.evaluation.provider_reliability import (
    RELIABILITY_PROMPT_HASH,
    decision_client_config_hash,
    run_provider_reliability,
    write_provider_reliability_report,
)


GOOD = '{"action":"MOVE","target":"home"}'


def _envelope(content: str | None = GOOD, *, model: str = "backend-one", usage=True) -> dict:
    result = {
        "model": model,
        "choices": [{"finish_reason": "stop", "message": {"content": content}}],
    }
    if usage:
        result["usage"] = {
            "prompt_tokens": 12,
            "completion_tokens": 8,
            "completion_tokens_details": {"reasoning_tokens": 3},
        }
    return result


def _run_responses(responses: list[httpx.Response | Exception]):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        payload = json.loads(request.content)
        assert set(payload) == {"model", "messages"}
        assert payload["messages"][0]["content"] == "Return JSON only."
        assert payload["messages"][1]["content"].endswith(GOOD)
        item = responses[len(seen) - 1]
        if isinstance(item, Exception):
            raise item
        return item

    client = OpenAICompatibleDecisionClient(
        base_url="https://example.invalid/api/coding/v3",
        api_key="test-only-secret",
        model="alias",
        timeout_seconds=60,
        minimal_request=True,
        transport=httpx.MockTransport(handler),
    )

    async def run():
        try:
            return await run_provider_reliability(client, requests=len(responses))
        finally:
            await client.aclose()

    return asyncio.run(run()), seen


def test_all_success_30_sequential_no_retry_and_gate_pass(tmp_path) -> None:
    client = FakeDecisionClient(GOOD)
    result = asyncio.run(run_provider_reliability(client))
    assert client.call_count == 30
    assert [row.request_index for row in result.requests] == list(range(1, 31))
    assert result.reliability_ok is True
    summary = result.summary()
    assert summary["requests_total"] == summary["requests_success"] == 30
    assert summary["success_rate"] == 1
    assert summary["timeout_rate"] == 0
    assert summary["input_tokens"] is None
    assert summary["reasoning_tokens"] is None
    assert summary["prompt_hash"] == RELIABILITY_PROMPT_HASH
    paths = write_provider_reliability_report(result, tmp_path)
    assert all(path.exists() for path in paths)
    serialized = paths[0].read_text() + paths[1].read_text()
    assert GOOD not in serialized
    assert "reasoning_content" not in serialized


def test_timeout_classification_and_attempted_latency_unknown_usage() -> None:
    result, seen = _run_responses([httpx.ConnectTimeout("private, never persisted")])
    assert len(seen) == 1
    row = result.requests[0]
    assert row.failure_type == "TIMEOUT"
    assert row.latency_seconds >= 0
    assert row.input_tokens is row.output_tokens is row.reasoning_tokens is None
    assert "private" not in json.dumps(row.to_dict())
    assert result.summary()["timeout_count"] == 1
    assert result.summary()["timeout_rate"] == 1


def test_http_error_status_and_no_response_body_persisted() -> None:
    response = httpx.Response(429, json={"error": {"message": "secret-body"}})
    result, _ = _run_responses([response])
    row = result.requests[0]
    assert row.failure_type == "HTTP_ERROR"
    assert row.http_status == 429
    assert "secret-body" not in json.dumps(row.to_dict())


def test_empty_content_and_invalid_provider_envelope_are_separate() -> None:
    result, _ = _run_responses([
        httpx.Response(200, json=_envelope("")),
        httpx.Response(200, json={"not_choices": []}),
    ])
    assert [row.failure_type for row in result.requests] == [
        "EMPTY_CONTENT", "INVALID_PROVIDER_ENVELOPE"
    ]
    assert result.summary()["empty_content_count"] == 1
    assert result.summary()["invalid_provider_envelope_count"] == 1


def test_invalid_json_and_invalid_action_are_separate() -> None:
    result, _ = _run_responses([
        httpx.Response(200, json=_envelope("not json")),
        httpx.Response(200, json=_envelope('{"action":"WAIT","target":null}')),
        httpx.Response(200, json=_envelope('{"action":"MOVE","target":"office"}')),
    ])
    assert [row.failure_type for row in result.requests] == [
        "INVALID_JSON", "INVALID_ACTION", "INVALID_ACTION"
    ]
    assert result.summary()["invalid_json_count"] == 1
    assert result.summary()["invalid_action_count"] == 2


def test_unknown_usage_is_null_and_model_backend_instability_detected() -> None:
    result, _ = _run_responses([
        httpx.Response(200, json=_envelope(model="backend-one", usage=False)),
        httpx.Response(200, json=_envelope(model="backend-two")),
    ])
    assert result.requests[0].input_tokens is None
    assert result.requests[0].output_tokens is None
    assert result.requests[0].reasoning_tokens is None
    summary = result.summary()
    assert summary["input_tokens"] == 12
    assert summary["input_tokens_observed_requests"] == 1
    assert summary["provider_model_counts"] == {"backend-one": 1, "backend-two": 1}
    assert summary["model_backend_stable"] == "NO"


def test_provider_controlled_model_and_finish_reason_cannot_leak_secret() -> None:
    payload = _envelope(model="ark-12345678901234567890")
    payload["choices"][0]["finish_reason"] = "Bearer test-only-secret"
    result, _ = _run_responses([httpx.Response(200, json=payload)])
    row = result.requests[0]
    assert row.success
    assert row.provider_model is None
    assert row.finish_reason is None
    assert "test-only-secret" not in json.dumps(row.to_dict())
    assert result.summary()["model_backend_stable"] == "UNKNOWN"


def test_one_timeout_does_not_automatically_fail_30_request_gate() -> None:
    class OneTimeout:
        def __init__(self) -> None:
            self.calls = 0

        async def complete(self, system_prompt, user_prompt):
            self.calls += 1
            if self.calls == 3:
                raise httpx.ReadTimeout("test")
            return DecisionReply(GOOD)

    client = OneTimeout()
    result = asyncio.run(run_provider_reliability(client))
    assert client.calls == 30
    assert result.summary()["requests_success"] == 29
    assert result.summary()["timeout_count"] == 1
    assert result.reliability_ok is True


def test_per_request_callback_sees_only_safe_results_and_order() -> None:
    captured = []

    async def callback(row):
        captured.append(row.to_dict())

    result = asyncio.run(run_provider_reliability(FakeDecisionClient(GOOD), requests=3, on_result=callback))
    assert [row["request_index"] for row in captured] == [1, 2, 3]
    assert len(result.requests) == 3
    assert "raw_text" not in json.dumps(captured)


def test_config_hash_uses_category_alias_timeout_retry_not_secret() -> None:
    first = DecisionProviderConfig(
        api_base="https://ark.cn-beijing.volces.com/api/coding/v3",
        model="ark-code-latest",
        api_key="first-super-secret",
    )
    second = DecisionProviderConfig(
        api_base="https://ark.cn-beijing.volces.com/api/coding/v3/",
        model="ark-code-latest",
        api_key="second-super-secret",
    )
    hash_a = decision_client_config_hash(first, timeout_seconds=60, max_retries=0)
    hash_b = decision_client_config_hash(second, timeout_seconds=60, max_retries=0)
    assert hash_a == hash_b
    assert "secret" not in hash_a
    assert hash_a != decision_client_config_hash(first, timeout_seconds=30, max_retries=0)
    assert hash_a != decision_client_config_hash(first, timeout_seconds=60, max_retries=1)
