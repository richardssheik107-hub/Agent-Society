"""Synthetic evidence tests only: never mutate or copy the historical real run."""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

from social_sim.continuity import q6_2_outcome_source as source
from social_sim.continuity.benchmark import seed_demo
from social_sim.continuity.engine import ContinuityWorld
from social_sim.continuity.q6_2_panel_reporting import paired_comparison, summarize


def _write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _project_state(world):
    """Test-only equivalent known state projection; no decision/client imports."""
    actor = world.store.actor(1)
    assert world.store.commitment(1) is None
    objects = {name: world.store.object(name) for name in source.OBJECTS}
    links = {name: world.store.link(1, name) for name in source.OBJECTS}
    watched = links["series_a"]["watched"]
    episodes = objects["series_a"]["episodes"]
    return {"minute": world.minute, "state_version": actor["version"],
            **{key: actor[key] for key in ("money_cents", "hunger_milli", "energy_milli", "location")},
            "commitment": None, "inventory": {name: links[name]["quantity"] for name in source.OBJECTS},
            "play_minutes": {"game_a": links["game_a"]["play_minutes"]},
            "media_progress": {"series_a": {"total_episodes": episodes, "watched": list(watched),
                "offsets": dict(links["series_a"]["offsets"]),
                "view_counts": dict(links["series_a"]["view_counts"]),
                "next_episode": next((n for n in range(1, episodes + 1) if n not in watched), None)}}}


def _state():
    return {"minute": 0, "money_cents": 5000, "hunger_milli": 800,
            "energy_milli": 700, "state_version": 0, "location": "home", "commitment": None,
            "inventory": dict.fromkeys(source.OBJECTS, 0), "play_minutes": {"game_a": 0},
            "media_progress": {"series_a": {"next_episode": 1, "offsets": {},
                "view_counts": {}, "watched": [], "total_episodes": 120}}}


