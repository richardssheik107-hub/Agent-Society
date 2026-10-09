"""Versioned timeout scheduling, using only local fakes and no real waits."""
from __future__ import annotations

import asyncio
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

import social_sim.continuity.q6_2_panel as panel
from social_sim.continuity.engine import ContinuityWorld
from social_sim.continuity.models import digest
from social_sim.continuity.q6_2_panel_fixtures import load_protocol
from social_sim.continuity.q6_2_panel_ledger import LedgerError, read_session
from social_sim.decision.client import DecisionClientError, DecisionResponseMetadata

LEGAL = '{"activity":"LEISURE","target":null}'
REJECTED = '{"activity":"PLAY","target":"food_meal"}'
MEAL = '{"activity":"MEAL","target":"food_meal"}'
PRIVATE_ERROR = "PRIVATE_TIMEOUT_ERROR_SENTINEL"


class SequenceClient:
    """Each item is one attempted cell, not a retry of an earlier cell."""

    def __init__(self, steps):
        self.steps = list(steps)
        self.call_count = 0
        self.last_metadata = None
        self.active = False
        self.ledger = None
        self.order = []

    async def complete(self, _system, _user):
        assert self.active is False, "provider calls must be serial and settled"
        if self.ledger is not None and self.call_count:
            prior = self.ledger.rows()[self.call_count - 1]
            assert prior.get("timeout_streak_after") is not None
            assert prior.get("continue_or_stop_reason") is not None
            assert read_session(self.ledger.dir)["cells"][self.call_count - 1]["row"] is not None
        self.active = True
        self.call_count += 1
        self.order.append(self.call_count)
        try:
            step = self.steps[self.call_count - 1] if self.call_count <= len(self.steps) else LEGAL
            if isinstance(step, BaseException):
                raise step
            self.last_metadata = SimpleNamespace(http_status=200, provider_model="SAFE_FAKE",
                                                  input_tokens=7, output_tokens=3,
                                                  reasoning_tokens=None)
            return SimpleNamespace(raw_text=step)
        finally:
            self.active = False


def run(tmp_path, client, *, version="v2", fault_hook=None):
    with panel.prepare_session(tmp_path, "synthetic", mode="offline",
                               protocol=load_protocol(version=version)) as ledger:
        client.ledger = ledger
        summary = asyncio.run(panel.run_session(ledger, mode="offline", client=client,
                                               fault_hook=fault_hook, progress=None))
        return summary, ledger.rows(), ledger.dir, ledger.claimed_count


