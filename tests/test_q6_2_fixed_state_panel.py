"""Full panel pipeline, with no external request and no actual credential reads."""
from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from social_sim.continuity.engine import ContinuityWorld
from social_sim.continuity.models import digest
from social_sim.continuity.q6_2_panel import (
    ScriptedPanelClient, export_only, prepare_session, run_session,
)
from social_sim.continuity.q6_2_panel_ledger import read_session
from social_sim.decision.client import DecisionClientError, DecisionResponseMetadata, ProviderContractError


def run(tmp_path, client, session="run", **kwargs):
    with prepare_session(tmp_path, session, mode="offline") as ledger:
        summary = asyncio.run(run_session(ledger, mode="offline", client=client, progress=None, **kwargs))
        return summary, ledger.rows(), ledger.dir


@pytest.mark.parametrize("case,expected_calls", [("a-illegal-b-legal", 48), ("both-legal", 48),
                                                ("b-worse", 48), ("no-valid-proposal", 1)])
def test_complete_scripted_cases_are_not_model_results(tmp_path, case, expected_calls):
    client = ScriptedPanelClient(case)
    summary, rows, directory = run(tmp_path, client)
    assert client.call_count == expected_calls
    assert summary["counts"]["planned"] == 48
    assert summary["pair_counts"]["planned"] == 24
    assert len(rows) == 48
    assert summary["real_provider_requests"] == 0
    assert summary["MODEL_BENEFIT"] == "NOT_TESTED"
    assert summary["mode"] == "OFFLINE_SYNTHETIC"
    assert all((directory / "cells" / row["cell_id"] / "world.sqlite3").exists() for row in rows)
    a = summary["by_condition"]["A_RAW"]["ratios"]["rule_rejection_rate"]["value"]
    b = summary["by_condition"]["B_FEASIBLE"]["ratios"]["rule_rejection_rate"]["value"]
    if case == "a-illegal-b-legal":
        assert a > b == 0
    elif case == "b-worse":
        assert b > a == 0
    elif case == "both-legal":
        assert a == b == 0
    else:
        assert a is None and b is None
        assert summary["counts"]["not_run"] == 47
        assert summary["counts"]["http_response_observed"] == 1
        assert summary["counts"]["service_contract_valid"] == 1
        assert summary["counts"]["strict_json_valid"] == 0
    assert summary["STATE_FEEDBACK_VISIBLE"] == "NOT_APPLICABLE"
    assert summary["costs"]["input_tokens"]["known_subtotal"] is None


class ProposalClient:
    def __init__(self, text):
        self.text, self.call_count = text, 0
        self.last_metadata = SimpleNamespace(http_status=200, provider_model=None)

    async def complete(self, system, user):
        self.call_count += 1
        body = json.loads(user)
        assert not {"scenario_id", "family", "repeat", "expected", "label"} & body.keys()
        return SimpleNamespace(raw_text=self.text)


def test_meal_known_failures_continue_and_do_not_rollback_travel(tmp_path):
    client = ProposalClient('{"activity":"MEAL","target":"food_meal"}')
    summary, rows, _ = run(tmp_path, client)
    assert client.call_count == 48
    failures = [r for r in rows if r["status"] == "COMMITMENT_FAILED"]
    assert failures
    assert {r["execution_failure_reason"] for r in failures} == {"INSUFFICIENT_FUNDS", "OUT_OF_STOCK"}
    assert all(r["invariants_valid"] and r["start_accepted"] for r in failures)
    assert all(r["after_state"]["location"] == "restaurant" and r["simulation_minutes"] == 15 for r in failures)
    assert summary["counts"]["valid_proposals"] == 48
    assert summary["counts"]["rule_rejected"] == 0


@pytest.mark.parametrize("failure,status", [("timeout", "PROVIDER_TIMEOUT"),
    ("http", "HTTP_ERROR"), ("transport", "TRANSPORT_ERROR"),
    ("contract", "PROVIDER_CONTRACT_ERROR"), ("cancel", "REQUEST_CANCELLED"),
    ("import", "ARCHITECTURE_ERROR")])