def _cells():
    cells = []
    families = sorted(source.FAMILIES)
    for index in range(1, 49):
        pair = (index + 1) // 2
        condition = "A_RAW" if index % 2 else "B_FEASIBLE"
        scenario = (pair + 1) // 2
        before = _state()
        after = copy.deepcopy(before)
        after.update(minute=15, state_version=3, hunger_milli=815, energy_milli=685, location="restaurant")
        timeout = (pair == 14 and condition == "A_RAW") or (pair == 21 and condition == "B_FEASIBLE")
        row = {"cell_id": f"c{index:03}", "pair_id": f"p{pair:03}", "scenario_id": f"s{scenario:02}",
               "family": families[(scenario - 1) // 2], "condition": condition, "order": index,
               "pair_order": pair, "repeat": 1 if pair % 2 else 2,
               "within_pair_order": 1 if index % 2 else 2,
               "candidate_count": 1, "candidate_hash": "a" * 64, "prompt_chars": 100,
               "prompt_hash": "b" * 64, "final_state_hash": "c" * 64,
               "status": "PROVIDER_TIMEOUT" if timeout else "DECISION_ACCEPTED",
               "before_state": before, "after_state": before if timeout else after,
               "proposal_activity": None if timeout else "TRAVEL",
               "proposal_target": None if timeout else "restaurant",
               "provider_model": None if timeout else "glm-5.3", "requested_model": "ark-code-latest",
               "commitment_status": None if timeout else "COMPLETED", "events_count": 1,
               "simulation_minutes": 0 if timeout else 15, "provider_requests": 1,
               "latency_seconds": 60.0 if timeout else 1.25,
               "input_tokens": None if timeout else 101, "output_tokens": None if timeout else 90,
               "reasoning_tokens": None if timeout else 88, "http_status": None if timeout else 200}
        for key in source.FLAG_FIELDS:
            row[key] = True
        if timeout:
            for key in ("activity_completed", "http_response_observed", "strict_json_valid", "catalog_valid",
                        "rule_checked", "proposal_in_feasible_set", "start_accepted"):
                row[key] = None
            row["service_contract_valid"] = False
        cells.append(row)
    return cells


@pytest.fixture
def allocated_source(tmp_path):
    directory = tmp_path / "synthetic_source"
    directory.mkdir()
    for name in source.TOP_FILES:
        (directory / name).write_bytes(b"{}")
    for index in range(1, 49):
        cell = directory / "cells" / f"c{index:03}"
        cell.mkdir(parents=True)
        for name in source.CELL_FILES:
            (cell / name).write_bytes(b"opaque journal, not a JSON/completion parser")
    return directory


def test_all_297_regular_files_hashed_and_read_only(allocated_source):
    before = source.source_hashes(allocated_source)
    assert len(before) == 297
    proof = source.verify_source_unchanged(allocated_source, before)
    assert proof["SOURCE_FILES_UNCHANGED"] == "PASS"
    assert proof["before"] == proof["after"]
    assert proof["new_real_provider_requests"] == 0


def test_hash_streams_journal_without_decoding(allocated_source, monkeypatch):
    def no_text(*args, **kwargs):
        pytest.fail("source hashing must not decode text")
    monkeypatch.setattr(Path, "read_text", no_text)
    assert len(source.source_hashes(allocated_source)) == 297


@pytest.mark.parametrize("extra", [".env", "response.json", "cells/c001/completion.txt", "cells/c049/world.sqlite3"])
def test_unapproved_files_rejected_before_they_are_read(allocated_source, extra, monkeypatch):
    added = allocated_source / extra
    added.parent.mkdir(parents=True, exist_ok=True)
    added.write_text("never expose this arbitrary text", encoding="utf-8")
    original = Path.open
    def guarded(path, *args, **kwargs):
        assert path != added
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", guarded)
    with pytest.raises(source.SourceEvidenceError, match="source.file_allowlist"):
        source.source_hashes(allocated_source)


def test_file_count_difference_is_not_claimed_as_297(allocated_source):
    # Exactly one explicit synthetic file removed, never a historical file.
    (allocated_source / "report_zh.md").unlink()
    with pytest.raises(source.SourceEvidenceError, match="source.file_count"):
        source.source_hashes(allocated_source)


def test_source_changed_stops_instead_of_repairing(allocated_source):
    before = source.source_hashes(allocated_source)
    path = allocated_source / "summary.json"
    path.write_bytes(b'{"tampered":true}')
    with pytest.raises(source.SourceEvidenceError, match="hashes_unchanged"):
        source.verify_source_unchanged(allocated_source, before)
    assert path.read_bytes() == b'{"tampered":true}'


def test_source_symlink_is_rejected(allocated_source, tmp_path):
    link = allocated_source / "cells/c001/untrusted"
    link.symlink_to(tmp_path)
    with pytest.raises(source.SourceEvidenceError, match="source.symlink"):
        source.source_hashes(allocated_source)


def test_missing_source_fails_without_report_fabrication(tmp_path):
    with pytest.raises(source.SourceEvidenceError, match="source.directory"):
        source.load_verified_session(tmp_path / "missing")
    assert list(tmp_path.iterdir()) == []


def test_malformed_structure_has_safe_fixed_error(allocated_source):
    _write(allocated_source / "manifest.json", {"arbitrary": "PRIVATE_SENTINEL"})
    with pytest.raises(source.SourceEvidenceError) as error:
        source.load_verified_session(allocated_source)
    assert "PRIVATE_SENTINEL" not in str(error.value)
    assert "SOURCE_EVIDENCE_MISMATCH:" in str(error.value)


def test_48_cells_24_pairs_22_complete_and_both_timeouts():
    cells = [source.sanitize_cell(row) for row in _cells()]
    original = paired_comparison(_cells(), protocol_version=source.PROTOCOL_VERSION)
    pairs = source._pairs(original, cells)
    assert len(cells) == 48 and len(pairs) == 24
    assert sum(pair["scored_pair_complete"] for pair in pairs) == 22
    assert [pair["pair_id"] for pair in pairs if not pair["scored_pair_complete"]] == ["p014", "p021"]
    missing = [cell for cell in cells if cell["status"] == "PROVIDER_TIMEOUT"]
    assert len(missing) == 2
    assert all(cell["effects_observed"] is False and cell["activity_completed"] is None for cell in missing)


@pytest.mark.parametrize("field", ["repeat", "scenario_id", "family"])
def test_pair_requires_matching_scenario_repeat_family(field):
    raw = _cells()
    cells = [source.sanitize_cell(row) for row in raw]
    pairs = paired_comparison(raw, protocol_version=source.PROTOCOL_VERSION)
    cells[1][field] = 2 if field == "repeat" else "s12" if field == "scenario_id" else "OWNERSHIP"
    with pytest.raises(source.SourceEvidenceError, match="scenario_repeat"):
        source._pairs(pairs, cells)


def test_pair_initial_state_mismatch_stops():
    raw = _cells()
    cells = [source.sanitize_cell(row) for row in raw]
    pairs = paired_comparison(raw, protocol_version=source.PROTOCOL_VERSION)
    cells[1]["before_state"]["money_cents"] += 1
    with pytest.raises(source.SourceEvidenceError, match="initial_state"):
        source._pairs(pairs, cells)


def test_duplicate_or_missing_pair_not_repaired():
    raw = _cells()
    cells = [source.sanitize_cell(row) for row in raw]
    pairs = paired_comparison(raw, protocol_version=source.PROTOCOL_VERSION)
    pairs[-1] = pairs[0]
    with pytest.raises(source.SourceEvidenceError, match="identity"):
        source._pairs(pairs, cells)


@pytest.mark.parametrize("field", ["proposal_activity", "proposal_target", "activity_completed", "input_tokens"])
def test_timeout_proposal_and_cost_cannot_be_filled(field):
    row = _cells()[26]
    row[field] = {"proposal_activity": "MEAL", "proposal_target": "food_meal", "activity_completed": False,
                  "input_tokens": 0}[field]
    with pytest.raises(source.SourceEvidenceError, match="timeout_missing"):
        source.sanitize_cell(row)


def test_arbitrary_model_text_and_unknown_fields_are_not_exported():
    row = _cells()[0]
    row.update(completion="PRIVATE_SENTINEL", prompt="PRIVATE_SENTINEL", authorization="PRIVATE_SENTINEL")
    row["before_state"]["private"] = "PRIVATE_SENTINEL"
    safe = source.sanitize_cell(row)
    assert "PRIVATE_SENTINEL" not in json.dumps(safe)
    assert not any(field in safe for field in ("completion", "prompt", "authorization"))


@pytest.mark.parametrize("field,value", [("proposal_target", "PRIVATE_SENTINEL"),
    ("provider_model", "PRIVATE_SENTINEL"), ("location", "PRIVATE_SENTINEL"),
    ("hunger_milli", 1001), ("energy_milli", -1), ("money_cents", True)])
def test_unsafe_values_fail_with_field_not_value(field, value):
    row = _cells()[0]
    if field in {"location", "hunger_milli", "energy_milli", "money_cents"}:
        row["before_state"][field] = value
    else:
        row[field] = value
    with pytest.raises(source.SourceEvidenceError) as error:
        source.sanitize_cell(row)
    assert "PRIVATE_SENTINEL" not in str(error.value)


@pytest.mark.parametrize("elapsed", [0, 14, True, -1])
def test_simulated_minutes_must_match_world_clock(elapsed):
    row = _cells()[0]
    row["simulation_minutes"] = elapsed
    with pytest.raises(source.SourceEvidenceError):
        source.sanitize_cell(row)


def test_original_counts_are_verified_not_redefined():
    raw = _cells()
    safe = [source.sanitize_cell(row) for row in raw]
    pairs = source._pairs(paired_comparison(raw, protocol_version=source.PROTOCOL_VERSION), safe)
    summary = summarize(raw, mode="REAL_PROVIDER", session_status="PANEL_COMPLETED",
                        protocol_version=source.PROTOCOL_VERSION)
    counts = source._verify_counts(summary, safe, pairs, "summary")
    assert counts["valid_proposals"] == counts["activity_completed"] == 46
    assert counts["rule_rejected"] == counts["commitment_failed"] == 0
    summary["counts"]["rule_rejected"] = 1
    with pytest.raises(source.SourceEvidenceError, match="summary.counts"):
        source._verify_counts(summary, safe, pairs, "summary")


def test_immutable_connection_rejects_writes_and_changes_no_bytes(tmp_path):
    path = tmp_path / "domain.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE facts(value INTEGER)")
        db.execute("INSERT INTO facts VALUES(17)")
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    with source.readonly_sqlite(path) as db:
        assert db.execute("SELECT value FROM facts").fetchone()[0] == 17
        with pytest.raises(sqlite3.OperationalError):
            db.execute("UPDATE facts SET value=0")
        assert db.execute("PRAGMA query_only").fetchone()[0] == 1
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    assert not Path(str(path) + "-wal").exists()
    assert not Path(str(path) + "-journal").exists()


