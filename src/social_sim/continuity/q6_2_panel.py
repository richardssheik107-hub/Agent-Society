"""Independent fixed-state panel; scheduling evidence is not domain truth."""
from __future__ import annotations

import asyncio
import hashlib
import importlib.metadata
import json
import time
from pathlib import Path
from types import SimpleNamespace

from social_sim.provider_runtime.environment import code_fingerprint, repository_info
from social_sim.provider_runtime.safety import atom, counter, exception_type, metadata, write_json

from .action_projection import project_actions, projected_prompt, proposal_in_feasible_set
from .decision import ActivityDecisionRunner
from .engine import ContinuityWorld
from .models import canonical_json, digest
from .q6_1 import environment_record, project_state
from .q6_2_panel_fixtures import (
    allocate_cells, build_world, freeze_scenarios, load_protocol, validate_protocol,
)
from .q6_2_panel_ledger import LedgerError, create_session, open_readonly_world, read_session
from .q6_2_panel_reporting import paired_comparison, render_report, summarize
from .validation import validate_world

MODES = {"dry-run": "DRY_RUN", "offline": "OFFLINE_SYNTHETIC", "real": "REAL_PROVIDER"}
KNOWN_COMMITMENT_FAILURES = frozenset({"OUT_OF_STOCK", "INSUFFICIENT_FUNDS", "OBJECT_UNAVAILABLE", "ITEM_NOT_OWNED"})