def test_fatal_paths_stop_all_remaining_cells(tmp_path, failure, status):
    class Client:
        call_count = 0
        last_metadata = None
        async def complete(self, _system, _user):
            self.call_count += 1
            if failure == "http":
                self.last_metadata = DecisionResponseMetadata(http_status=429)
                raise DecisionClientError("PRIVATE_SENTINEL_ERROR_BODY")
            if failure == "contract":
                raise ProviderContractError("NO_CHOICES", DecisionResponseMetadata(http_status=200))
            errors = {"timeout": TimeoutError, "transport": httpx.ConnectError,
                      "cancel": asyncio.CancelledError, "import": ImportError}
            raise errors[failure]("PRIVATE_SENTINEL_ERROR_BODY")
    client = Client()
    summary, rows, directory = run(tmp_path, client)
    assert client.call_count == 1
    assert rows[0]["status"] == status
    assert summary["counts"]["not_run"] == 47
    assert all(r["status"] == "NOT_RUN" and r["stop_reason"] == status for r in rows[1:])
    for path in directory.rglob("*"):
        if path.is_file():
            assert b"PRIVATE_SENTINEL_ERROR_BODY" not in path.read_bytes()


def test_outside_catalog_keeps_safe_parse_stage_not_raw_target(tmp_path):
    sentinel = "PRIVATE_SENTINEL_TARGET"
    client = ProposalClient(json.dumps({"activity": "PLAY", "target": sentinel}))
    summary, rows, directory = run(tmp_path, client)
    assert rows[0]["status"] == "OUTSIDE_CATALOG"
    assert rows[0]["strict_json_valid"] is True and rows[0]["catalog_valid"] is False
    assert rows[0]["proposal_target"] is None
    assert rows[0]["proposal_target_hash"] == digest(sentinel)
    assert summary["counts"]["valid_proposals"] == 0
    assert summary["ratios"]["rule_rejection_rate"]["value"] is None
    for path in directory.rglob("*"):
        if path.is_file():
            assert sentinel.encode() not in path.read_bytes()


def test_dry_run_needs_no_client_and_recovery_is_readonly(tmp_path):
    with prepare_session(tmp_path / "registry", "dry") as ledger:
        summary = asyncio.run(run_session(ledger, mode="dry-run"))
        assert summary["counts"]["not_run"] == 48
        assert summary["real_provider_requests"] == 0
        source = ledger.dir
    before = {str(p): p.read_bytes() for p in source.rglob("*") if p.is_file()}
    recovered = export_only(source, tmp_path / "recovered")
    assert recovered["counts"]["not_run"] == 48
    assert before == {str(p): p.read_bytes() for p in source.rglob("*") if p.is_file()}
    with pytest.raises(FileExistsError):
        prepare_session(tmp_path / "registry", "dry", mode="offline")


def test_actual_wire_contract_remains_minimal_offline(tmp_path):
    from social_sim.decision import OpenAICompatibleDecisionClient
    bodies = []
    def transport(request):
        body = json.loads(request.content)
        bodies.append(body)
        assert set(body) == {"model", "messages"}
        assert [m["role"] for m in body["messages"]] == ["system", "user"]
        return httpx.Response(200, json={"model": "MOCK_BACKEND", "choices": [{"finish_reason": "stop",
            "message": {"content": '{"activity":"LEISURE","target":null}'}}]})
    async def exercise():
        client = OpenAICompatibleDecisionClient(base_url="https://offline.invalid/v1", model="fake-alias",
            api_key="PRIVATE_CREDENTIAL_SENTINEL", minimal_request=True,
            transport=httpx.MockTransport(transport))
        try:
            with prepare_session(tmp_path, "wire", mode="offline") as ledger:
                return await run_session(ledger, mode="offline", client=client, progress=None), ledger.rows()
        finally:
            await client.aclose()
    summary, rows = asyncio.run(exercise())
    assert len(bodies) == 48 and summary["real_provider_requests"] == 0
    assert all(r["provider_model"] == "MOCK_BACKEND" for r in rows)
    for path in (tmp_path / "wire").rglob("*"):
        if path.is_file():
            assert b"PRIVATE_CREDENTIAL_SENTINEL" not in path.read_bytes()