def load_cli():
    path = Path(__file__).resolve().parents[1] / "scripts/run_q6_2_fixed_state_panel.py"
    spec = importlib.util.spec_from_file_location("panel_timeout_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_old_cli_explicit_protocol_selection_defaults_to_v1():
    cli = load_cli()
    args = cli.parser().parse_args(["--session-id", "default-dry"])
    assert args.protocol == "v1"
    assert "--protocol" in cli.parser().format_help()
    assert cli.parser().parse_args(["--session-id", "v2-dry", "--protocol", "v2"]).protocol == "v2"
    with pytest.raises(SystemExit):
        cli.parser().parse_args(["--session-id", "other", "--protocol", "v3"])


def test_cli_v2_is_forwarded_to_execution_without_provider_config(monkeypatch, capsys):
    cli = load_cli()
    selected = []
    async def execute(args, protocol):
        selected.append(protocol["protocol_version"])
        assert args.mode == "dry-run"
        return {"schema_version": "Q6_2_FIXED_PANEL_METRICS_V1", "mode": "DRY_RUN",
                "session_status": "NOT_RUN", "counts": {"not_run": 48}, "real_provider_requests": 0}
    monkeypatch.setattr(cli, "_execute", execute)
    assert cli.main(["--session-id", "v2-dry", "--protocol", "v2"]) == 0
    assert selected == ["q62_fixed_state_panel_v2"]
    assert "REAL_PROVIDER_REQUESTS_THIS_TASK=0" in capsys.readouterr().out


def test_prepare_real_session_persists_safe_authorization_without_loading_provider(tmp_path, monkeypatch):
    import social_sim.decision as decision_package
    import social_sim.decision.client as decision_client
    import social_sim.provider_runtime.environment as environment
    def forbidden(*_args, **_kwargs):
        pytest.fail("preparation must not read provider config or construct a provider client")
    monkeypatch.setattr(environment, "load_provider_config", forbidden)
    monkeypatch.setattr(decision_package, "OpenAICompatibleDecisionClient", forbidden)
    monkeypatch.setattr(decision_client, "OpenAICompatibleDecisionClient", forbidden)
    protocol = load_protocol(version="v2")
    authorization = {"source": "OFFLINE_AUTHORIZATION_RECORD_TEST", "session_id": "safe-real-preparation",
        "protocol_version": protocol["protocol_version"], "max_client_attempts": 48,
        "additional_real_probes": 0, "retry": False, "resume": False,
        "execution_commit": "0" * 40, "protocol_hash": digest(protocol)}
    with panel.prepare_session(tmp_path, authorization["session_id"], mode="real",
                               protocol=protocol, authorization=authorization) as ledger:
        saved = read_session(ledger.dir)
        assert saved["metadata"]["session_authorization_record"] == authorization
        assert saved["metadata"]["mode"] == "REAL_PROVIDER"
        assert saved["metadata"]["real_authorized"] is True
        assert ledger.claimed_count == 0
        assert not saved["evidence"] and all(row["status"] == "NOT_RUN" for row in ledger.rows())


def test_v1_single_timeout_remains_fatal(tmp_path):
    client = SequenceClient([TimeoutError(PRIVATE_ERROR), LEGAL])
    summary, rows, _directory, claims = run(tmp_path, client, version="v1")
    assert client.call_count == claims == 1
    assert rows[0]["status"] == "PROVIDER_TIMEOUT"
    assert summary["session_status"] == "PROVIDER_TIMEOUT"
    assert summary["status_counts"]["NOT_RUN"] == 47
    assert all(row["stop_reason"] == "PROVIDER_TIMEOUT" for row in rows[1:])


@pytest.mark.parametrize("error", [TimeoutError(PRIVATE_ERROR), httpx.ReadTimeout(PRIVATE_ERROR)])
def test_v2_single_safely_settled_timeout_continues_without_resending(tmp_path, error):
    client = SequenceClient([error])
    summary, rows, directory, claims = run(tmp_path, client)
    assert client.call_count == claims == 48
    assert client.order == list(range(1, 49))
    assert rows[0]["status"] == "PROVIDER_TIMEOUT"
    assert rows[0]["timeout_streak_before"] == 0 and rows[0]["timeout_streak_after"] == 1
    assert rows[0]["local_call_settled"] is True and rows[0]["timeout_locally_safe"] is True
    assert rows[1]["timeout_streak_before"] == 1 and rows[1]["timeout_streak_after"] == 0
    assert summary["session_status"] == "PANEL_COMPLETED"
    assert summary["counts"]["activity_completed"] == 47
    assert summary["counts"]["not_run"] == 0
    assert len({row["request_id"] for row in rows}) == 48
    evidence = read_session(directory)["evidence"]
    assert sum(event["stage"] == "CLIENT_CALL_STARTED" and event["cell_id"] == "c001"
               for event in evidence) == 1
    for path in directory.rglob("*"):
        if path.is_file():
            assert PRIVATE_ERROR.encode() not in path.read_bytes()


def test_v2_consecutive_timeout_crosses_ab_pair_and_stops_on_exactly_two_calls(tmp_path):
    client = SequenceClient([TimeoutError(), httpx.ReadTimeout("local fake")])
    summary, rows, _directory, claims = run(tmp_path, client)
    assert client.call_count == claims == 2
    assert rows[0]["pair_id"] == rows[1]["pair_id"]
    assert rows[0]["condition"] != rows[1]["condition"]
    assert [row["status"] for row in rows[:2]] == ["PROVIDER_TIMEOUT", "PROVIDER_TIMEOUT"]
    assert [(row["timeout_streak_before"], row["timeout_streak_after"]) for row in rows[:2]] == [(0, 1), (1, 2)]
    assert summary["session_status"] == "CONSECUTIVE_TIMEOUT_LIMIT"
    assert summary["status_counts"]["PROVIDER_TIMEOUT"] == 2
    assert summary["counts"]["not_run"] == 46
    assert all(row["status"] == "NOT_RUN" and row["stop_reason"] == "CONSECUTIVE_TIMEOUT_LIMIT"
               for row in rows[2:])


@pytest.mark.parametrize("middle,expected", [(LEGAL, "DECISION_ACCEPTED"),
                                               (REJECTED, "RULE_REJECTED"),
                                               (MEAL, "COMMITMENT_FAILED")])
def test_valid_result_resets_streak_including_rejection_and_known_failure(tmp_path, middle, expected):
    client = SequenceClient([TimeoutError(), middle, TimeoutError()])
    summary, rows, _directory, claims = run(tmp_path, client)
    assert client.call_count == claims == 48
    assert rows[1]["status"] == expected
    assert rows[1]["strict_json_valid"] is True and rows[1]["catalog_valid"] is True
    assert [(row["timeout_streak_before"], row["timeout_streak_after"]) for row in rows[:4]] == [
        (0, 1), (1, 0), (0, 1), (1, 0)]
    assert summary["session_status"] == "PANEL_COMPLETED"
    assert summary["status_counts"]["PROVIDER_TIMEOUT"] == 2
    if expected == "COMMITMENT_FAILED":
        assert rows[1]["execution_failure_reason"] == "INSUFFICIENT_FUNDS"
        assert rows[1]["invariants_valid"] is True


def test_timeout_counter_is_not_reset_by_scene_or_pair_boundary(tmp_path):
    client = SequenceClient([LEGAL, TimeoutError(), TimeoutError()])
    summary, rows, _directory, claims = run(tmp_path, client)
    assert client.call_count == claims == 3
    assert rows[1]["scenario_id"] != rows[2]["scenario_id"]
    assert rows[1]["pair_id"] != rows[2]["pair_id"]
    assert rows[2]["timeout_streak_before"] == 1 and rows[2]["timeout_streak_after"] == 2
    assert summary["session_status"] == "CONSECUTIVE_TIMEOUT_LIMIT"


@pytest.mark.parametrize("http_status", [401, 403, 408, 429, 500, 503])
def test_http_errors_even_408_stop_and_are_not_timeout_continuations(tmp_path, http_status):
    class HttpClient(SequenceClient):
        async def complete(self, system, user):
            if self.call_count == 1:
                self.call_count += 1
                self.last_metadata = DecisionResponseMetadata(http_status=http_status)
                raise DecisionClientError(PRIVATE_ERROR)
            return await super().complete(system, user)
    client = HttpClient([TimeoutError(), LEGAL])
    summary, rows, _directory, claims = run(tmp_path, client)
    assert client.call_count == claims == 2
    assert rows[0]["status"] == "PROVIDER_TIMEOUT" and rows[1]["status"] == "HTTP_ERROR"
    assert rows[1]["http_status"] == http_status
    assert summary["session_status"] == "HTTP_ERROR"
    assert summary["status_counts"]["PROVIDER_TIMEOUT"] == 1
    assert summary["counts"]["not_run"] == 46


@pytest.mark.parametrize("error,expected", [(httpx.ConnectError(PRIVATE_ERROR), "TRANSPORT_ERROR"),
    (asyncio.CancelledError(PRIVATE_ERROR), "REQUEST_CANCELLED"),
    (ImportError(PRIVATE_ERROR), "ARCHITECTURE_ERROR"),
    ("not JSON", "INVALID_MODEL_OUTPUT"),
    ('{"activity":"PLAY","target":"unknown_target"}', "OUTSIDE_CATALOG")])
def test_non_timeout_fatal_after_timeout_still_stops_immediately(tmp_path, error, expected):
    client = SequenceClient([TimeoutError(), error, LEGAL])
    summary, rows, _directory, claims = run(tmp_path, client)
    assert client.call_count == claims == 2
    assert rows[1]["status"] == expected
    assert summary["session_status"] == expected
    assert summary["counts"]["not_run"] == 46


def test_timeout_does_not_inherit_previous_success_receipt(tmp_path):
    client = SequenceClient([LEGAL, TimeoutError(), TimeoutError()])
    summary, rows, _directory, _claims = run(tmp_path, client)
    assert rows[0]["provider_model"] == "SAFE_FAKE" and rows[0]["input_tokens"] == 7
    for row in rows[1:3]:
        assert row["http_status"] is None and row["provider_model"] is None
        assert row["input_tokens"] is None and row["output_tokens"] is None
        assert row["reasoning_tokens"] is None and row["http_response_observed"] is None
    assert summary["counts"]["http_response_observed"] == 1
    assert summary["costs"]["input_tokens"]["known_subtotal"] == 7
    assert summary["costs"]["input_tokens"]["missing_rows"] == 2


def test_v2_unsafe_local_timeout_cannot_start_next_cell(tmp_path, monkeypatch):
    original = panel._CellClient
    class UnsettledClient(original):
        async def complete(self, system, user):
            try:
                return await super().complete(system, user)
            finally:
                # Fault injection only: no real leaking task or timed wait.
                self.local_call_settled = False
    monkeypatch.setattr(panel, "_CellClient", UnsettledClient)
    client = SequenceClient([TimeoutError(), LEGAL])
    summary, rows, _directory, claims = run(tmp_path, client)
    assert client.call_count == claims == 1
    assert rows[0]["local_call_settled"] is False
    assert rows[0]["timeout_locally_safe"] is False
    assert summary["counts"]["not_run"] == 47
    assert summary["session_status"] not in {"PANEL_COMPLETED", "RUNNING", "CONSECUTIVE_TIMEOUT_LIMIT"}


def test_timeout_with_new_unsettled_local_task_stops_then_test_cleans_it(tmp_path):
    class BackgroundFaultClient(SequenceClient):
        pending = None
        async def complete(self, system, user):
            # Synthetic architecture fault: hold a reference and clean it below.
            self.pending = asyncio.create_task(asyncio.Event().wait())
            await asyncio.sleep(0)
            return await super().complete(system, user)
    async def exercise():
        client = BackgroundFaultClient([TimeoutError(), LEGAL])
        try:
            with panel.prepare_session(tmp_path, "background-fault", mode="offline",
                                       protocol=load_protocol(version="v2")) as ledger:
                client.ledger = ledger
                summary = await panel.run_session(ledger, mode="offline", client=client, progress=None)
                return summary, ledger.rows(), client.call_count
        finally:
            if client.pending is not None:
                client.pending.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await client.pending
                assert client.pending.done()
    summary, rows, calls = asyncio.run(exercise())
    assert calls == 1 and rows[0]["local_call_settled"] is False
    assert rows[0]["timeout_locally_safe"] is False
    assert summary["counts"]["not_run"] == 47


def test_client_call_that_suppresses_cancellation_stops_before_next_call(tmp_path, monkeypatch):
    original_wait = asyncio.wait
    timeouts = []
    async def immediate_wait(tasks, *, timeout=None, **kwargs):
        timeouts.append(timeout)
        return await original_wait(tasks, timeout=0.001, **kwargs)
    monkeypatch.setattr(asyncio, "wait", immediate_wait)
    class StubbornClient(SequenceClient):
        task = None
        async def complete(self, _system, _user):
            self.call_count += 1
            self.task = asyncio.current_task()
            self.active = True
            try:
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    # Simulate a defective coroutine once; test cancels it below.
                    await asyncio.Event().wait()
            finally:
                self.active = False
    async def exercise():
        client = StubbornClient([])
        try:
            with panel.prepare_session(tmp_path, "unsettled-call", mode="offline",
                                       protocol=load_protocol(version="v2")) as ledger:
                client.ledger = ledger
                summary = await panel.run_session(ledger, mode="offline", client=client, progress=None)
                assert client.task is not None and not client.task.done()
                return summary, ledger.rows(), client.call_count
        finally:
            if client.task is not None and not client.task.done():
                client.task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await client.task
                assert client.task.done() and client.active is False
    summary, rows, calls = asyncio.run(exercise())
    assert timeouts[:2] == [60, 5]
    assert calls == 1 and rows[0]["status"] == "PROVIDER_TIMEOUT"
    assert rows[0]["local_call_settled"] is False and rows[0]["timeout_locally_safe"] is False
    assert summary["counts"]["not_run"] == 47


def test_late_reply_after_cancel_is_discarded_not_committed(tmp_path, monkeypatch):
    original_wait = asyncio.wait
    waits = 0
    async def only_first_immediate(tasks, *, timeout=None, **kwargs):
        nonlocal waits
        waits += 1
        return await original_wait(tasks, timeout=0.001 if waits == 1 else timeout, **kwargs)
    monkeypatch.setattr(asyncio, "wait", only_first_immediate)
    class LateReplyClient(SequenceClient):
        async def complete(self, system, user):
            if self.call_count == 0:
                self.call_count += 1
                self.active = True
                try:
                    try:
                        await asyncio.Event().wait()
                    except asyncio.CancelledError:
                        return SimpleNamespace(raw_text=LEGAL)
                finally:
                    self.active = False
            return await super().complete(system, user)
    client = LateReplyClient([])
    summary, rows, source, claims = run(tmp_path, client)
    assert client.call_count == claims == 48
    assert rows[0]["status"] == "PROVIDER_TIMEOUT" and rows[0]["timeout_locally_safe"] is True
    assert rows[0]["strict_json_valid"] is None and rows[0]["proposal_activity"] is None
    assert rows[0]["after_state"] == rows[0]["before_state"]
    with ContinuityWorld(source / "cells/c001/world.sqlite3") as world:
        assert world.store.db.execute("SELECT 1 FROM commands WHERE id=?", (rows[0]["request_id"],)).fetchone() is None
    assert summary["counts"]["activity_completed"] == summary["counts"]["valid_proposals"] == 47


def test_timeout_with_unexplained_domain_commit_cannot_continue(tmp_path):
    class SideEffectClient(SequenceClient):
        async def complete(self, system, user):
            if self.call_count == 0:
                with ContinuityWorld(self.ledger.dir / "cells/c001/world.sqlite3") as world:
                    assert world.start("unexplained", 1, "LEISURE")["accepted"]
                    panel.execute_activity(world, "unexplained", 96)
            return await super().complete(system, user)
    client = SideEffectClient([TimeoutError(), LEGAL])
    summary, rows, _directory, claims = run(tmp_path, client)
    assert client.call_count == claims == 1
    assert rows[0]["timeout_locally_safe"] is False
    assert rows[0]["simulation_minutes"] > 0
    assert summary["counts"]["not_run"] == 47


def test_missing_timeout_ledger_evidence_cannot_continue(tmp_path, monkeypatch):
    original = panel.timeout_safety
    def evidence_missing(world, request_id, before, proxy, evidence):
        evidence.clear()
        return original(world, request_id, before, proxy, evidence)
    monkeypatch.setattr(panel, "timeout_safety", evidence_missing)
    client = SequenceClient([TimeoutError(), LEGAL])
    summary, rows, _directory, claims = run(tmp_path, client)
    assert client.call_count == claims == 1
    assert rows[0]["timeout_locally_safe"] is False
    assert summary["counts"]["not_run"] == 47


def test_settled_cancellation_is_complete_before_next_attempt(tmp_path, monkeypatch):
    original_wait_for = asyncio.wait_for
    waits = 0
    class CancelledFirstClient(SequenceClient):
        async def complete(self, system, user):
            if self.call_count == 0:
                self.call_count += 1
                self.active = True
                try:
                    await asyncio.Event().wait()
                finally:
                    self.active = False
            return await super().complete(system, user)
    async def controlled_wait_for(awaitable, timeout):
        nonlocal waits
        waits += 1
        if waits != 1:
            return await original_wait_for(awaitable, timeout=timeout)
        task = asyncio.ensure_future(awaitable)
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert task.done()
        raise TimeoutError()
    monkeypatch.setattr(asyncio, "wait_for", controlled_wait_for)
    client = CancelledFirstClient([])
    summary, rows, _directory, claims = run(tmp_path, client)
    assert client.call_count == claims == 48
    assert rows[0]["status"] == "PROVIDER_TIMEOUT" and rows[0]["local_call_settled"] is True
    assert summary["session_status"] == "PANEL_COMPLETED"
    assert client.active is False


def test_timeout_claims_are_permanent_and_full_48_budget_cannot_reopen(tmp_path):
    client = SequenceClient([TimeoutError()])
    with panel.prepare_session(tmp_path, "budget", mode="offline", protocol=load_protocol(version="v2")) as ledger:
        client.ledger = ledger
        summary = asyncio.run(panel.run_session(ledger, mode="offline", client=client, progress=None))
        assert client.call_count == ledger.claimed_count == 48
        assert summary["status_counts"]["PROVIDER_TIMEOUT"] == 1
        for cid in ("c001", "c048"):
            with pytest.raises(LedgerError):
                ledger.claim(cid)
        second = SequenceClient([])
        with pytest.raises(ValueError, match="NO_RESUME_OR_RERUN"):
            asyncio.run(panel.run_session(ledger, mode="offline", client=second, progress=None))
        assert second.call_count == 0 and ledger.claimed_count == 48
    with pytest.raises(FileExistsError):
        panel.prepare_session(tmp_path, "budget", mode="offline", protocol=load_protocol(version="v2"))


def test_read_only_recovery_preserves_timeout_streak_and_planned_denominators(tmp_path):
    client = SequenceClient([TimeoutError(), TimeoutError()])
    summary, rows, source, _claims = run(tmp_path / "registry", client)
    before = {str(path): path.read_bytes() for path in source.rglob("*") if path.is_file()}
    recovered = panel.export_only(source, tmp_path / "recovered")
    restored = [json.loads(line) for line in (tmp_path / "recovered/cells.jsonl").read_text().splitlines()]
    assert recovered["counts"]["planned"] == 48 and recovered["pair_counts"]["planned"] == 24
    assert recovered["status_counts"]["PROVIDER_TIMEOUT"] == 2
    assert recovered["counts"]["not_run"] == summary["counts"]["not_run"] == 46
    for original, exported in zip(rows[:2], restored[:2], strict=True):
        for field in ("timeout_streak_before", "timeout_streak_after", "local_call_settled",
                      "timeout_locally_safe", "continue_or_stop_reason"):
            assert exported[field] == original[field]
    assert all(row["stop_reason"] == "CONSECUTIVE_TIMEOUT_LIMIT" for row in restored[2:])
    assert before == {str(path): path.read_bytes() for path in source.rglob("*") if path.is_file()}


def test_intent_only_recovery_is_unknown_not_safe_timeout(tmp_path):
    with panel.prepare_session(tmp_path / "registry", "interrupted", mode="offline",
                               protocol=load_protocol(version="v2")) as ledger:
        ledger.claim("c001")
        ledger.record("c001", "REQUEST_STARTED", {"request_id": ledger.rows()[0]["request_id"]})
        source = ledger.dir
    before = {str(path): path.read_bytes() for path in source.rglob("*") if path.is_file()}
    recovered = panel.export_only(source, tmp_path / "recovered")
    row = json.loads((tmp_path / "recovered/cells.jsonl").read_text().splitlines()[0])
    assert row["status"] == "UNKNOWN"
    assert row.get("local_call_settled") is not True and row.get("timeout_locally_safe") is not True
    assert row["client_call_attempted"] is None and row["provider_requests"] is None
    assert recovered["counts"]["unknown"] == 1 and recovered["counts"]["not_run"] == 47
    assert recovered["counts"]["valid_proposals"] == 0
    assert recovered["ratios"]["rule_rejection_rate"]["value"] is None
    assert before == {str(path): path.read_bytes() for path in source.rglob("*") if path.is_file()}


def test_last_planned_cell_http_failure_recovery_retains_fatal_not_completed(tmp_path):
    class LastHttpClient(SequenceClient):
        async def complete(self, system, user):
            if self.call_count == 47:
                self.call_count += 1
                self.last_metadata = DecisionResponseMetadata(http_status=429)
                raise DecisionClientError(PRIVATE_ERROR)
            return await super().complete(system, user)
    client = LastHttpClient([])
    summary, rows, source, claims = run(tmp_path / "registry", client)
    assert client.call_count == claims == 48
    assert summary["session_status"] == "HTTP_ERROR" and rows[-1]["status"] == "HTTP_ERROR"
    assert summary["counts"]["not_run"] == 0 and summary["counts"]["valid_proposals"] == 47
    before = {str(path): path.read_bytes() for path in source.rglob("*") if path.is_file()}
    recovered = panel.export_only(source, tmp_path / "recovered")
    assert recovered["session_status"] == "STOPPED_READ_ONLY_RECOVERY"
    assert recovered["session_termination"] == "HTTP_ERROR"
    assert recovered["counts"]["not_run"] == 0 and recovered["status_counts"]["HTTP_ERROR"] == 1
    assert json.loads((tmp_path / "recovered/recovery.json").read_text())["new_provider_requests"] == 0
    assert client.call_count == 48
    assert before == {str(path): path.read_bytes() for path in source.rglob("*") if path.is_file()}


def test_timeout_with_http408_receipt_missing_final_row_recovers_as_http_error(tmp_path):
    class TimeoutHttpClient(SequenceClient):
        async def complete(self, _system, _user):
            self.call_count += 1
            self.last_metadata = DecisionResponseMetadata(http_status=408)
            raise httpx.ReadTimeout(PRIVATE_ERROR)
    def stop_before_final_row(stage, _cid):
        if stage == "world_result_committed":
            raise SystemExit("synthetic process interruption")
    client = TimeoutHttpClient([])
    with panel.prepare_session(tmp_path / "registry", "http408-interrupted", mode="offline",
                               protocol=load_protocol(version="v2")) as ledger:
        client.ledger = ledger
        with pytest.raises(SystemExit):
            asyncio.run(panel.run_session(ledger, mode="offline", client=client,
                                          fault_hook=stop_before_final_row, progress=None))
        saved = read_session(ledger.dir)
        assert saved["cells"][0]["row"] is None and saved["rows"][0]["status"] == "HTTP_ERROR"
        assert client.call_count == ledger.claimed_count == 1
        source = ledger.dir
    before = {str(path): path.read_bytes() for path in source.rglob("*") if path.is_file()}
    recovered = panel.export_only(source, tmp_path / "recovered")
    row = json.loads((tmp_path / "recovered/cells.jsonl").read_text().splitlines()[0])
    assert row["status"] == "HTTP_ERROR" and row["http_status"] == 408
    assert recovered["session_termination"] == "HTTP_ERROR"
    assert recovered["status_counts"].get("PROVIDER_TIMEOUT", 0) == 0
    assert recovered["counts"]["not_run"] == 47
    assert json.loads((tmp_path / "recovered/recovery.json").read_text())["new_provider_requests"] == 0
    assert client.call_count == 1
    assert before == {str(path): path.read_bytes() for path in source.rglob("*") if path.is_file()}


@pytest.mark.parametrize("failure", [False, True])
def test_client_cleanup_records_safe_type_without_exception_body(failure):
    cli = load_cli()
    class Client:
        calls = 0
        async def aclose(self):
            self.calls += 1
            if failure:
                raise RuntimeError(PRIVATE_ERROR)
    client = Client()
    result = asyncio.run(cli.close_client_safely(client))
    assert client.calls == 1
    assert result["cleanup_outcome"] == ("FAILED" if failure else "CLOSED")
    assert result["cleanup_exception_type"] == ("RuntimeError" if failure else None)
    assert PRIVATE_ERROR not in json.dumps(result)


def test_cleanup_synchronous_close_exception_is_safe_metadata_not_primary_failure():
    cli = load_cli()
    class Client:
        def aclose(self):
            raise RuntimeError(PRIVATE_ERROR)
    result = asyncio.run(cli.close_client_safely(Client()))
    assert result["cleanup_outcome"] == "FAILED"
    assert result["cleanup_exception_type"] == "RuntimeError"
    assert PRIVATE_ERROR not in json.dumps(result)


@pytest.mark.parametrize("close_result,exception_type", [("success", None),
                                                         ("exception", "RuntimeError"),
                                                         ("timeout", "TimeoutError")])
def test_closed_client_with_pending_call_is_not_locally_settled(monkeypatch, close_result, exception_type):
    cli = load_cli()
    original_wait = asyncio.wait
    async def immediate_wait(tasks, *, timeout=None, **kwargs):
        return await original_wait(tasks, timeout=0.001, **kwargs)
    monkeypatch.setattr(asyncio, "wait", immediate_wait)
    class Client:
        async def aclose(self):
            if close_result == "exception":
                raise RuntimeError(PRIVATE_ERROR)
            if close_result == "timeout":
                await asyncio.Event().wait()
            return None
    async def exercise():
        client = Client()
        pending = asyncio.create_task(asyncio.Event().wait())
        client._q62_pending_tasks = (pending,)
        try:
            result = await cli.close_client_safely(client)
            assert not pending.done()
            return result
        finally:
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
    result = asyncio.run(exercise())
    assert result["cleanup_outcome"] == "NOT_LOCALLY_SETTLED"
    assert result["cleanup_local_settled"] is False and result["cleanup_exception_type"] == exception_type
    assert PRIVATE_ERROR not in json.dumps(result)


def test_execute_v2_process_exits_without_unbounded_gather_on_stubborn_task():
    cli_path = Path(__file__).resolve().parents[1] / "scripts/run_q6_2_fixed_state_panel.py"
    script = """
import asyncio
import importlib.util
import sys

spec = importlib.util.spec_from_file_location('panel_timeout_subprocess', sys.argv[1])
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)
held_tasks = []

async def stubborn():
    while True:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            continue

async def finished_session():
    held_tasks.append(asyncio.create_task(stubborn()))
    await asyncio.sleep(0)
    return {'session_status': 'TIMEOUT_NOT_LOCALLY_SETTLED'}

result = cli.execute_v2(finished_session())
assert result['session_status'] == 'TIMEOUT_NOT_LOCALLY_SETTLED'
print('STOPPED_WITHOUT_NEW_REQUEST_OR_UNBOUNDED_GATHER')
"""
    completed = subprocess.run([sys.executable, "-c", script, str(cli_path)],
                               capture_output=True, text=True, check=False, timeout=5)
    assert completed.returncode == 0
    assert "LOCAL_SHUTDOWN_UNSETTLED_TASKS=1" in completed.stdout
    assert "STOPPED_WITHOUT_NEW_REQUEST_OR_UNBOUNDED_GATHER" in completed.stdout
    assert completed.stderr == ""


def test_cleanup_timeout_uses_existing_five_second_cap_without_waiting_it(monkeypatch):
    cli = load_cli()
    original_wait = asyncio.wait
    timeouts = []
    async def immediate_wait(tasks, *, timeout=None, **kwargs):
        timeouts.append(timeout)
        return await original_wait(tasks, timeout=0.001, **kwargs)
    monkeypatch.setattr(asyncio, "wait", immediate_wait)
    class Client:
        async def aclose(self):
            await asyncio.Event().wait()
    result = asyncio.run(cli.close_client_safely(Client()))
    assert timeouts[0] == 5
    assert result["cleanup_outcome"] == "FAILED"
    assert result["cleanup_exception_type"] == "TimeoutError"


def test_cleanup_cancellation_not_settled_is_explicit_and_test_cleans_task(monkeypatch):
    cli = load_cli()
    original_wait = asyncio.wait
    async def immediate_wait(tasks, *, timeout=None, **kwargs):
        return await original_wait(tasks, timeout=0.001, **kwargs)
    monkeypatch.setattr(asyncio, "wait", immediate_wait)
    class Client:
        task = None
        async def aclose(self):
            self.task = asyncio.current_task()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                # Only the synthetic fault suppresses one cancellation.
                await asyncio.Event().wait()
    async def exercise():
        client = Client()
        try:
            return await cli.close_client_safely(client)
        finally:
            if client.task is not None and not client.task.done():
                client.task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await client.task
                assert client.task.done()
    result = asyncio.run(exercise())
    assert result["cleanup_outcome"] == "NOT_LOCALLY_SETTLED"
    assert result["cleanup_exception_type"] == "TimeoutError"


def test_cleanup_failure_cannot_overwrite_primary_session_error_or_send_again(tmp_path):
    cli = load_cli()
    client = SequenceClient([TimeoutError(), TimeoutError()])
    with panel.prepare_session(tmp_path, "cleanup-primary", mode="offline",
                               protocol=load_protocol(version="v2")) as ledger:
        client.ledger = ledger
        summary = asyncio.run(panel.run_session(ledger, mode="offline", client=client, progress=None))
        cleanup = {"cleanup_outcome": "FAILED", "cleanup_exception_type": "RuntimeError"}
        final = cli.append_cleanup(ledger, summary, cleanup)
        assert final["session_status"] == summary["session_status"] == "CONSECUTIVE_TIMEOUT_LIMIT"
        saved = json.loads((ledger.dir / "summary.json").read_text())
        assert saved["session_status"] == "CONSECUTIVE_TIMEOUT_LIMIT"
        assert json.loads((ledger.dir / "cleanup.json").read_text()) == cleanup
        assert saved["status_counts"]["PROVIDER_TIMEOUT"] == 2
        assert saved["counts"]["not_run"] == 46
        assert client.call_count == ledger.claimed_count == 2
        assert saved["cleanup"] == {"outcome": "FAILED", "exception_type": "RuntimeError",
                                    "does_not_replace_primary_termination": True}
        for path in ledger.dir.rglob("*"):
            if path.is_file():
                assert PRIVATE_ERROR.encode() not in path.read_bytes()