class PanelStop(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _json(path: Path, data: object) -> None:
    # New session or new recovery destination only. No historical files are touched.
    write_json(path, data)


def execution_fingerprint(root: Path) -> str:
    return digest({"sources": code_fingerprint(root), "cli": hashlib.sha256(
        (root / "scripts/run_q6_2_fixed_state_panel.py").read_bytes()).hexdigest()})


def _audit(world: ContinuityWorld, condition: str, max_chars: int) -> dict:
    validate_world(world)
    if world.store.commitment(1):
        raise ValueError("BLOCKING_COMMITMENT")
    projection = project_actions(world)
    if not projection["executable_options"]:
        raise ValueError("NO_EXECUTABLE_OPTIONS")
    system, user = projected_prompt(world, mode=condition, max_chars=max_chars)
    return {"state_hash": digest(world.store.snapshot()),
            "observation_hash": projection["observation_digest"],
            "object_candidates": json.loads(user)["observation"]["objects"],
            "candidate_hash": projection["candidate_digest"],
            "candidate_count": projection["candidate_count"],
            "prompt_hash": digest({"system": system, "user": user}), "prompt_chars": len(system) + len(user)}


def _matches_frozen(audit: dict, scenario: dict, condition: str) -> bool:
    return (all(audit[k] == scenario[k] for k in
                ("state_hash", "observation_hash", "object_candidates", "candidate_hash"))
            and audit["prompt_hash"] == scenario["prompt_hashes"][condition]
            and audit["prompt_chars"] == scenario["prompt_chars"][condition])


def prepare_session(registry: Path, session_id: str, *, mode: str = "dry-run",
                    protocol: dict | None = None, root: Path | None = None):
    if mode not in MODES:
        raise ValueError("INVALID_MODE")
    protocol = protocol or load_protocol()
    validate_protocol(protocol)
    scenarios = freeze_scenarios(protocol)
    cells = allocate_cells(protocol, scenarios)
    by_scenario = {s["scenario_id"]: s for s in scenarios}
    for cell in cells:
        scenario = by_scenario[cell["scenario_id"]]
        cell.update(candidate_count=scenario["candidate_count"], candidate_hash=scenario["candidate_hash"],
                    prompt_hash=scenario["prompt_hashes"][cell["condition"]],
                    prompt_chars=scenario["prompt_chars"][cell["condition"]])
    manifest = {"schema": "Q62_FIXED_PANEL_MANIFEST_V1", "protocol": protocol,
                "protocol_hash": digest(protocol), "scenarios": scenarios, "cells": cells}
    root = root or Path(__file__).resolve().parents[3]
    environment = environment_record(root,
                                     provider_model=None, real_provider=False)
    environment.update(execution_fingerprint=execution_fingerprint(root),
                       worktree_clean=repository_info(root)["worktree_clean"],
                       dependencies={name: importlib.metadata.version(name) for name in
                                     ("httpx", "httpcore", "anyio")})
    ledger = create_session(registry, session_id, manifest,
                            {"mode": MODES[mode], "environment": environment,
                             "real_authorized": mode == "real"})
    try:
        _json(ledger.dir / "config.json", protocol)
        _json(ledger.dir / "manifest.json", manifest)
        _json(ledger.dir / "session.json", {"session_id": session_id, "mode": MODES[mode],
              "status": "PREPARING", "execution": environment, "protocol_hash": digest(protocol)})
        pair_audits = {}
        for cell in cells:
            directory = ledger.dir / "cells" / cell["cell_id"]
            directory.mkdir(parents=True)
            with build_world(directory / "world.sqlite3", cell["scenario_id"], protocol) as world:
                audit = _audit(world, cell["condition"], protocol["max_prompt_chars"])
                scenario = next(s for s in scenarios if s["scenario_id"] == cell["scenario_id"])
                if not _matches_frozen(audit, scenario, cell["condition"]):
                    raise RuntimeError("FROZEN_STATE_MISMATCH")
                comparable = {k: audit[k] for k in
                              ("state_hash", "observation_hash", "object_candidates", "candidate_hash")}
                previous = pair_audits.setdefault(cell["pair_id"], comparable)
                if previous != comparable:
                    raise RuntimeError("PAIR_INITIAL_STATE_MISMATCH")
                _json(directory / "initial_audit.json", audit)
                _json(directory / "initial_state.json", project_state(world))
                _json(directory / "initial_projection.json", project_actions(world))
        _json(ledger.dir / "session.json", {"session_id": session_id, "mode": MODES[mode],
              "status": "PREPARED", "execution": environment, "protocol_hash": digest(protocol),
              "fixed_state_pairing": "PASS"})
    except BaseException:
        ledger.close()
        raise
    return ledger


class ScriptedPanelClient:
    """Synthetic scripts are pipeline tests, never evidence about model benefit."""
    def __init__(self, case: str = "a-illegal-b-legal"):
        if case not in {"a-illegal-b-legal", "both-legal", "b-worse", "no-valid-proposal"}:
            raise ValueError("INVALID_SCRIPTED_CASE")
        self.case, self.call_count = case, 0
        self.provider_request_count = 0
        self.last_metadata = None

    async def complete(self, _system: str, user: str):
        self.call_count += 1
        body = json.loads(user)
        b = "executable_options" in body
        self.last_metadata = SimpleNamespace(http_status=200, provider_model="SCRIPTED_FAKE",
                                            input_tokens=None, output_tokens=None, reasoning_tokens=None)
        if self.case == "no-valid-proposal":
            text = "invalid synthetic JSON"
        elif (self.case == "a-illegal-b-legal" and not b) or (self.case == "b-worse" and b):
            text = canonical_json({"activity": "PLAY", "target": "game_a"})
        else:
            text = canonical_json({"activity": "LEISURE", "target": None})
        return SimpleNamespace(raw_text=text, provider_model="SCRIPTED_FAKE")


class _CellClient:
    def __init__(self, client, ledger, cell_id, fault):
        self.client, self.ledger, self.cell_id, self.fault = client, ledger, cell_id, fault
        self.last_metadata = None
        self.request_delta = None
        self.call_latency = None

    def __getattr__(self, name):
        return getattr(self.client, name)

    async def complete(self, system, user):
        self.ledger.record(self.cell_id, "CLIENT_CALL_STARTED", {"client_call_attempted": True})
        if self.fault:
            self.fault("client_call_started", self.cell_id)
        previous_metadata = getattr(self.client, "last_metadata", None)
        previous_counter = counter(getattr(self.client, "provider_request_count", None))
        started = time.perf_counter()
        succeeded = False
        try:
            reply = await self.client.complete(system, user)
            succeeded = True
            return reply
        finally:
            self.call_latency = round(time.perf_counter() - started, 6)
            current = getattr(self.client, "last_metadata", None)
            # A failing reusable client must not inherit the last successful cell's receipt.
            self.last_metadata = current if succeeded or current is not previous_metadata else None
            after_counter = counter(getattr(self.client, "provider_request_count", None))
            if previous_counter is not None and after_counter is not None and after_counter >= previous_counter:
                self.request_delta = after_counter - previous_counter


def execute_activity(world: ContinuityWorld, request_id: str, max_steps: int) -> dict:
    steps = 0
    while commitment := world.store.commitment(1):
        if steps >= max_steps:
            raise PanelStop("EXECUTION_LIMIT_EXCEEDED")
        if commitment["status"] != "ACTIVE" or commitment["remaining_min"] <= 0:
            raise PanelStop("ARCHITECTURE_ERROR")
        target = world.minute + min(15, commitment["remaining_min"])
        result = world.advance(f"{request_id}:t{target}", target)
        if not result["accepted"]:
            raise PanelStop("ARCHITECTURE_ERROR")
        steps += 1
    final = world.store.get_commitment(request_id)
    return {"commitment_status": final["status"], "execution_failure_reason": final["failure_reason"],
            "micro_steps": steps, "activity_completed": final["status"] == "COMPLETED"}


def _classify(raw: dict) -> str:
    if raw["status"] in {"ALREADY_RECORDED", "ALREADY_ATTEMPTED", "COMMITMENT_PRESENT"}:
        return "EVIDENCE_INCOMPLETE"
    if raw["status"] == "PROVIDER_ERROR":
        if raw.get("exception_type") in {"ImportError", "ModuleNotFoundError"}:
            return "ARCHITECTURE_ERROR"
        http_status = raw.get("http_status")
        return "HTTP_ERROR" if http_status is not None and http_status != 200 else (
            "PROVIDER_CONTRACT_ERROR" if http_status == 200 else "TRANSPORT_ERROR")
    return raw["status"]


def write_exports(ledger, *, mode: str, status: str, wall_seconds: float | None = None) -> dict:
    rows = ledger.rows()
    pairs = paired_comparison(rows)
    summary = summarize(rows, mode=mode, session_status=status, wall_seconds=wall_seconds)
    requests = [r.get("provider_requests") for r in rows if r.get("intent_registered") is True]
    known = [v for v in requests if counter(v) is not None]
    summary["provider_request_evidence"] = {"known_subtotal": sum(known) if known else None,
        "unknown_intents": len(requests) - len(known), "claimed_cells": ledger.claimed_count}
    if mode == "REAL_PROVIDER":
        summary["real_provider_requests"] = sum(known) if len(known) == len(requests) else None
    _json(ledger.dir / "summary.json", summary)
    _json(ledger.dir / "paired_comparison.json", pairs)
    with (ledger.dir / "cells.jsonl").open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(canonical_json(row) + "\n")
    (ledger.dir / "report_zh.md").write_text(render_report(summary, pairs), encoding="utf-8")
    return summary


async def run_session(ledger, *, mode: str, client=None, fault_hook=None, progress=print) -> dict:
    """One call per isolated cell. Fatal errors never become replacement actions."""
    saved = read_session(ledger.dir)
    protocol = saved["manifest"]["protocol"]
    validate_protocol(protocol)
    if digest(protocol) != saved["manifest"]["protocol_hash"]:
        raise ValueError("PROTOCOL_HASH_MISMATCH")
    if saved["claimed_count"] or any(c["row"] is not None for c in saved["cells"]):
        raise ValueError("NO_RESUME_OR_RERUN")
    cells = saved["manifest"]["cells"]
    by_scenario = {s["scenario_id"]: s for s in saved["manifest"]["scenarios"]}
    mode_name = MODES[mode]
    if mode == "dry-run":
        return write_exports(ledger, mode=mode_name, status="NOT_RUN")
    if client is None:
        raise ValueError("EXPLICIT_CLIENT_REQUIRED")
    started = time.perf_counter()
    stop_reason = "PANEL_COMPLETED"
    for cell in cells:
        cid = cell["cell_id"]
        directory = ledger.dir / "cells" / cid
        scenario = by_scenario[cell["scenario_id"]]
        audit = {k: scenario[k] for k in ("state_hash", "observation_hash", "object_candidates",
                                         "candidate_hash", "candidate_count")}
        audit.update(prompt_hash=scenario["prompt_hashes"][cell["condition"]],
                     prompt_chars=scenario["prompt_chars"][cell["condition"]])
        before = scenario["initial_projected_state"]
        evidence = {}
        row = {**cell, **{k: audit[k] for k in ("candidate_count", "candidate_hash", "prompt_chars", "prompt_hash")},
               "intent_registered": False, "client_call_attempted": False,
               "http_response_observed": None, "service_contract_valid": None,
               "strict_json_valid": None, "catalog_valid": None, "rule_checked": None,
               "start_accepted": None, "activity_completed": None, "invariants_valid": None,
               "proposal_in_feasible_set": None, "before_state": before,
               "requested_model": atom(getattr(client, "_model", "SCRIPTED_FAKE") if mode == "offline"
                                  else getattr(client, "_model", None)),
               "input_tokens": None, "output_tokens": None, "reasoning_tokens": None,
               "provider_model": None, "provider_requests": 0 if mode == "offline" else None}
        try:
            if not (directory / "world.sqlite3").is_file():
                raise PanelStop("EVIDENCE_INCOMPLETE")
            with ContinuityWorld(directory / "world.sqlite3") as world:
                current = _audit(world, cell["condition"], protocol["max_prompt_chars"])
                if current != audit or not _matches_frozen(current, by_scenario[cell["scenario_id"]], cell["condition"]):
                    raise RuntimeError("PRE_CALL_SNAPSHOT_CHANGED")
                if project_state(world) != before:
                    raise RuntimeError("PRE_CALL_PROJECTED_STATE_CHANGED")
                try:
                    artifact_audit = json.loads((directory / "initial_audit.json").read_text())
                except (OSError, ValueError) as error:
                    raise PanelStop("EVIDENCE_INCOMPLETE") from error
                if artifact_audit != audit:
                    raise PanelStop("EVIDENCE_INCOMPLETE")
                projection_before = project_actions(world)
                if mode == "real":
                    root = Path(__file__).resolve().parents[3]
                    frozen_environment = saved["metadata"]["environment"]
                    info = repository_info(root)
                    if (info["git_commit"] != frozen_environment["git_commit"] or not info["worktree_clean"]
                            or execution_fingerprint(root) != frozen_environment["execution_fingerprint"]):
                        raise PanelStop("ARCHITECTURE_ERROR")
                request_id = ledger.claim(cid)
                row.update(request_id=request_id, intent_registered=True)
                if fault_hook:
                    fault_hook("intent_registered", cid)
                proxy = _CellClient(client, ledger, cid, fault_hook)
                def hook(stage, data, current_id=cid, current_evidence=evidence, current_proxy=proxy):
                    # Safe stages arrive before parsing / before irreversible execution.
                    if mode == "real" and stage in {"RESPONSE_OBSERVED", "DECISION_RECORDED"}:
                        data = {**data, "provider_requests": current_proxy.request_delta}
                    ledger.record(current_id, stage, data)
                    current_evidence.update(data)
                    if fault_hook:
                        fault_hook(stage.lower(), current_id)
                runner = ActivityDecisionRunner(world, proxy, max_calls=1,
                    hard_timeout_seconds=protocol["timeout_seconds"],
                    journal_path=directory / "decision_journal.jsonl",
                    prompt_builder=lambda w, a, context_mode=cell["condition"]: projected_prompt(w, a, mode=context_mode,
                                                                max_chars=protocol["max_prompt_chars"]),
                    evidence_hook=hook)
                try:
                    raw = await runner.decide(request_id)
                except asyncio.CancelledError:
                    attempt = world.store.db.execute("SELECT data FROM decision_attempts WHERE id=?", (request_id,)).fetchone()
                    raw = json.loads(attempt[0]) if attempt else {"status": "REQUEST_CANCELLED"}
                safe_metadata = metadata(proxy)
                safe_metadata.update({k: raw[k] for k in safe_metadata if raw.get(k) is not None})
                row.update(status=_classify(raw), **safe_metadata,
                           exception_type=raw.get("exception_type"),
                           failure_category=raw.get("failure_category"), latency_seconds=proxy.call_latency)
                for key in ("strict_json_valid", "catalog_valid", "service_contract_valid",
                            "proposal_activity", "proposal_target", "proposal_target_hash"):
                    row[key] = evidence.get(key)
                row["http_response_observed"] = row["http_status"] is not None
                if raw["status"].startswith("PROVIDER_"):
                    row["service_contract_valid"] = False
                if mode == "real":
                    # Actual client has an explicit per-call counter. A claim alone is not a send.
                    row["provider_requests"] = proxy.request_delta
                    if proxy.request_delta is not None and proxy.request_delta > 1:
                        raise PanelStop("REQUEST_BUDGET_EXHAUSTED")
                proposal = raw.get("proposal")
                if proposal:
                    row["proposal_activity"], row["proposal_target"] = proposal["activity"], proposal["target"]
                    row["proposal_in_feasible_set"] = proposal_in_feasible_set(proposal, projection_before)
                    row.update(rule_checked=True, start_accepted=raw["result"]["accepted"])
                if row["start_accepted"]:
                    row.update(execute_activity(world, request_id, protocol["max_activity_micro_steps"]))
                    if not row["activity_completed"]:
                        row["status"] = "COMMITMENT_FAILED"
                elif row["status"] == "RULE_REJECTED":
                    row["activity_completed"] = False
                row["rule_reason"] = (raw.get("result") or {}).get("reason")
                if fault_hook:
                    fault_hook("activity_committed", cid)
                validation = validate_world(world)
                row.update(invariants_valid=True, final_state_hash=validation["state_hash"],
                           after_state=project_state(world), simulation_minutes=world.minute - before["minute"],
                           events_count=len(world.store.events()))
                if row["status"] == "COMMITMENT_FAILED" and row.get("execution_failure_reason") not in protocol["known_commitment_failures"]:
                    row["status"] = "UNKNOWN_EXECUTION_FAILURE"
                ledger.record(cid, "WORLD_RESULT_COMMITTED", row)
                if fault_hook:
                    fault_hook("world_result_committed", cid)
                _json(directory / "final_state.json", world.store.snapshot())
        except Exception as error:
            code = ("REQUEST_BUDGET_EXHAUSTED" if isinstance(error, LedgerError)
                    else "STATE_INVARIANT_FAILED" if isinstance(error, AssertionError)
                    else error.code if isinstance(error, PanelStop) else "ARCHITECTURE_ERROR")
            row.update(status=code,
                       exception_type=exception_type(error))
            if isinstance(error, AssertionError):
                row["invariants_valid"] = False
            row["missing_evidence"] = ["NORMAL_FINALIZATION_INTERRUPTED"]
        durable = next(r for r in ledger.rows() if r["cell_id"] == cid)
        for key in ("intent_registered", "client_call_attempted", "http_response_observed",
                    "service_contract_valid", "strict_json_valid", "catalog_valid",
                    "proposal_activity", "proposal_target", "proposal_target_hash",
                    "input_tokens", "output_tokens", "reasoning_tokens", "provider_model", "http_status"):
            if durable.get(key) is not None:
                row[key] = durable[key]
        if row.get("missing_evidence") and (directory / "world.sqlite3").is_file():
            # Read the partial committed world without re-executing any activity.
            with open_readonly_world(directory / "world.sqlite3") as world:
                row.update(after_state=project_state(world), simulation_minutes=world.minute - before["minute"],
                           events_count=len(world.store.events()))
            # Do not fabricate result/response facts when a recording operation failed.
        if row["status"] == "DECISION_ACCEPTED" and row["activity_completed"] is not True:
            row["status"] = "EVIDENCE_INCOMPLETE"
        fatal = row["status"] not in {"DECISION_ACCEPTED", "RULE_REJECTED", "COMMITMENT_FAILED"}
        if fatal:
            stop_reason = row["status"]
        if not row["intent_registered"]:
            row.update(status="NOT_RUN", stop_reason=stop_reason)
        ledger.finish(cid, row)
        if fatal:
            for remaining in cells[cell["order"]:]:
                ledger.finish(remaining["cell_id"], {**remaining, "status": "NOT_RUN",
                    "stop_reason": stop_reason, "intent_registered": False,
                    "client_call_attempted": False, "provider_requests": 0})
        write_exports(ledger, mode=mode_name, status=stop_reason if fatal else "RUNNING",
                                wall_seconds=round(time.perf_counter() - started, 6))
        if progress:
            progress(f"COMPLETED={cell['order']}/48 CELL={cid} STATUS={row['status']} CALLS={sum(r.get('client_call_attempted') is True for r in ledger.rows())}")
        if fatal:
            break
    return write_exports(ledger, mode=mode_name, status=stop_reason,
                         wall_seconds=round(time.perf_counter() - started, 6))


def export_only(source: Path, output: Path) -> dict:
    """Only read already committed facts. No client, credential, action or migration."""
    if output.resolve() == source.resolve() or source.resolve() in output.resolve().parents:
        raise ValueError("RECOVERY_MUST_BE_NEW_EXTERNAL_DIRECTORY")
    saved = read_session(source)
    rows = saved["rows"]
    for row in rows:
        if row["status"] == "NOT_RUN":
            row.setdefault("stop_reason", "SOURCE_SESSION_NOT_EXECUTED_OR_INTERRUPTED_NO_RESUME")
        directory = source / "cells" / row["cell_id"]
        request_id = row.get("request_id")
        if not request_id or not row.get("missing_evidence"):
            continue
        with open_readonly_world(directory / "world.sqlite3") as world:
            initial = project_state(world)
            scenario = next(s for s in saved["manifest"]["scenarios"]
                            if s["scenario_id"] == row["scenario_id"])
            row["before_state"] = scenario["initial_projected_state"]
            row.update(after_state=initial, simulation_minutes=world.minute - row["before_state"]["minute"],
                       events_count=len(world.store.events()))
            attempt = world.store.db.execute("SELECT status,data FROM decision_attempts WHERE id=?", (request_id,)).fetchone()
            command = world.store.db.execute("SELECT result FROM commands WHERE id=?", (request_id,)).fetchone()
            if attempt:
                raw = json.loads(attempt["data"])
                row.update(last_world_decision_status=attempt["status"])
                if attempt["status"] != "REQUEST_STARTED":
                    row.update({k: raw.get(k) for k in ("input_tokens", "output_tokens", "reasoning_tokens", "http_status", "provider_model", "latency_seconds")})
                    row["status"] = _classify(raw)
                    row["http_response_observed"] = row.get("http_status") is not None
                    proposal = raw.get("proposal")
                    if proposal:
                        row.update(proposal_activity=proposal["activity"], proposal_target=proposal["target"])
                        scenario = next(s for s in saved["manifest"]["scenarios"]
                                        if s["scenario_id"] == row["scenario_id"])
                        row["proposal_in_feasible_set"] = proposal_in_feasible_set(proposal, scenario)
            if command:
                result = json.loads(command[0])
                row.update(rule_checked=True, start_accepted=result["accepted"], rule_reason=result["reason"])
                if result["accepted"]:
                    final = world.store.get_commitment(request_id)
                    row.update(commitment_status=final["status"], activity_completed=final["status"] == "COMPLETED",
                               execution_failure_reason=final["failure_reason"])
                    row["status"] = ("DECISION_ACCEPTED" if final["status"] == "COMPLETED"
                                     else ("COMMITMENT_FAILED" if final["failure_reason"] in KNOWN_COMMITMENT_FAILURES
                                           else "UNKNOWN_EXECUTION_FAILURE") if final["status"] == "FAILED"
                                     else "UNKNOWN")
                else:
                    row.update(status="RULE_REJECTED", activity_completed=False)
                try:
                    validation = validate_world(world)
                    row.update(invariants_valid=True, final_state_hash=validation["state_hash"],
                               after_state=project_state(world))
                except AssertionError:
                    row.update(status="STATE_INVARIANT_FAILED", invariants_valid=False)
            row["recovery_source"] = "READ_ONLY_COMMITTED_WORLD_AND_SESSION_LEDGER"
    output.mkdir(parents=True, exist_ok=False)
    pairs = paired_comparison(rows)
    summary = summarize(rows, mode=saved["metadata"]["mode"], session_status="STOPPED_READ_ONLY_RECOVERY")
    _json(output / "summary.json", summary)
    _json(output / "paired_comparison.json", pairs)
    _json(output / "recovery.json", {"source": str(source.resolve()), "automatic_resume": False,
          "source_modified": False, "new_provider_requests": 0,
          "last_complete_evidence": len(saved["evidence"]),
          "missing_evidence_cells": [r["cell_id"] for r in rows if r["status"] == "UNKNOWN"]})
    with (output / "cells.jsonl").open("x", encoding="utf-8") as stream:
        stream.write("".join(canonical_json(row) + "\n" for row in rows))
    (output / "report_zh.md").write_text(render_report(summary, pairs), encoding="utf-8")
    return summary
