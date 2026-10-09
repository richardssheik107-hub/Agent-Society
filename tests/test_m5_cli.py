"""CLI subprocess safety and authorized mock-only real-path integration."""
from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from social_sim.longrun.config import LongRunConfig
from social_sim.longrun.provider import M5ProviderClient
from social_sim.longrun.runner import LongRunRunner
from social_sim.longrun.session import LongRunSession

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_m5_long_horizon.py"
COMMIT = "a" * 40


def cli_module():
    spec = importlib.util.spec_from_file_location("m5_cli_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def subprocess_cli(*args, guard=False):
    environment = dict(os.environ)
    environment["CONTINUITY_API_KEY"] = "sentinel-existing-key-is-not-authorization"
    code = """
import runpy, sys
sys.path.insert(0, 'src')
from social_sim.decision.client import OpenAICompatibleDecisionClient
from social_sim.provider_runtime import environment
def forbidden(*a, **k):
    raise AssertionError('offline must not read credentials or construct provider')
OpenAICompatibleDecisionClient.__init__ = forbidden
environment.load_provider_config = forbidden
sys.argv = ['scripts/run_m5_long_horizon.py', *sys.argv[1:]]
runpy.run_path('scripts/run_m5_long_horizon.py', run_name='__main__')
"""
    command = [sys.executable, "-c", code] if guard else [sys.executable, str(SCRIPT)]
    return subprocess.run([*command, *map(str, args)], cwd=ROOT, env=environment,
                          text=True, capture_output=True, timeout=60)


def test_actual_subprocess_help_contract():
    result = subprocess_cli("--help", guard=True)
    assert result.returncode == 0, result.stderr
    for name in ("--mode", "--session-id", "--sim-days", "--max-decisions",
                 "--max-provider-requests", "--max-wall-seconds", "--allow-provider",
                 "--execution-commit", "--protocol-hash", "--env-file", "--export-only",
                 "--resume", "--authorization-path", "--protocol"):
        assert name in result.stdout


def test_default_offline_actual_subprocess_never_reads_key_or_constructs_real_client(tmp_path):
    result = subprocess_cli("--sim-days", 1, "--output-root", tmp_path, guard=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "NEW_REAL_PROVIDER_REQUESTS=0" in result.stdout
    assert "SCRIPTED_OR_FAKE_LONG_RUN" in result.stdout
    session_dir = next(path for path in tmp_path.iterdir() if path.is_dir())
    data = LongRunSession.export_only(session_dir)
    assert data["world"]["minute"] == 1440
    assert data["session"]["provider_requests_reserved"] == 0
    assert data["session"]["decisions"] > 0
    assert all(row["provider_requests"] == 0 for row in data["requests"])
    assert data["manifest"]["config"]["mode"] == "offline"
    assert (session_dir / "report.md").is_file()


@pytest.mark.parametrize("extra", [[], ["--allow-provider"],
                                   ["--allow-provider", "--max-provider-requests", "1"]])
def test_real_default_zero_authorization_refuses_before_env_read(tmp_path, extra):
    result = subprocess_cli("--mode", "real", "--session-id", "unauthorized",
                            "--env-file", tmp_path / "never-read.env", *extra, guard=True)
    assert result.returncode == 1
    assert "ZERO_PROVIDER_BUDGET_NOT_AUTHORIZED" in result.stdout
    assert "NEW_REAL_PROVIDER_REQUESTS=0" in result.stdout
    assert "must not read credentials" not in result.stderr


def file_hashes(directory):
    return {str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in directory.rglob("*") if path.is_file()}


def test_export_only_subprocess_is_read_only_and_cannot_overwrite_history(tmp_path):
    source = tmp_path / "sessions"
    with LongRunSession.create(source, "source", LongRunConfig(sim_days=1), {}) as session:
        asyncio.run(LongRunRunner(session, _sleep_fake()).run(max_steps=1))
    session_dir = source / "source"
    before = file_hashes(session_dir)
    output = tmp_path / "export"
    result = subprocess_cli("--export-only", session_dir, "--output", output, guard=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "NEW_REAL_PROVIDER_REQUESTS=0" in result.stdout
    assert file_hashes(session_dir) == before
    assert json.loads((output / "export.json").read_text())["world"]["minute"] == 15
    exported = file_hashes(output)
    again = subprocess_cli("--export-only", session_dir, "--output", output, guard=True)
    assert again.returncode != 0
    assert file_hashes(output) == exported and file_hashes(session_dir) == before


def _sleep_fake():
    from social_sim.decision.client import DecisionReply
    class Fake:
        mode = "offline"
        provider_request_count = 0
        async def complete(self, system, user):
            return DecisionReply('{"activity":"SLEEP","target":null}')
    return Fake()


def auth(config, session, *, resume=False):
    return {"authorization_type": "EXPLICIT_USER_SESSION_AUTHORIZATION", "approved": True,
        "session_id": session, "execution_commit": COMMIT, "protocol_hash": config.protocol_hash,
        "max_provider_requests": config.max_provider_requests,
        "acceptance": {"execution_commit": COMMIT, "result": "PASS"},
        "request_policy": {"retry": False, "fallback": False}, "resume": resume}


def patch_real_gates(module, monkeypatch, registry):
    monkeypatch.setattr(module, "REGISTRY", registry)
    monkeypatch.setattr(module, "git_value", lambda *args: COMMIT)
    monkeypatch.setattr("social_sim.provider_runtime.environment.repository_info", lambda root: {
        "git_commit": COMMIT, "parent_repository": True, "worktree_clean": True,
        "upstream_matches": True})
    monkeypatch.setattr("social_sim.provider_runtime.environment.inspect_runtime",
                        lambda: {"result": "PASS"})
    monkeypatch.setattr(module, "load_provider_environment", lambda path: {
        "base_url": "https://offline.invalid/v1", "api_key": "mock-only-placeholder",
        "model": "ark-code-latest"})


def wire(content):
    return {"model": "mock-backend", "choices": [{"finish_reason": "stop",
        "message": {"content": content, "reasoning_content": "never persist hidden text"}}]}


def test_real_cli_executes_actual_mock_posts_with_independent_authorization(tmp_path, monkeypatch):
    module = cli_module()
    registry = tmp_path / "sessions"
    patch_real_gates(module, monkeypatch, registry)
    config = replace(LongRunConfig(), mode="real", max_provider_requests=2)
    protocol = tmp_path / "protocol.json"
    protocol.write_text(json.dumps(config.to_dict()), encoding="utf-8")
    authorization = tmp_path / "authorization.json"
    authorization.write_text(json.dumps(auth(config, "mock_real")), encoding="utf-8")
    posts = []
    def handle(request):
        posts.append(request)
        proposal = ('{"activity":"ACQUIRE","target":"game_a"}' if len(posts) == 1
                    else '{"activity":"PLAY","target":"game_a"}')
        return httpx.Response(200, json=wire(proposal))
    clients = []
    def factory(provider, frozen):
        client = M5ProviderClient(provider, frozen, transport=httpx.MockTransport(handle))
        clients.append(client)
        return client
    monkeypatch.setattr(module, "M5ProviderClient", factory)
    result = module.main(["--mode", "real", "--session-id", "mock_real", "--protocol", str(protocol),
        "--allow-provider", "--execution-commit", COMMIT, "--protocol-hash", config.protocol_hash,
        "--authorization-path", str(authorization)])
    assert result == 1  # Truthful budget truncation, not a seven-day PASS.
    assert len(posts) == 2 and all(request.method == "POST" for request in posts)
    assert clients[0]._client._http.is_closed
    saved = LongRunSession.export_only(registry / "mock_real")
    assert saved["session"]["stop_reason"] == "REQUEST_BUDGET_REACHED"
    assert saved["session"]["provider_requests_reserved"] == 2
    game = next(link["state"] for link in saved["world"]["links"] if link["object_id"] == "game_a")
    assert game["quantity"] == 1 and game["play_minutes"] > 0
    assert all(row["input_tokens"] is None for row in saved["requests"])
    assert "never persist hidden text" not in json.dumps(saved)


def test_real_resume_finishes_existing_activity_before_next_mock_request(tmp_path, monkeypatch):
    module = cli_module()
    registry = tmp_path / "sessions"
    patch_real_gates(module, monkeypatch, registry)
    config = replace(LongRunConfig(), mode="real", max_provider_requests=2)
    original = auth(config, "real_resume")
    def office_fixture(world, frozen):
        from social_sim.longrun.policy import seed_world
        seed_world(world, frozen)
        assert world.start("fixture-office", 1, "TRAVEL", "office")["accepted"]
        assert world.advance("fixture-office-end", 30)["accepted"]
    with LongRunSession.create(registry, "real_resume", config, {
            "execution_commit": COMMIT, "execution_authorization": original},
            seed_world=office_fixture) as session:
        client = M5ProviderClient({"base_url": "https://offline.invalid/v1",
            "model": "ark-code-latest", "api_key": "mock-placeholder"}, config,
            transport=httpx.MockTransport(lambda request: httpx.Response(200,
                json=wire('{"activity":"ACQUIRE","target":"game_a"}'))))
        async def pause():
            try:
                return await LongRunRunner(session, client).run(max_steps=1)
            finally:
                await client.aclose()
        paused = asyncio.run(pause())
        assert paused["state"] == "PAUSED" and paused["active_commitment"]
        assert client.provider_request_count == 1
    protocol = tmp_path / "protocol.json"
    protocol.write_text(json.dumps(config.to_dict()), encoding="utf-8")
    authorization = tmp_path / "resume.json"
    authorization.write_text(json.dumps(auth(config, "real_resume", resume=True)), encoding="utf-8")
    posts = []
    clients = []
    def handle(request):
        # The new independent decision may be posted only after deterministic
        # travel and purchase have finished using the already committed intent.
        data = LongRunSession.export_only(registry / "real_resume")
        game = next(link["state"] for link in data["world"]["links"]
                    if link["object_id"] == "game_a")
        assert game["quantity"] == 1
        assert not any(c["status"] == "ACTIVE" for c in data["world"]["commitments"])
        posts.append(request)
        return httpx.Response(200, json=wire('{"activity":"PLAY","target":"game_a"}'))
    def factory(provider, frozen):
        client = M5ProviderClient(provider, frozen, transport=httpx.MockTransport(handle))
        clients.append(client)
        return client
    monkeypatch.setattr(module, "M5ProviderClient", factory)
    result = module.main(["--mode", "real", "--resume", str(registry / "real_resume"),
        "--protocol", str(protocol), "--allow-provider", "--execution-commit", COMMIT,
        "--protocol-hash", config.protocol_hash, "--authorization-path", str(authorization)])
    assert result == 1 and len(posts) == 1
    assert clients[0]._client._http.is_closed
    saved = LongRunSession.export_only(registry / "real_resume")
    assert saved["session"]["provider_requests_reserved"] == 2
    assert saved["session"]["resume_count"] == 1
    assert saved["session"]["stop_reason"] == "REQUEST_BUDGET_REACHED"
    receipt = json.loads((registry / "real_resume" / "resume_authorization_000001.json").read_text())
    assert receipt["execution_authorization"]["resume"] is True
    cleanup = json.loads((registry / "real_resume" / "cleanup_run_000001.json").read_text())
    assert cleanup["cleanup_outcome"] == "CLOSED"


def test_uncertain_real_resume_refuses_before_key_read(tmp_path, monkeypatch):
    module = cli_module()
    registry = tmp_path / "sessions"
    patch_real_gates(module, monkeypatch, registry)
    config = replace(LongRunConfig(), mode="real", max_provider_requests=2)
    with LongRunSession.create(registry, "unknown", config, {
            "execution_commit": COMMIT, "execution_authorization": auth(config, "unknown")}) as session:
        session.register_request(session.world.store.actor(1)["version"], {})
        session.transition("RECOVERY_REQUIRED", "UNCERTAIN_REQUEST_STATE")
    before = file_hashes(registry / "unknown")
    def forbidden(path):
        raise AssertionError("unknown request may not read key")
    monkeypatch.setattr(module, "load_provider_environment", forbidden)
    protocol = tmp_path / "protocol.json"
    protocol.write_text(json.dumps(config.to_dict()), encoding="utf-8")
    result = module.main(["--mode", "real", "--resume", str(registry / "unknown"),
        "--protocol", str(protocol), "--allow-provider", "--execution-commit", COMMIT,
        "--protocol-hash", config.protocol_hash])
    assert result == 1 and file_hashes(registry / "unknown") == before


def test_offline_resume_actual_cli_preserves_money_and_activity(tmp_path):
    config = LongRunConfig(sim_days=1)
    with LongRunSession.create(tmp_path, "offline_resume", config, {}) as session:
        asyncio.run(LongRunRunner(session, _sleep_fake()).run(max_steps=1))
        money = session.world.store.actor(1)["money_cents"]
    result = subprocess_cli("--resume", tmp_path / "offline_resume", guard=True)
    assert result.returncode == 0, result.stderr + result.stdout
    saved = LongRunSession.export_only(tmp_path / "offline_resume")
    assert saved["world"]["minute"] == 1440 and saved["session"]["resume_count"] == 1
    assert saved["session"]["provider_requests_reserved"] == 0
    assert money == saved["session"]["initial_state"]["actors"][0]["money_cents"]


@pytest.mark.parametrize("audit_status", ["FAIL", "UNVERIFIED"])
def test_final_full_audit_failure_overrides_provisional_horizon_success(tmp_path, monkeypatch,
                                                                     capsys, audit_status):
    module = cli_module()
    from social_sim.longrun.evaluation import InvariantViolation
    from social_sim.longrun import reporting
    seen_states = []
    original_export = reporting.export_reports
    def failed_full_audit(world):
        assert world.minute == 1440
        if audit_status == "FAIL":
            raise InvariantViolation("FINAL_FULL_AUDIT_FAILURE")
        return {"invariants": "UNVERIFIED", "L1": "UNVERIFIED"}
    def observed_export(session, *args, **kwargs):
        seen_states.append(session.load()["state"])
        return original_export(session, *args, **kwargs)
    monkeypatch.setattr(reporting, "check_invariants_full", failed_full_audit)
    monkeypatch.setattr(reporting, "export_reports", observed_export)
    result = module.main(["--sim-days", "1", "--session-id", "final_audit_failure",
                          "--output-root", str(tmp_path)])
    assert result == 1
    printed = capsys.readouterr().out
    assert '"stop_reason": "INVARIANT_FAILED"' in printed
    assert '"final_audit_failed": true' in printed
    assert "NEW_REAL_PROVIDER_REQUESTS=0" in printed
    assert seen_states == ["COMPLETED", "STOPPED_BY_FAILURE"]
    directory = tmp_path / "final_audit_failure"
    saved = LongRunSession.export_only(directory)
    assert saved["world"]["minute"] == saved["session"]["horizon_minute"] == 1440
    assert saved["session"]["state"] == "STOPPED_BY_FAILURE"
    assert saved["session"]["stop_reason"] == "INVARIANT_FAILED"
    summary = json.loads((directory / "summary.json").read_text())
    assert summary["horizon_reached"] is True
    assert summary["stop_reason"] == "INVARIANT_FAILED"
    assert summary["evaluation"]["L1"]["status"] == "FAIL"
    assert summary["evaluation"]["L2"]["evidence_status"] == "UNTRUSTED_ENGINEERING_FAILURE"
    assert "L1 工程一致性：FAIL" in (directory / "report.md").read_text()
