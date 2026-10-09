"""Actual compatible-client POSTs through local MockTransport, never a provider."""
from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from social_sim.decision.client import DecisionClientError, ProviderContractError
from social_sim.longrun.config import LongRunConfig
from social_sim.longrun.provider import M5ProviderClient, validate_real_authorization

SECRET = "local-test-placeholder-never-a-real-key"
PROVIDER = {"base_url": "https://offline.invalid/v1", "api_key": SECRET,
            "model": "ark-code-latest"}


def payload(content='{"activity":"ACQUIRE","target":"game-1"}', *, usage=None,
            finish="stop", reasoning="private hidden chain"):
    result = {"id": "local-response", "model": "actual-backend-v1", "choices": [{
        "finish_reason": finish,
        "message": {"content": content, "reasoning_content": reasoning},
    }]}
    if usage is not None:
        result["usage"] = usage
    return result


def run_once(handler, *, config=None):
    client = M5ProviderClient(PROVIDER, config or LongRunConfig(),
                              transport=httpx.MockTransport(handler))
    async def exercise():
        try:
            return await client.complete("strict M2 JSON", "current bounded facts")
        finally:
            await client.aclose()
    return client, exercise


def test_actual_post_minimal_contract_safe_proposal_and_cleanup():
    posts = []
    def handle(request):
        posts.append(request)
        assert request.method == "POST"
        assert str(request.url) == "https://offline.invalid/v1/chat/completions"
        body = json.loads(request.content)
        assert set(body) == {"model", "messages"}
        assert body["model"] == "ark-code-latest"
        return httpx.Response(200, json=payload(usage={"prompt_tokens": 0,
            "completion_tokens": 14, "completion_tokens_details": {"reasoning_tokens": 8}}))
    client, exercise = run_once(handle)
    reply = asyncio.run(exercise())
    assert json.loads(reply.raw_text) == {"activity": "ACQUIRE", "target": "game-1"}
    assert len(posts) == client.call_count == client.provider_request_count == 1
    evidence = client.safe_evidence
    assert evidence["request_alias"] == "ark-code-latest"
    assert evidence["response_backend"] == "actual-backend-v1"
    assert evidence["http_status"] == 200 and evidence["http_observable"] is True
    assert evidence["input_tokens"] == 0 and evidence["reasoning_tokens"] == 8
    assert evidence["latency_seconds"] >= 0
    assert client._client._http.is_closed
    assert client._client.last_raw_text is None
    serialized = json.dumps(evidence)
    assert SECRET not in serialized and "private hidden chain" not in serialized
    assert "reasoning_content" not in serialized and "raw_text" not in serialized


def test_missing_usage_is_null_and_not_zero():
    client, exercise = run_once(lambda request: httpx.Response(200, json=payload()))
    reply = asyncio.run(exercise())
    assert reply.input_tokens is reply.output_tokens is reply.reasoning_tokens is None
    assert all(client.safe_evidence[name] is None for name in
               ("input_tokens", "output_tokens", "reasoning_tokens"))
    assert client.provider_request_count == 1 and client._client._http.is_closed


@pytest.mark.parametrize(("response", "error_type", "category", "status"), [
    (payload(finish="length"), ProviderContractError, "OUTPUT_BUDGET_EXHAUSTED", 200),
    (payload(content="", reasoning="secret hidden reasoning"), ProviderContractError,
     "EMPTY_FINAL_CONTENT_WITH_REASONING", 200),
    (payload(content=None, reasoning=""), ProviderContractError, "EMPTY_FINAL_CONTENT", 200),
    (payload(content="{illegal-json"), ValueError, "INVALID_MODEL_OUTPUT", 200),
    (payload(content='{"activity":"SLEEP","target":null,"private":"secret"}'),
     ValueError, "INVALID_MODEL_OUTPUT", 200),
    ({"error": {"code": "bad_request", "message": SECRET + " private reasoning"}},
     DecisionClientError, "PROVIDER_ERROR", 400),
])
def test_unusable_response_never_retries_repairs_or_falls_back(response, error_type,
                                                               category, status):
    requests = []
    def handle(request):
        requests.append(request)
        return httpx.Response(status, json=response)
    client, exercise = run_once(handle)
    with pytest.raises(error_type):
        asyncio.run(exercise())
    assert len(requests) == client.call_count == client.provider_request_count == 1
    assert client.safe_evidence["failure_category"] == category
    assert client.safe_evidence["http_status"] == status
    assert client.safe_evidence["valid_proposal"] is None
    assert client._client._http.is_closed and client._client.last_raw_text is None
    serialized = json.dumps(client.safe_evidence)
    assert SECRET not in serialized and "secret hidden reasoning" not in serialized
    assert "illegal-json" not in serialized


