"""面板预算/身份/中断证据与只读源库测试；不读取凭据或构造真实 client。"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from social_sim.continuity.benchmark import seed_demo
from social_sim.continuity.engine import ContinuityWorld
from social_sim.continuity.q6_2_panel_ledger import (
    LedgerError,
    create_session,
    open_readonly_world,
    read_session,
    read_world,
)
from social_sim.continuity.q6_1 import project_state
from social_sim.continuity.validation import validate_world


def _manifest() -> dict:
    return {"protocol_version": "q62_fixed_panel_v1", "seed": 20261008,
            "cells": [{"cell_id": f"cell-{index:02d}", "pair_id": f"pair-{index // 2:02d}",
                       "arm": "A_RAW" if index % 2 == 0 else "B_FEASIBLE"}
                      for index in range(48)]}


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_exclusive_session_keeps_frozen_48_allocation_and_execution_version(tmp_path):
    manifest = _manifest()
    with create_session(tmp_path, "one", manifest, {
        "execution_commit": "1" * 40, "mode": "dry-run"}) as ledger:
        assert ledger.dir == tmp_path / "one"
        assert ledger.path == ledger.dir / "session.sqlite3"
        assert len(ledger.rows()) == 48
        assert all(row["status"] == "NOT_RUN" for row in ledger.rows())
        assert ledger.claimed_count == 0
    with pytest.raises(FileExistsError):
        create_session(tmp_path, "one", manifest, {"mode": "offline"})
    exported = read_session(tmp_path / "one")
    assert exported["manifest"] == manifest
    assert exported["metadata"]["execution_commit"] == "1" * 40
    assert exported["planned_cells"] == exported["max_calls"] == 48
    assert exported["max_calls_per_cell"] == 1
    assert exported["resume_allowed"] is False


@pytest.mark.parametrize("session_id", ["../escape", "a/b", ".", "..", "", "x" * 65])
def test_session_paths_cannot_escape_fixed_registry(tmp_path, session_id):
    with pytest.raises(ValueError, match="INVALID_SESSION_ID"):
        create_session(tmp_path, session_id, _manifest(), {})
    assert list(tmp_path.iterdir()) == []


def test_concurrent_start_reserves_exactly_one_local_identity(tmp_path):
    def start():
        try:
            with create_session(tmp_path, "concurrent", _manifest(), {}):
                return "CREATED"
        except FileExistsError:
            return "EXISTS"

    with ThreadPoolExecutor(max_workers=2) as workers:
        outcomes = list(workers.map(lambda _index: start(), range(2)))
    assert sorted(outcomes) == ["CREATED", "EXISTS"]
    assert len(read_session(tmp_path / "concurrent")["cells"]) == 48


def test_claim_is_atomic_per_cell_and_preserves_unknown_before_client_entry(tmp_path):
    with create_session(tmp_path, "duplicate", _manifest(), {}) as ledger:
        def claim():
            try:
                return ledger.claim("cell-00")
            except LedgerError:
                return "DUPLICATE"

        with ThreadPoolExecutor(max_workers=2) as workers:
            outcomes = list(workers.map(lambda _index: claim(), range(2)))
        assert outcomes.count("DUPLICATE") == 1
        assert ledger.claimed_count == 1
        row = ledger.rows()[0]
        assert row["status"] == row["request_send_status"] == "UNKNOWN"
        assert row["call_intent_registered"] is True
        assert row["client_call_attempted"] is None
        assert row["application_calls"] is row["provider_requests"] is None
        assert row["missing_evidence"] == ["FINAL_ROW"]
    exported = read_session(tmp_path / "duplicate")
    assert exported["claimed_count"] == 1
    assert exported["rows"][0]["provider_requests"] is None
    assert exported["resume_allowed"] is False


def test_48_request_intents_are_prelimited_and_never_refunded(tmp_path):
    with create_session(tmp_path, "budget", _manifest(), {}) as ledger:
        with ThreadPoolExecutor(max_workers=8) as workers:
            requests = list(workers.map(ledger.claim, [f"cell-{i:02d}" for i in range(48)]))
        assert len(set(requests)) == 48
        assert ledger.claimed_count == 48
        with pytest.raises(LedgerError, match="CELL_ALREADY_CLAIMED"):
            ledger.claim("cell-00")
        with pytest.raises(LedgerError, match="CELL_NOT_ALLOCATED"):
            ledger.claim("cell-48")
        ledger.finish("cell-00", {"status": "PROVIDER_TIMEOUT", "provider_requests": None})
        assert ledger.claimed_count == 48
        with pytest.raises(LedgerError, match="CELL_ALREADY_CLAIMED"):
            ledger.claim("cell-00")


def test_client_entry_cannot_be_registered_twice(tmp_path):
    with create_session(tmp_path, "client", _manifest(), {}) as ledger:
        ledger.claim("cell-00")
        ledger.record("cell-00", "CLIENT_CALL_STARTED", {"application_calls": 1})
        with pytest.raises(LedgerError, match="CELL_CLIENT_CALL_ALREADY_STARTED"):
            ledger.record("cell-00", "CLIENT_CALL_STARTED", {"application_calls": 1})
        row = ledger.rows()[0]
        assert row["client_call_attempted"] is True and row["application_calls"] == 1
        assert row["provider_requests"] is None


def test_response_before_final_result_keeps_evidence_without_inventing_success(tmp_path):
    with create_session(tmp_path, "response", _manifest(), {}) as ledger:
        ledger.claim("cell-00")
        ledger.record("cell-00", "CLIENT_CALL_STARTED", {"application_calls": 1})
        ledger.record("cell-00", "RESPONSE_OBSERVED", {
            "http_status": 200, "input_tokens": 13, "output_tokens": None,
            "reasoning_tokens": None, "provider_model": None,
            "service_contract_valid": True})
    before = _hash(tmp_path / "response/session.sqlite3")
    exported = read_session(tmp_path / "response")
    assert exported["rows"][0]["status"] == "UNKNOWN"
    assert exported["rows"][0]["http_response_observed"] is True
    assert exported["rows"][0].get("strict_json_valid") is None
    assert exported["evidence"][-1]["data"]["input_tokens"] == 13
    assert exported["evidence"][-1]["data"]["output_tokens"] is None
    assert before == _hash(tmp_path / "response/session.sqlite3")


def test_metadata_without_http_status_does_not_invent_http_response(tmp_path):
    with create_session(tmp_path, "metadata", _manifest(), {}) as ledger:
        ledger.claim("cell-00")
        ledger.record("cell-00", "RESPONSE_OBSERVED", {
            "http_status": None, "input_tokens": None, "service_contract_valid": True})
        ledger.record("cell-00", "PARSE_RESULT", {
            "strict_json_valid": True, "catalog_valid": True,
            "proposal_activity": "SLEEP", "proposal_target": None})
        row = ledger.rows()[0]
        assert row["intent_registered"] is True
        assert row["http_response_observed"] is False
        assert row["strict_json_valid"] is True and row["catalog_valid"] is True
        assert row["input_tokens"] is None
        assert row["status"] == "UNKNOWN"


def test_committed_world_result_survives_missing_final_export(tmp_path):
    with create_session(tmp_path, "committed", _manifest(), {}) as ledger:
        request_id = ledger.claim("cell-00")
        ledger.record("cell-00", "CLIENT_CALL_STARTED", {"application_calls": 1})
        ledger.record("cell-00", "WORLD_RESULT_COMMITTED", {
            "status": "DECISION_ACCEPTED", "request_id": request_id,
            "provider_requests": 1, "http_status": 200,
            "strict_json_valid": True, "catalog_valid": True,
            "activity_completed": True, "invariants": "PASS",
            "before_state": {"minute": 0}, "after_state": {"minute": 360}})
    recovered = read_session(tmp_path / "committed")["rows"][0]
    assert recovered["status"] == "DECISION_ACCEPTED"
    assert recovered["activity_completed"] is True
    assert recovered["recovered_world_result"] is True
    assert recovered["provider_requests"] == 1
    assert recovered["missing_evidence"] == ["FINAL_ROW"]


def test_final_rows_cannot_overwrite_and_unclaimed_only_not_run(tmp_path):
    with create_session(tmp_path, "finished", _manifest(), {}) as ledger:
        with pytest.raises(LedgerError, match="UNCLAIMED_CELL_RESULT"):
            ledger.finish("cell-00", {"status": "DECISION_ACCEPTED"})
        ledger.finish("cell-00", {"status": "NOT_RUN", "stop_reason": "SESSION_FATAL"})
        with pytest.raises(LedgerError, match="CELL_ALREADY_FINISHED"):
            ledger.finish("cell-00", {"status": "NOT_RUN"})
        ledger.claim("cell-01")
        with pytest.raises(LedgerError, match="REQUEST_ID_MISMATCH"):
            ledger.finish("cell-01", {"status": "UNKNOWN", "request_id": "other"})
        with pytest.raises(LedgerError, match="CELL_ID_MISMATCH"):
            ledger.finish("cell-01", {"status": "UNKNOWN", "cell_id": "cell-00"})
        ledger.finish("cell-01", {"status": "UNKNOWN", "provider_requests": None})
        assert len(ledger.rows()) == 48
        assert ledger.rows()[0]["stop_reason"] == "SESSION_FATAL"


@pytest.mark.parametrize("field", ["raw_text", "prompt", "headers", "API_KEY",
                                    "reasoning_content", "exception_body"])
def test_raw_sensitive_fields_rejected_before_persistence(tmp_path, field):
    with create_session(tmp_path, "safety", _manifest(), {}) as ledger:
        ledger.claim("cell-00")
        with pytest.raises(ValueError, match="UNSAFE_AUDIT_FIELD"):
            ledger.record("cell-00", "FAILURE", {"nested": {field: "SENSITIVE_SENTINEL"}})
    assert b"SENSITIVE_SENTINEL" not in (tmp_path / "safety/session.sqlite3").read_bytes()


def test_manifest_duplicates_and_wrong_capacity_fail_before_reservation(tmp_path):
    manifest = _manifest()
    manifest["cells"][1]["cell_id"] = "cell-00"
    with pytest.raises(LedgerError, match="DUPLICATE_CELL_ID"):
        create_session(tmp_path, "duplicate", manifest, {})
    with pytest.raises(LedgerError, match="MANIFEST_REQUIRES_48_CELLS"):
        create_session(tmp_path, "small", {"cells": [{"cell_id": "one"}]}, {})
    assert list(tmp_path.iterdir()) == []


def test_readonly_export_neither_changes_ledger_nor_migrates_unknown_schema(tmp_path):
    with create_session(tmp_path, "readonly", _manifest(), {}):
        pass
    path = tmp_path / "readonly/session.sqlite3"
    before = _hash(path)
    assert read_session(path)["read_only"] is True
    assert _hash(path) == before
    with sqlite3.connect(path) as db:
        db.execute("UPDATE meta SET value=? WHERE key='schema_version'",
                   (json.dumps("future_schema"),))
    corrupted_hash = _hash(path)
    with pytest.raises(LedgerError, match="UNSUPPORTED_LEDGER_SCHEMA"):
        read_session(path)
    assert _hash(path) == corrupted_hash


def test_readonly_export_detects_cell_allocation_not_matching_frozen_manifest(tmp_path):
    with create_session(tmp_path, "allocation", _manifest(), {}):
        pass
    path = tmp_path / "allocation/session.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("UPDATE cells SET plan=? WHERE cell_id='cell-00'",
                   (json.dumps({"cell_id": "cell-00", "arm": "B_FEASIBLE"}),))
    before = _hash(path)
    with pytest.raises(LedgerError, match="ALLOCATION_EVIDENCE_MISMATCH"):
        read_session(path)
    assert before == _hash(path)


def test_world_commit_before_summary_is_recoverable_readonly_without_action_replay(tmp_path):
    source = tmp_path / "world.sqlite3"
    with ContinuityWorld(source) as world:
        seed_demo(world)
        before_state = project_state(world)
        assert world.act("committed-command", 1, "MOVE", "restaurant")["accepted"]
        state_after = world.store.snapshot()
        invariant = validate_world(world)
    before_hash = _hash(source)
    recovered = read_world(source)
    assert recovered["state"] == state_after
    assert recovered["state_hash"] == invariant["state_hash"]
    assert recovered["state"]["actors"][0]["location"] == "restaurant"
    assert recovered["commands"][0]["id"] == "committed-command"
    with open_readonly_world(source) as readonly:
        assert project_state(readonly)["location"] != before_state["location"]
        assert validate_world(readonly)["invariants"] == "PASS"
        with pytest.raises(sqlite3.OperationalError):
            readonly.store.db.execute("UPDATE meta SET value='123' WHERE key='minute'")
    assert _hash(source) == before_hash


def test_unknown_world_schema_is_not_silently_created_or_migrated(tmp_path):
    path = tmp_path / "empty.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE marker(value TEXT)")
    before = _hash(path)
    with pytest.raises(sqlite3.OperationalError):
        read_world(path)
    assert _hash(path) == before
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == [
            ("marker",)]


class _ProcessInterrupted(BaseException):
    """A process interruption must bypass the runner's handled failure path."""


