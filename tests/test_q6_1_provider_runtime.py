"""实际客户端 + MockTransport，零外网；覆盖调用、响应、关闭与串行门禁。"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from social_sim.decision import OpenAICompatibleDecisionClient
from social_sim.provider_runtime.environment import EXPECTED_BASE, EXPECTED_MODEL, load_provider_config
from social_sim.provider_runtime.safety import atom, exception_type, failure_stage
from social_sim.provider_runtime.workflow import (
    continuity_result, execute_session, run_preflight,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = {"base_url": EXPECTED_BASE, "model": EXPECTED_MODEL, "api_key": "private-test-credential"}
ENVIRONMENT = {"repository": {"git_commit": "test-commit"}}
GOOD = '{"activity":"SLEEP","target":null}'
WATCH = '{"activity":"WATCH","target":"series_a"}'


def wire(content=GOOD, *, finish="stop", model="test-backend", **message_extra):
    return {"id": "local-test", "model": model, "choices": [{"finish_reason": finish,
            "message": {"role": "assistant", "content": content, **message_extra}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 30,
                      "completion_tokens_details": {"reasoning_tokens": 15}}}


def factory_for(handler, *, bad_close=False):
    def factory(config):
        class Transport(httpx.MockTransport):
            async def aclose(self):
                if bad_close:
                    raise ImportError("secret cleanup detail " + CONFIG["api_key"])
        return OpenAICompatibleDecisionClient(**config, minimal_request=True,
                                               transport=Transport(handler))
    return factory


def no_secrets(directory):
    for path in directory.rglob("*"):
        if path.is_file() and path.suffix in {".json", ".jsonl", ".md"}:
            content = path.read_text(encoding="utf-8")
            assert CONFIG["api_key"] not in content
            assert "PRIVATE_REASONING_CANARY" not in content
            assert "secret cleanup detail" not in content
            assert "Authorization" not in content


def test_preflight_uses_actual_client_exactly_one_request(tmp_path):
    requests = []
    def handler(request):
        requests.append(request)
        body = json.loads(request.content)
        assert set(body) == {"model", "messages"}
        assert body["model"] == EXPECTED_MODEL
        assert request.url.path == "/api/coding/v3/chat/completions"
        return httpx.Response(200, json=wire(reasoning_content="PRIVATE_REASONING_CANARY"))
    result = asyncio.run(run_preflight(tmp_path / "pre", CONFIG, factory=factory_for(handler),
                                       mode="OFFLINE_TRANSPORT_CONTRACT"))
    assert len(requests) == result["provider_requests"] == 1
    assert result["result"] == "PASS"
    assert result["http_status"] == 200
    assert result["reasoning_tokens"] == 15
    assert result["real_provider_attempted"] is False
    no_secrets(tmp_path)


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503, 302])
def test_http_error_no_retry_or_redirect(tmp_path, status):
    calls = []
    def handler(request):
        calls.append(1)
        return httpx.Response(status, headers={"Location": "https://other.invalid"},
                              json={"error": {"code": "TEST_ERROR", "message": CONFIG["api_key"]}})
    result = asyncio.run(run_preflight(tmp_path / "pre", CONFIG, factory=factory_for(handler)))
    assert result["result"] == "FAIL"
    assert result["failure_stage"] == "HTTP_ERROR"
    assert result["http_status"] == status
    assert len(calls) == 1
    no_secrets(tmp_path)


@pytest.mark.parametrize("kind,stage", [(ImportError, "PYTHON_ENVIRONMENT"),
    (httpx.ConnectError, "NETWORK_RUNTIME"), (httpx.ReadTimeout, "NETWORK_RUNTIME"),
    (RuntimeError, "UNKNOWN_TRANSPORT")])
def test_transport_type_without_exception_body(tmp_path, kind, stage):
    def handler(request):
        raise kind(CONFIG["api_key"])
    result = asyncio.run(run_preflight(tmp_path / "pre", CONFIG, factory=factory_for(handler)))
    assert result["failure_stage"] == stage
    assert result["exception_type"] == kind.__name__
    assert result["server_receipt"] == "UNKNOWN"
    assert result["provider_requests"] == 1
    no_secrets(tmp_path)


def test_construction_failure_does_not_count_as_request(tmp_path):
    def broken(config):
        raise ImportError(CONFIG["api_key"])
    result = asyncio.run(run_preflight(tmp_path / "pre", CONFIG, factory=broken))
    assert result["provider_requests"] == result["application_calls"] == 0
    assert result["failure_stage"] == "PYTHON_ENVIRONMENT"
    assert result["real_provider_attempted"] is False
    no_secrets(tmp_path)


def test_wall_timeout_is_not_an_extra_request(tmp_path):
    async def handler(request):
        await asyncio.sleep(10)
        return httpx.Response(200, json=wire())
    result = asyncio.run(run_preflight(tmp_path / "pre", CONFIG,
                                       factory=factory_for(handler), timeout=0.01))
    assert result["exception_type"] == "TimeoutError"
    assert result["provider_requests"] == 1


@pytest.mark.parametrize("content", ["not JSON", '```json\n'+GOOD+'\n```',
    '{"activity":"SLEEP","target":null,"extra":1}',
    '{"activity":"SLEEP","activity":"WORK","target":null}', WATCH])
def test_malformed_or_wrong_preflight_proposal_fails(tmp_path, content):
    result = asyncio.run(run_preflight(tmp_path / "pre", CONFIG,
        factory=factory_for(lambda req: httpx.Response(200, json=wire(content)))))
    assert result["failure_stage"] == "MODEL_OUTPUT"
    assert result["result"] == "FAIL"
    assert result["provider_requests"] == 1


@pytest.mark.parametrize("payload", [{"choices": []}, wire(None, refusal="no"),
    wire(GOOD, finish="length"), wire(None, tool_calls=[{}])])
def test_wire_contract_failure_is_separate(tmp_path, payload):
    result = asyncio.run(run_preflight(tmp_path / "pre", CONFIG,
        factory=factory_for(lambda req: httpx.Response(200, json=payload))))
    assert result["failure_stage"] == "PROVIDER_CONTRACT"
    assert result["result"] == "FAIL"


def test_cleanup_failure_blocks_pilot_and_preserves_successful_response(tmp_path):
    count = []
    def handler(request):
        count.append(1)
        return httpx.Response(200, json=wire())
    session = tmp_path / "session"
    session.mkdir()
    result = asyncio.run(execute_session(session, CONFIG, ENVIRONMENT, with_pilot=True,
        factory=factory_for(handler, bad_close=True), mode="OFFLINE"))
    pre = json.loads((session / "preflight/summary.json").read_text())
    assert pre["request_result"] == "PASS"
    assert pre["cleanup_exception_type"] == "ImportError"
    assert result["preflight"] == "FAIL"
    assert not result["attempt_3_executed"]
    assert len(count) == 1
    assert not (session / "attempt_3").exists()
    no_secrets(tmp_path)


def test_first_failure_not_overwritten_by_cleanup_failure(tmp_path):
    def handler(request):
        raise httpx.ConnectError(CONFIG["api_key"])
    pre = asyncio.run(run_preflight(tmp_path / "pre", CONFIG,
        factory=factory_for(handler, bad_close=True)))
    assert pre["exception_type"] == "ConnectError"
    assert pre["failure_stage"] == "NETWORK_RUNTIME"
    assert pre["cleanup_exception_type"] == "ImportError"
    no_secrets(tmp_path)


def test_successful_preflight_plus_four_decisions_same_client_contract(tmp_path):
    messages = []
    def handler(request):
        body = json.loads(request.content)
        messages.append(body["messages"])
        return httpx.Response(200, json=wire(GOOD if len(messages) == 1 else WATCH))
    session = tmp_path / "session"
    session.mkdir()
    result = asyncio.run(execute_session(session, CONFIG, ENVIRONMENT, with_pilot=True,
        factory=factory_for(handler), mode="OFFLINE"))
    assert result["preflight"] == "PASS"
    assert len(messages) == result["total_provider_request_attempts"] == 5
    assert result["short_horizon_state_continuity"] == "SUPPORTED"
    assert '"next_episode":2' in messages[2][1]["content"]
    pilot = json.loads((session / "attempt_3/summary.json").read_text())
    assert pilot["completed_decisions"] == 4
    assert pilot["real_provider_executed"] is False
    assert pilot["observed_backend_models"] == ["test-backend"]
    assert (session / "attempt_3/request_progress.jsonl").exists()
    no_secrets(tmp_path)


def test_formal_pilot_failure_stops_after_one_call_and_saves_type(tmp_path):
    count = []
    def handler(request):
        count.append(1)
        if len(count) == 1:
            return httpx.Response(200, json=wire())
        raise httpx.ConnectError(CONFIG["api_key"])
    session = tmp_path / "session"
    session.mkdir()
    result = asyncio.run(execute_session(session, CONFIG, ENVIRONMENT, with_pilot=True,
        factory=factory_for(handler), mode="OFFLINE"))
    assert len(count) == 2
    assert result["short_horizon_state_continuity"] == "INSUFFICIENT_EVIDENCE"
    rows = [json.loads(line) for line in (session / "attempt_3/decisions.jsonl").read_text().splitlines()]
    assert len(rows) == 1
    assert rows[0]["exception_type"] == "ConnectError"
    assert rows[0]["decision_status"] == "PROVIDER_ERROR"
    no_secrets(tmp_path)


def test_no_network_cli_does_not_need_provider_environment():
    env = {k: v for k, v in os.environ.items() if not k.startswith("CONTINUITY_")}
    result = subprocess.run([sys.executable, str(ROOT / "scripts/check_q6_1_provider_runtime.py")],
                            env=env, text=True, capture_output=True, timeout=10, check=False)
    assert result.returncode == 0
    assert "NOT_AUTHORIZED" in result.stdout
    assert "PROVIDER_REQUESTS=0" in result.stdout


def test_explicit_file_mapping_without_execution_or_interpolation(tmp_path, monkeypatch):
    for name in ("CONTINUITY_BASE_URL", "CONTINUITY_MODEL", "CONTINUITY_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    file = tmp_path / ".env"
    file.write_text('AGENTSOCIETY_LLM_API_KEY="${UNCHANGED_LITERAL}"\n', encoding="utf-8")
    before = file.read_bytes()
    result = load_provider_config(file)
    assert result["api_key"] == "${UNCHANGED_LITERAL}"
    assert result["model"] == EXPECTED_MODEL
    assert file.read_bytes() == before
    assert "CONTINUITY_API_KEY" not in os.environ


def test_config_missing_or_different_model_fails_closed(monkeypatch):
    for name in ("CONTINUITY_BASE_URL", "CONTINUITY_MODEL", "CONTINUITY_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError, match="MISSING"):
        load_provider_config()
    monkeypatch.setenv("CONTINUITY_BASE_URL", EXPECTED_BASE)
    monkeypatch.setenv("CONTINUITY_MODEL", "different")
    monkeypatch.setenv("CONTINUITY_API_KEY", CONFIG["api_key"])
    with pytest.raises(ValueError, match="DIFFERS"):
        load_provider_config()


def test_metadata_model_alias_not_confused_with_key():
    assert atom("ark-code-latest", CONFIG["api_key"]) == "ark-code-latest"
    assert atom(CONFIG["api_key"], CONFIG["api_key"]) is None
    secret_exception = type(CONFIG["api_key"], (Exception,), {})
    assert exception_type(secret_exception()) == "OtherException"
    assert failure_stage(ImportError("private")) == "PYTHON_ENVIRONMENT"


def test_zero_decisions_or_only_unchanged_state_cannot_be_supported():
    base = {"termination_reason": "BUDGET_COMPLETED", "completed_decisions": 0,
            "final_invariants": {"invariants": "PASS"}}
    assert continuity_result(base, [], cleanup_error=None) == "INSUFFICIENT_EVIDENCE"
    rows = [{"decision_status": "DECISION_ACCEPTED", "commitment_status": "COMPLETED",
             "STATE_FEEDBACK_VISIBLE": True, "STATE_FEEDBACK_CHANGED": False}] * 4
    base["completed_decisions"] = 4
    assert continuity_result(base, rows, cleanup_error=None) == "INSUFFICIENT_EVIDENCE"


def test_runtime_rejects_cache_pythonpath(monkeypatch):
    from social_sim.provider_runtime.environment import inspect_runtime
    monkeypatch.setenv("PYTHONPATH", "/tmp/uv/archive-v0/one:/tmp/uv/archive-v0/two")
    result = inspect_runtime()
    assert result["result"] == "FAIL"
    assert "PYTHONPATH_MUST_BE_EMPTY" in result["issues"]
    assert result["provider_requests"] == 0


def test_existing_session_does_not_call_provider(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("q61_cli_test", ROOT / "scripts/check_q6_1_provider_runtime.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "inspect_runtime", lambda: {"result": "PASS"})
    monkeypatch.setattr(module, "repository_info", lambda root: {})
    session = tmp_path / "run/evaluation/q6_1_provider_runtime/once"
    session.mkdir(parents=True)
    def fail(*args, **kwargs):
        pytest.fail("provider configuration must not be read for duplicate session")
    monkeypatch.setattr(module, "load_provider_config", fail)
    assert module.main(["--allow-provider", "--session-id", "once"]) == 1