def test_active_wal_and_missing_db_refused_without_creation(tmp_path):
    path = tmp_path / "domain.sqlite3"
    with pytest.raises(source.SourceEvidenceError, match="sqlite.source"), source.readonly_sqlite(path):
        pass
    assert not path.exists()
    path.write_bytes(b"synthetic")
    Path(str(path) + "-wal").write_bytes(b"active")
    with pytest.raises(source.SourceEvidenceError, match="sqlite.active_wal"), source.readonly_sqlite(path):
        pass


def test_world_domain_state_and_food_ledger_verified_read_only(tmp_path):
    cell_dir = tmp_path / "cell"
    cell_dir.mkdir()
    path = cell_dir / "world.sqlite3"
    with ContinuityWorld(path) as world:
        seed_demo(world)
        before = _project_state(world)
        fixture_count = len(world.store.events())
        result = world.start("synthetic-meal", 1, "MEAL", "food_meal")
        assert result["accepted"] is True
        for _ in range(8):
            if world.store.commitment(1) is None:
                break
            remaining = world.store.commitment(1)["remaining_min"]
            until = world.minute + min(15, remaining)
            assert world.advance(f"synthetic-t{until}", until)["accepted"] is True
        assert world.store.commitment(1) is None
        after = _project_state(world)
        snapshot = world.store.snapshot()
        event_count = len(world.store.events())
    _write(cell_dir / "final_state.json", snapshot)
    cell = {"before_state": before, "after_state": after, "final_state_hash": source.canonical_digest(snapshot),
            "events_count": event_count}
    before_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    facts = source._world(path, cell, fixture_count)
    assert facts["purchased_quantities"] == {"food_meal": 1}
    assert facts["consumed_quantities"] == {"food_meal": 1}
    assert facts["calories_kcal_before"] == 0 and facts["calories_kcal_after"] == 650
    assert facts["work_minutes_before"] == facts["work_minutes_after"] == 0
    assert before["inventory"]["food_meal"] == after["inventory"]["food_meal"] == 0
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before_hash
    cell["after_state"]["money_cents"] += 1
    with pytest.raises(source.SourceEvidenceError, match="world.after_state"):
        source._world(path, cell, fixture_count)