@pytest.mark.parametrize("interruption", ["intent_registered", "response_observed",
                                          "activity_committed"])
def test_real_runner_readonly_export_at_three_durable_boundaries(
        tmp_path, monkeypatch, interruption):
    from social_sim.continuity.q6_2_panel import (
        ScriptedPanelClient, export_only, prepare_session, run_session,
    )
    from social_sim.continuity.store import StateStore
    from social_sim.provider_runtime import environment
    import social_sim.decision

    source = tmp_path / "registry" / interruption
    client = ScriptedPanelClient("both-legal")

    def interrupt(stage, _cell_id):
        if stage == interruption:
            raise _ProcessInterrupted

    with prepare_session(tmp_path / "registry", interruption, mode="offline") as ledger:
        with pytest.raises(_ProcessInterrupted):
            asyncio.run(run_session(ledger, mode="offline", client=client,
                                    fault_hook=interrupt, progress=None))
    before = {str(path.relative_to(source)): _hash(path)
              for path in source.rglob("*") if path.is_file()}

    def forbidden(*_args, **_kwargs):
        raise AssertionError("RECOVERY_MUST_NOT_BUILD_CLIENT_READ_CONFIG_OR_EXECUTE")

    monkeypatch.setattr(environment, "load_provider_config", forbidden)
    monkeypatch.setattr(social_sim.decision, "OpenAICompatibleDecisionClient", forbidden)
    monkeypatch.setattr(ContinuityWorld, "__init__", forbidden)
    monkeypatch.setattr(StateStore, "__init__", forbidden)
    for method in ("start", "advance", "act"):
        monkeypatch.setattr(ContinuityWorld, method, forbidden)
    output = tmp_path / "recoveries" / interruption
    summary = export_only(source, output)
    after = {str(path.relative_to(source)): _hash(path)
             for path in source.rglob("*") if path.is_file()}
    assert before == after
    assert summary["counts"]["planned"] == 48
    assert summary["counts"]["not_run"] == 47
    recovery = json.loads((output / "recovery.json").read_text())
    rows = [json.loads(line) for line in (output / "cells.jsonl").read_text().splitlines()]
    row = rows[0]
    assert recovery["source_modified"] is False
    assert recovery["automatic_resume"] is False
    assert recovery["new_provider_requests"] == 0
    assert row["intent_registered"] is True
    if interruption == "intent_registered":
        assert client.call_count == 0
        assert row["status"] == "UNKNOWN"
        assert row["client_call_attempted"] is None
        assert row["provider_requests"] is None
        assert summary["counts"]["intent_send_unknown"] == 1
        assert row.get("activity_completed") is None
    elif interruption == "response_observed":
        assert client.call_count == 1
        assert row["status"] == "UNKNOWN"
        assert row["http_status"] == 200
        assert row["http_response_observed"] is True
        assert row["service_contract_valid"] is True
        assert row.get("strict_json_valid") is None
        assert summary["counts"]["http_response_observed"] == 1
        assert row.get("activity_completed") is None
    else:
        assert client.call_count == 1
        assert row["status"] == "DECISION_ACCEPTED"
        assert row["activity_completed"] is True
        assert row["commitment_status"] == "COMPLETED"
        assert row["rule_checked"] is True
        assert row["invariants_valid"] is True
        assert row["strict_json_valid"] is True and row["catalog_valid"] is True
        assert row["after_state"]["minute"] > 0
        assert summary["counts"]["activity_completed"] == 1
    assert all(other["status"] == "NOT_RUN" for other in rows[1:])