def test_timeout_is_one_unknown_receipt_attempt_and_closes():
    requests = []
    def handle(request):
        requests.append(request)
        raise httpx.ReadTimeout("local timeout with " + SECRET, request=request)
    client, exercise = run_once(handle)
    with pytest.raises(httpx.ReadTimeout):
        asyncio.run(exercise())
    assert len(requests) == client.provider_request_count == 1
    assert client.safe_evidence["failure_category"] == "PROVIDER_TIMEOUT"
    assert client.safe_evidence["exception_type"] == "ReadTimeout"
    assert client.safe_evidence["http_status"] is None
    assert client.safe_evidence["http_observable"] is False
    assert client._client._http.is_closed and SECRET not in json.dumps(client.safe_evidence)


def test_request_timeout_is_enforced_during_mock_post():
    async def handle(request):
        await asyncio.sleep(1)
        return httpx.Response(200, json=payload())
    client, exercise = run_once(handle, config=replace(LongRunConfig(), request_timeout_seconds=0.01))
    with pytest.raises(TimeoutError):
        asyncio.run(exercise())
    assert client.provider_request_count == 1 and client._client._http.is_closed
    assert client.safe_evidence["failure_category"] == "PROVIDER_TIMEOUT"


def test_non_minimal_request_honors_frozen_parameters():
    def handle(request):
        body = json.loads(request.content)
        assert body["max_tokens"] == 96 and body["temperature"] == 0.1
        assert body["thinking"] == {"type": "disabled"}
        assert body["stream"] is False and body["n"] == 1
        return httpx.Response(200, json=payload())
    client, exercise = run_once(handle, config=replace(LongRunConfig(),
        provider_minimal_request=False, provider_max_tokens=96, provider_temperature=0.1,
        provider_thinking_disabled=True))
    asyncio.run(exercise())
    assert client.provider_request_count == 1


def authorization(config, commit="a" * 40, session="approved_session"):
    return {"authorization_type": "EXPLICIT_USER_SESSION_AUTHORIZATION", "approved": True,
            "session_id": session, "execution_commit": commit,
            "protocol_hash": config.protocol_hash, "max_provider_requests": 2,
            "acceptance": {"execution_commit": commit, "result": "PASS"},
            "request_policy": {"retry": False, "fallback": False}, "resume": False}


def gate(tmp_path, config, auth_path=None, **overrides):
    values = dict(root=tmp_path, registry=tmp_path / "registry", config=config,
                  session_id="approved_session", allow_provider=True,
                  execution_commit="a" * 40, protocol_hash=config.protocol_hash,
                  frozen_protocol_hash=config.protocol_hash, authorization_path=auth_path)
    values.update(overrides)
    return validate_real_authorization(**values)


def test_future_positive_authorization_requires_no_core_change(tmp_path, monkeypatch):
    config = replace(LongRunConfig(), mode="real", max_provider_requests=2)
    path = tmp_path / "authorization.json"
    data = authorization(config)
    data["untrusted_extra"] = "never persist this"
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr("social_sim.provider_runtime.environment.repository_info", lambda root: {
        "git_commit": "a" * 40, "parent_repository": True, "worktree_clean": True,
        "upstream_matches": True})
    monkeypatch.setattr("social_sim.provider_runtime.environment.inspect_runtime",
                        lambda: {"result": "PASS"})
    approved = gate(tmp_path, config, path)
    assert approved["max_provider_requests"] == 2
    assert "untrusted_extra" not in approved