def load_cli():
    path = Path(__file__).resolve().parents[1] / "scripts/run_q6_2_fixed_state_panel.py"
    spec = importlib.util.spec_from_file_location("panel_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_help_and_real_requires_both_explicit_gates(capsys, monkeypatch):
    cli = load_cli()
    assert all(flag in cli.parser().format_help() for flag in
               ("--mode", "--allow-provider", "--export-only", "--env-file", "--execution-commit", "--protocol-hash"))
    monkeypatch.setattr(cli, "prepare_session", lambda *_a, **_k: pytest.fail("must not prepare real"))
    assert cli.main(["--mode", "real", "--session-id", "denied"]) == 1
    assert "REAL_PROVIDER_NOT_AUTHORIZED" in capsys.readouterr().out
    assert cli.main(["--mode", "real", "--session-id", "denied", "--allow-provider"]) == 1
    for args in (["--session-id", "dry", "--allow-provider"],
                 ["--session-id", "dry", "--output", "elsewhere"],
                 ["--session-id", "dry", "--max-requests", "49"]):
        with pytest.raises(SystemExit):
            cli.main(args)


def test_prompt_hook_is_optin_and_response_saved_before_parse(tmp_path):
    from social_sim.continuity.benchmark import seed_demo
    from social_sim.continuity.decision import ActivityDecisionRunner
    seen = []
    with ContinuityWorld(tmp_path / "one.sqlite3") as world:
        seed_demo(world)
        runner = ActivityDecisionRunner(world, ProposalClient("not JSON"),
                                        evidence_hook=lambda stage, data: seen.append((stage, data)))
        raw = asyncio.run(runner.decide("single"))
        assert raw["status"] == "INVALID_MODEL_OUTPUT"
        assert [stage for stage, _data in seen] == ["REQUEST_STARTED", "RESPONSE_OBSERVED", "PARSE_RESULT", "DECISION_RECORDED"]
        assert seen[1][1]["http_status"] == 200


def test_unknown_backend_does_not_gain_comparability(tmp_path):
    summary, rows, _ = run(tmp_path, ProposalClient('{"activity":"LEISURE","target":null}'))
    assert summary["pair_counts"]["backend_unknown"] == 24
    assert summary["pair_counts"]["comparable_scored"] == 0
    assert all(r["provider_model"] is None for r in rows)


def test_world_invariant_failure_is_fatal(tmp_path):
    class Poison(ProposalClient):
        async def complete(self, system, user):
            import sqlite3
            # Synthetic fault injection only, not a fixture-setting production path.
            path = tmp_path / "run/cells/c001/world.sqlite3"
            with sqlite3.connect(path) as db:
                data = json.loads(db.execute("SELECT data FROM actors WHERE id=1").fetchone()[0])
                data["money_cents"] += 1
                db.execute("UPDATE actors SET data=? WHERE id=1", (json.dumps(data),))
            return await super().complete(system, user)
    summary, rows, _ = run(tmp_path, Poison('{"activity":"LEISURE","target":null}'))
    assert rows[0]["status"] == "STATE_INVARIANT_FAILED"
    assert summary["counts"]["not_run"] == 47


def test_activity_limit_is_not_reported_as_complete(tmp_path):
    from social_sim.continuity.q6_2_panel_fixtures import load_protocol
    protocol = load_protocol()
    # Hard execution fault testing uses the public single-activity helper.
    from social_sim.continuity.q6_2_panel import PanelStop, execute_activity
    from social_sim.continuity.q6_2_panel_fixtures import build_world
    with build_world(tmp_path / "limited.sqlite3", "s01", protocol) as world:
        assert world.start("long", 1, "SLEEP")["accepted"]
        with pytest.raises(PanelStop, match="EXECUTION_LIMIT_EXCEEDED"):
            execute_activity(world, "long", 1)
        assert world.store.get_commitment("long")["status"] == "ACTIVE"


def test_progress_and_calls_are_incremental(tmp_path):
    progress = []
    with prepare_session(tmp_path, "incremental", mode="offline") as ledger:
        summary = asyncio.run(run_session(ledger, mode="offline", client=ScriptedPanelClient("both-legal"),
                                         progress=progress.append))
        saved = read_session(ledger.dir)
        assert saved["claimed_count"] == 48
    assert len(progress) == 48
    assert "CALLS=1" in progress[0] and "CALLS=48" in progress[-1]
    assert summary["counts"]["activity_completed"] == 48


def test_reused_client_does_not_reuse_a_previous_http_receipt(tmp_path):
    class Client:
        call_count = 0
        last_metadata = None
        async def complete(self, _system, _user):
            self.call_count += 1
            if self.call_count == 1:
                self.last_metadata = SimpleNamespace(http_status=200, provider_model="FIRST_ONLY", input_tokens=42)
                return SimpleNamespace(raw_text='{"activity":"LEISURE","target":null}')
            # Deliberately defective fake leaves its old last_metadata object untouched.
            raise httpx.ConnectError("PRIVATE_SENTINEL")
    summary, rows, _ = run(tmp_path, Client())
    assert rows[0]["http_status"] == 200
    assert rows[1]["status"] == "TRANSPORT_ERROR"
    assert rows[1]["http_status"] is None and rows[1]["provider_model"] is None
    assert rows[1]["input_tokens"] is None
    assert summary["counts"]["http_response_observed"] == 1


def test_reply_metadata_is_preserved_even_without_client_metadata(tmp_path):
    class Client:
        async def complete(self, _system, _user):
            return SimpleNamespace(raw_text='{"activity":"LEISURE","target":null}',
                input_tokens=7, output_tokens=3, reasoning_tokens=None, provider_model="REPLY_ONLY")
    summary, rows, _ = run(tmp_path, Client())
    assert all(r["input_tokens"] == 7 and r["output_tokens"] == 3 for r in rows)
    assert summary["costs"]["input_tokens"]["known_subtotal"] == 336
    assert summary["costs"]["reasoning_tokens"]["known_subtotal"] is None


def test_normal_exception_after_response_preserves_stage_evidence(tmp_path):
    def interrupt(stage, _cid):
        if stage == "response_observed":
            raise RuntimeError("PRIVATE_ERROR_SENTINEL")
    summary, rows, _ = run(tmp_path, ScriptedPanelClient("both-legal"), fault_hook=interrupt)
    assert rows[0]["status"] == "ARCHITECTURE_ERROR"
    assert rows[0]["http_response_observed"] is True
    assert rows[0]["service_contract_valid"] is True
    assert rows[0]["strict_json_valid"] is None
    assert summary["counts"]["not_run"] == 47


def test_same_handle_cannot_run_twice(tmp_path):
    with prepare_session(tmp_path, "once", mode="offline") as ledger:
        asyncio.run(run_session(ledger, mode="offline", client=ScriptedPanelClient("both-legal"), progress=None))
        second = ScriptedPanelClient("both-legal")
        with pytest.raises(ValueError, match="NO_RESUME_OR_RERUN"):
            asyncio.run(run_session(ledger, mode="offline", client=second, progress=None))
        assert second.call_count == 0


def test_changed_world_and_local_audit_cannot_bypass_database_manifest(tmp_path):
    from social_sim.continuity.q6_2_panel import _audit
    with prepare_session(tmp_path, "frozen", mode="offline") as ledger:
        plan = read_session(ledger.dir)["manifest"]["cells"][0]
        directory = ledger.dir / "cells/c001"
        with ContinuityWorld(directory / "world.sqlite3") as world:
            assert world.start("changed", 1, "LEISURE")["accepted"]
            from social_sim.continuity.q6_2_panel import execute_activity
            execute_activity(world, "changed", 96)
            # Simulate someone rewriting the adjacent artifact as well as the world.
            (directory / "initial_audit.json").write_text(json.dumps(_audit(world, plan["condition"], 5000)))
        client = ScriptedPanelClient("both-legal")
        summary = asyncio.run(run_session(ledger, mode="offline", client=client, progress=None))
        assert client.call_count == 0
        assert summary["counts"]["not_run"] == 48
        assert summary["session_status"] == "ARCHITECTURE_ERROR"