def test_analysis_module_imports_only_standard_library_and_has_no_writes():
    path = Path(source.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    modules = [name.name for node in imports if isinstance(node, ast.Import) for name in node.names]
    modules.extend(node.module for node in imports if isinstance(node, ast.ImportFrom))
    assert all(not str(module).startswith(("social_sim", "httpx", "openai", "requests")) for module in modules)
    assert not any(isinstance(node, ast.Attribute) and node.attr in
                   {"write_text", "write_bytes", "mkdir", "unlink", "execute_script"} for node in ast.walk(tree))


@pytest.fixture(scope="module")
def complete_synthetic_evidence(tmp_path_factory):
    """Create fresh synthetic worlds from frozen recipes; no real source copied.

    Disposable recipes use the new pure offline audit plumbing, not the old
    Q6.1 fixture module which imports decision clients. The fresh CLI interpreter
    below rejects client imports, credential access, and socket connections.
    Fake HTTP metadata are contract fixtures, not claimed provider responses.
    """
    from social_sim.continuity.action_projection import project_actions, projected_prompt
    from social_sim.continuity.context import observe
    from social_sim.continuity.q6_2_outcome_prompt import _build_isolated, _expected_allocations
    from social_sim.continuity.q6_2_panel_ledger import create_session

    root = tmp_path_factory.mktemp("offline_success_evidence")
    repository = Path(__file__).resolve().parents[1]
    protocol = json.loads((repository / "config/experimental/q6_2_fixed_state_panel_v2.json").read_text(encoding="utf-8"))
    assert source.canonical_digest(protocol) == source.PROTOCOL_HASH
    @contextmanager
    def build_world(path, scenario_id, protocol):
        specification = next(item for item in protocol["scenarios"] if item["scenario_id"] == scenario_id)
        with ContinuityWorld(path) as world:
            _build_isolated(world, specification["recipe"], protocol["max_activity_micro_steps"])
            yield world
    scenarios = []
    for specification in protocol["scenarios"]:
        with build_world(":memory:", specification["scenario_id"], protocol) as world:
            projection = project_actions(world)
            observation = observe(world, 1)
            prompts = {mode: projected_prompt(world, mode=mode, max_chars=protocol["max_prompt_chars"])
                       for mode in source.CONDITIONS}
            scenarios.append({**specification, "schema": "Q62_FIXED_STATE_FIXTURES_V1",
                "initial_projected_state": _project_state(world),
                "state_hash": source.canonical_digest(world.store.snapshot()),
                "observation_hash": source.canonical_digest(observation),
                "observation_chars": len(json.dumps(observation, ensure_ascii=False, sort_keys=True, separators=(",", ":"))),
                "object_candidates": observation["objects"],
                "candidate_hash": projection["candidate_digest"], "candidate_count": projection["candidate_count"],
                "executable_options": projection["executable_options"],
                "fixture_event_count": len(world.store.events()),
                "state_minute": world.minute, "state_version": observation["actor"]["version"],
                "prompt_hashes": {mode: source.canonical_digest({"system": prompt[0], "user": prompt[1]})
                                  for mode, prompt in prompts.items()},
                "prompt_chars": {mode: len(prompt[0]) + len(prompt[1]) for mode, prompt in prompts.items()},
                "prompt_bytes": {mode: len(prompt[0].encode()) + len(prompt[1].encode()) for mode, prompt in prompts.items()},
                "invariants": "PASS"})
    plans = _expected_allocations(protocol)
    for plan in plans:
        scenario = next(item for item in scenarios if item["scenario_id"] == plan["scenario_id"])
        plan.update(candidate_count=scenario["candidate_count"], candidate_hash=scenario["candidate_hash"],
                    prompt_chars=scenario["prompt_chars"][plan["condition"]],
                    prompt_hash=scenario["prompt_hashes"][plan["condition"]])
    scenario_fields = ("scenario_id", "family", "state_hash", "initial_projected_state",
                       "observation_hash", "object_candidates", "candidate_hash", "prompt_hashes")
    allocation_fields = ("cell_id", "pair_id", "scenario_id", "family", "repeat", "condition",
                         "order", "pair_order", "within_pair_order")
    research_states = [{key: item[key] for key in scenario_fields} for item in scenarios]
    allocation = [{key: item[key] for key in allocation_fields} for item in plans]
    fairness = {"schema": "Q62_FIXED_PANEL_FAIRNESS_V1", "scenario_count": 12, "cell_count": 48,
                "scenario_fingerprint": source.canonical_digest(research_states),
                "schedule_fingerprint": source.canonical_digest(allocation),
                "fairness_fingerprint": source.canonical_digest({"scenarios": research_states, "cells": allocation})}
    manifest = {"schema": "Q62_FIXED_PANEL_MANIFEST_V1", "protocol": protocol,
                "protocol_hash": source.PROTOCOL_HASH, "scenarios": scenarios, "cells": plans,
                "fairness": fairness}
    session_id = "q62-panel-real-v2-01"
    rows = []
    prototypes = _cells()
    with create_session(root / "synthetic_registry", session_id, manifest, {"synthetic": True}) as ledger:
        directory = ledger.dir
        for plan in plans:
            cell_dir = directory / "cells" / plan["cell_id"]
            cell_dir.mkdir(parents=True)
            scenario = next(item for item in scenarios if item["scenario_id"] == plan["scenario_id"])
            timeout = plan["cell_id"] in {"c027", "c041"}
            row = {**copy.deepcopy(prototypes[26] if timeout else prototypes[0]), **plan}
            row["request_id"] = ledger.claim(plan["cell_id"])
            ledger.record(plan["cell_id"], "CLIENT_CALL_STARTED", {})
            with build_world(cell_dir / "world.sqlite3", plan["scenario_id"], protocol) as world:
                initial = _project_state(world)
                projection = project_actions(world)
                _write(cell_dir / "initial_state.json", initial)
                _write(cell_dir / "initial_projection.json", projection)
                _write(cell_dir / "initial_audit.json", {
                    "candidate_count": plan["candidate_count"], "candidate_hash": plan["candidate_hash"],
                    "prompt_chars": plan["prompt_chars"], "prompt_hash": plan["prompt_hash"],
                    "state_hash": scenario["state_hash"], "observation_hash": scenario["observation_hash"],
                    "object_candidates": scenario["object_candidates"],
                })
                if not timeout:
                    option = next(item for item in projection["executable_options"] if item["activity"] == "MEAL")
                    row.update(proposal_activity=option["activity"], proposal_target=option["target"])
                    assert world.start(row["request_id"], 1, **option)["accepted"] is True
                    for _ in range(8):
                        commitment = world.store.commitment(1)
                        if commitment is None:
                            break
                        until = world.minute + min(15, commitment["remaining_min"])
                        assert world.advance(row["request_id"] + f":t{until}", until)["accepted"] is True
                    assert world.store.commitment(1) is None
                snapshot = world.store.snapshot()
                row.update(before_state=initial, after_state=_project_state(world),
                           events_count=len(world.store.events()), final_state_hash=source.canonical_digest(snapshot),
                           simulation_minutes=world.minute - initial["minute"])
                _write(cell_dir / "final_state.json", snapshot)
            # Opaque text must be hashed but must never be decoded or exported.
            (cell_dir / "decision_journal.jsonl").write_bytes(b"RAW_MODEL_TEXT_SENTINEL")
            if not timeout:
                ledger.record(plan["cell_id"], "RESPONSE_OBSERVED", {"http_status": 200})
                ledger.record(plan["cell_id"], "PARSE_RESULT", {"strict_json_valid": True})
            ledger.record(plan["cell_id"], "WORLD_RESULT_COMMITTED", {})
            ledger.finish(plan["cell_id"], row)
            rows.append(row)
    _write(directory / "manifest.json", manifest)
    _write(directory / "config.json", protocol)
    _write(directory / "session.json", {
        "session_id": session_id, "mode": "REAL_PROVIDER", "status": "PANEL_COMPLETED",
        "session_termination": "PANEL_COMPLETED", "processed_cells": 48, "protocol_hash": source.PROTOCOL_HASH,
        "execution": {"git_commit": source.EXECUTION_COMMIT,
                      "agentsociety_submodule_commit": "670c94fff7c64c4f79b632125f2ccf968155e746"},
    })
    cleanup = {"cleanup_exception_type": None, "cleanup_local_settled": True, "cleanup_outcome": "CLOSED"}
    _write(directory / "cleanup.json", cleanup)
    pairs = paired_comparison(rows, protocol_version=source.PROTOCOL_VERSION)
    summary = summarize(rows, mode="REAL_PROVIDER", session_status="PANEL_COMPLETED",
                        protocol_version=source.PROTOCOL_VERSION, session_termination="PANEL_COMPLETED",
                        cleanup_outcome="CLOSED")
    _write(directory / "summary.json", summary)
    _write(directory / "paired_comparison.json", pairs)
    (directory / "cells.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    (directory / "report_zh.md").write_text("这是独立合成测试数据，不是真实模型证据。", encoding="utf-8")
    hashes = source.source_hashes(directory)
    recovery = root / "synthetic_recovery"
    recovery.mkdir()
    _write(recovery / "summary.json", summary)
    _write(recovery / "paired_comparison.json", pairs)
    (recovery / "cells.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    _write(recovery / "recovery.json", {"automatic_resume": False, "source_modified": False,
                                         "new_provider_requests": 0})
    _write(recovery / "source_hash_proof.json", {"source_files": 297, "source_hashes": hashes,
        "source_all_hashes_unchanged": True, "source_modified": False, "new_provider_requests": 0})
    analysis = root / "synthetic_analysis"
    analysis.mkdir()
    selected_hashes = {name: hashes[name] for name in (
        "summary.json", "cells.jsonl", "paired_comparison.json", "manifest.json", "session.json", "cleanup.json")}
    _write(analysis / "safe_metrics.json", {
        "source_session_id": session_id, "source_execution_commit": source.EXECUTION_COMMIT,
        "protocol_canonical_hash": source.PROTOCOL_HASH, "overall": {"counts": summary["counts"]},
        "pair_counts": summary["pair_counts"], "pairs": pairs, "additional_provider_requests": 0,
        "source_written": False, "credential_files_read": 0, "source_hashes": selected_hashes,
    })
    _write(analysis / "source_integrity.json", {"unchanged": True, "credential_files_read": 0,
        "provider_requests": 0, "before": selected_hashes, "after": selected_hashes})
    return directory, recovery, analysis, hashes


@pytest.mark.parametrize("entrypoint", ["main", "audit_to_directory"])
def test_successful_cli_fresh_interpreter_has_zero_network_credentials_or_provider_imports(
        complete_synthetic_evidence, tmp_path, entrypoint):
    directory, recovery, analysis, before_hashes = complete_synthetic_evidence
    repository = Path(__file__).resolve().parents[1]
    cli = repository / "scripts" / "audit_q6_2_outcomes.py"
    output = tmp_path / "new_safe_audit"
    # Exists outside the source tree: any attempt to read it is forbidden below.
    (tmp_path / ".env").write_text("API_KEY=ENVIRONMENT_KEY_SENTINEL", encoding="utf-8")
    environment = dict(os.environ)
    environment.update(CONTINUITY_API_KEY="ENVIRONMENT_KEY_SENTINEL", OPENAI_API_KEY="ENVIRONMENT_KEY_SENTINEL")
    program = r'''
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import sys

blocked = (
    "social_sim.decision", "social_sim.provider_runtime", "social_sim.continuity.decision",
    "social_sim.continuity.q6_1", "social_sim.continuity.q6_2_panel",
    "openai", "httpx", "requests", "litellm",
)
class NoProviderImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == prefix or fullname.startswith(prefix + ".") for prefix in blocked):
            raise AssertionError("OFFLINE_PROVIDER_IMPORT_FORBIDDEN")
sys.meta_path.insert(0, NoProviderImports())

def no_network_or_credentials(event, arguments):
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto", "socket.bind"}:
        raise AssertionError("OFFLINE_NETWORK_FORBIDDEN")
    if event == "open" and isinstance(arguments[0], (str, bytes, os.PathLike)):
        name = Path(os.fsdecode(arguments[0])).name.lower()
        if name == ".env" or name.startswith(".env.") or "credential" in name:
            raise AssertionError("OFFLINE_CREDENTIAL_FILE_FORBIDDEN")
sys.addaudithook(no_network_or_credentials)
original_read_text = Path.read_text
def safe_read_text(path, *args, **kwargs):
    if path.name == "decision_journal.jsonl":
        raise AssertionError("OFFLINE_RAW_JOURNAL_DECODE_FORBIDDEN")
    return original_read_text(path, *args, **kwargs)
Path.read_text = safe_read_text
original_getitem = os._Environ.__getitem__
def no_environment_key(self, key):
    if key in {"CONTINUITY_API_KEY", "OPENAI_API_KEY"}:
        raise AssertionError("OFFLINE_ENVIRONMENT_KEY_READ_FORBIDDEN")
    return original_getitem(self, key)
os._Environ.__getitem__ = no_environment_key

cli, source, recovery, analysis, output, entrypoint = sys.argv[1:]
spec = importlib.util.spec_from_file_location("offline_outcome_cli", cli)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
if entrypoint == "main":
    result = module.main(["--source-session", source, "--output", output,
                          "--recovery", recovery, "--analysis", analysis, "--verify-integrity"])
    assert result == 0
else:
    audit = module.audit_to_directory(source, output, recovery=recovery, analysis=analysis)
    assert audit["markers"]["NEW_REAL_PROVIDER_REQUESTS"] == 0
    print("AUDIT_STATUS=PASS")
summary = json.loads((Path(output) / "summary.json").read_text())
assert summary["markers"]["NEW_REAL_PROVIDER_REQUESTS"] == 0
assert summary["markers"]["SOURCE_FILES_UNCHANGED"] == "PASS"
assert summary["markers"]["SOURCE_SESSION_VERIFIED"] == "PASS"
assert not any(any(name == prefix or name.startswith(prefix + ".") for prefix in blocked)
               for name in sys.modules)
print("DYNAMIC_OFFLINE_GUARDS=PASS")
'''
    result = subprocess.run([sys.executable, "-c", program, str(cli), str(directory), str(recovery),
                             str(analysis), str(output), entrypoint], cwd=tmp_path, env=environment,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "DYNAMIC_OFFLINE_GUARDS=PASS" in result.stdout
    assert "AUDIT_STATUS=PASS" in result.stdout
    assert "ENVIRONMENT_KEY_SENTINEL" not in result.stdout + result.stderr
    assert source.source_hashes(directory) == before_hashes
    integrity = json.loads((output / "source_integrity.json").read_text(encoding="utf-8"))
    assert integrity["before"] == integrity["after"] == before_hashes
    assert integrity["file_count"] == 297 and integrity["fully_scored_pairs"] == 22
    provenance = json.loads((output / "provenance.json").read_text(encoding="utf-8"))
    assert provenance["protocol_hash"] == source.PROTOCOL_HASH
    assert provenance["execution_commit"] == source.EXECUTION_COMMIT
    assert provenance["session_id"] == "q62-panel-real-v2-01"
    assert all(b"RAW_MODEL_TEXT_SENTINEL" not in path.read_bytes()
               and b"ENVIRONMENT_KEY_SENTINEL" not in path.read_bytes() for path in output.iterdir())