@pytest.mark.parametrize(("field", "value", "message"), [
    ("approved", False, "EXECUTION_AUTHORIZATION_MISMATCH"),
    ("approved", 1, "EXECUTION_AUTHORIZATION_MISMATCH"),
    ("session_id", "different", "EXECUTION_AUTHORIZATION_MISMATCH"),
    ("execution_commit", "b" * 40, "EXECUTION_AUTHORIZATION_MISMATCH"),
    ("protocol_hash", "b" * 64, "EXECUTION_AUTHORIZATION_MISMATCH"),
    ("max_provider_requests", 0, "EXECUTION_AUTHORIZATION_BUDGET_MISMATCH"),
    ("max_provider_requests", True, "EXECUTION_AUTHORIZATION_BUDGET_MISMATCH"),
    ("acceptance", {"result": "PASS", "execution_commit": "b" * 40},
     "EXECUTION_COMMIT_NOT_ACCEPTED"),
    ("request_policy", {"retry": True, "fallback": False}, "UNAPPROVED_REQUEST_POLICY"),
])
def test_authorization_cannot_expand_or_reinterpret_approval(tmp_path, field, value, message):
    config = replace(LongRunConfig(), mode="real", max_provider_requests=2)
    data = authorization(config)
    data[field] = value
    path = tmp_path / "authorization.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        gate(tmp_path, config, path)


def test_zero_budget_stops_before_authorization_file_runtime_or_credentials(tmp_path, monkeypatch):
    config = replace(LongRunConfig(), mode="real")
    def forbidden(*args, **kwargs):
        raise AssertionError("must not reach runtime or credentials")
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr("social_sim.provider_runtime.environment.inspect_runtime", forbidden)
    monkeypatch.setattr("social_sim.provider_runtime.environment.load_provider_config", forbidden)
    with pytest.raises(ValueError, match="ZERO_PROVIDER_BUDGET_NOT_AUTHORIZED"):
        gate(tmp_path, config, tmp_path / "unread.json")


@pytest.mark.parametrize("failure", ["worktree_clean", "parent_repository", "upstream_matches",
                                      "git_commit", "runtime"])
def test_approved_file_still_requires_accepted_clean_execution_environment(tmp_path, monkeypatch,
                                                                        failure):
    config = replace(LongRunConfig(), mode="real", max_provider_requests=2)
    path = tmp_path / "authorization.json"
    path.write_text(json.dumps(authorization(config)), encoding="utf-8")
    repository = {"git_commit": "a" * 40, "parent_repository": True,
                  "worktree_clean": True, "upstream_matches": True}
    if failure != "runtime":
        repository[failure] = "b" * 40 if failure == "git_commit" else False
    monkeypatch.setattr("social_sim.provider_runtime.environment.repository_info",
                        lambda root: repository)
    monkeypatch.setattr("social_sim.provider_runtime.environment.inspect_runtime",
                        lambda: {"result": "FAIL" if failure == "runtime" else "PASS"})
    with pytest.raises(ValueError, match=("REAL_RUNTIME_GATE_FAILED" if failure == "runtime"
                                         else "REAL_REPOSITORY_GATE_FAILED")):
        gate(tmp_path, config, path)


def test_same_session_or_duplicate_authorization_keys_are_refused(tmp_path):
    config = replace(LongRunConfig(), mode="real", max_provider_requests=2)
    path = tmp_path / "authorization.json"
    text = json.dumps(authorization(config))
    path.write_text(text[:-1] + ',"approved":true}', encoding="utf-8")
    with pytest.raises(ValueError, match="EXECUTION_AUTHORIZATION_FILE_INVALID"):
        gate(tmp_path, config, path)
    (tmp_path / "registry" / "approved_session").mkdir(parents=True)
    with pytest.raises(ValueError, match="SESSION_ALREADY_EXISTS"):
        gate(tmp_path, config, path)
