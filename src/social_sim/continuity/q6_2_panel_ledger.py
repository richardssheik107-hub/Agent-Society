"""固定面板的最小调度账本；领域事实仍只来自各 cell 的 world。

注册根由入口固定选择，不能跟随报告的 --output。session 排他创建且不能
重新打开为可写；请求意图占用的预算永不释放。这里只声明本机去重保证，
不声称分布式 exactly-once，也不提供 resume/retry。
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
import threading
from collections.abc import Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .engine import ContinuityWorld
from .models import SCHEMA_VERSION, RuleParameters, canonical_json, digest
from .store import StateStore

LEDGER_SCHEMA = "q62_fixed_panel_ledger_v1"
MAX_CELLS = 48
STAGES = frozenset({
    "CALL_INTENT_REGISTERED", "REQUEST_STARTED", "CLIENT_CALL_STARTED",
    "HTTP_RESPONSE_OBSERVED", "RESPONSE_OBSERVED", "SERVICE_CONTRACT_VALID",
    "STRICT_JSON_VALID", "PARSE_RESULT", "RULE_CHECKED", "DECISION_RECORDED",
    "WORLD_RESULT_COMMITTED", "FAILURE", "FINAL_ROW",
})
_FORBIDDEN_FIELDS = frozenset({
    "prompt", "system_prompt", "user_prompt", "raw_text", "raw_output",
    "completion", "reasoning_content", "hidden_reasoning", "headers",
    "http_headers", "authorization", "api_key", "secret", "exception_body",
    "error_body", "response_body", "request_body",
})


class LedgerError(RuntimeError):
    """Only a fixed diagnostic code is exposed, never supplied data."""


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", value):
        raise ValueError(f"INVALID_{label}")
    if value in {".", ".."}:
        raise ValueError(f"INVALID_{label}")
    return value


def _safe_json(value: Any, depth: int = 0) -> Any:
    """Accept pre-sanitized audit facts, reject raw/provider secret containers.

    Callers remain responsible for whitelist selection of model-derived values:
    target must be a known canonical ID/null/hash, not an arbitrary model string.
    This final storage guard is intentionally not a second provider sanitizer.
    """
    if depth > 30:
        raise ValueError("UNSAFE_AUDIT_DEPTH")
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("UNSAFE_AUDIT_NUMBER")
        return value
    if isinstance(value, str):
        if len(value) > 2048:
            raise ValueError("UNSAFE_AUDIT_STRING")
        return value
    if isinstance(value, Mapping):
        output = {}
        for key, item in value.items():
            if (not isinstance(key, str) or key.lower() in _FORBIDDEN_FIELDS
                    or len(key) > 128):
                raise ValueError("UNSAFE_AUDIT_FIELD")
            output[key] = _safe_json(item, depth + 1)
        return output
    if isinstance(value, (list, tuple)):
        return [_safe_json(item, depth + 1) for item in value]
    raise ValueError("UNSAFE_AUDIT_TYPE")


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _readonly_database(path: Path):
    """mode=ro is essential: StateStore.__init__ would create/migrate tables."""
    resolved = path.resolve(strict=True)
    db = sqlite3.connect(resolved.as_uri() + "?mode=ro", uri=True,
                         isolation_level=None, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    db.execute("BEGIN")
    try:
        yield db
    finally:
        if db.in_transaction:
            db.execute("ROLLBACK")
        db.close()


def _decoded_cells(db: sqlite3.Connection) -> list[dict]:
    cells = []
    for row in db.execute("SELECT * FROM cells ORDER BY ordinal"):
        cells.append({
            "ordinal": row["ordinal"], "cell_id": row["cell_id"],
            "plan": json.loads(row["plan"]), "request_id": row["request_id"],
            "stage": row["stage"],
            "row": json.loads(row["final_row"]) if row["final_row"] else None,
        })
    return cells


def _decoded_evidence(db: sqlite3.Connection) -> list[dict]:
    return [{"seq": row["seq"], "cell_id": row["cell_id"], "stage": row["stage"],
             "recorded_at": row["recorded_at"], "data": json.loads(row["data"])}
            for row in db.execute("SELECT * FROM evidence ORDER BY seq")]


def _rows(cells: list[dict], evidence: list[dict]) -> list[dict]:
    stages: dict[str, set[str]] = {}
    details: dict[str, dict] = {}
    committed: dict[str, dict] = {}
    for event in evidence:
        stages.setdefault(event["cell_id"], set()).add(event["stage"])
        details.setdefault(event["cell_id"], {}).update(event["data"])
        if event["stage"] == "WORLD_RESULT_COMMITTED":
            committed[event["cell_id"]] = event["data"]
    output = []
    for cell in cells:
        if cell["row"] is not None:
            output.append({**cell["plan"], **cell["row"], "cell_id": cell["cell_id"],
                           "request_id": cell["request_id"]})
            continue
        claimed = cell["request_id"] is not None
        observed = stages.get(cell["cell_id"], set())
        known = details.get(cell["cell_id"], {})
        world_result = committed.get(cell["cell_id"])
        http_status = known.get("http_status")
        http_observed = (isinstance(http_status, int) and not isinstance(http_status, bool)
                         and 100 <= http_status <= 599) or known.get(
                             "http_response_observed") is True
        client_attempted = (True if "CLIENT_CALL_STARTED" in observed else
                            None if claimed else False)
        output.append({
            **cell["plan"], **known, **(world_result or {}), "cell_id": cell["cell_id"],
            "request_id": cell["request_id"],
            "status": (world_result.get("status", "UNKNOWN") if world_result is not None
                       else "UNKNOWN" if claimed else "NOT_RUN"),
            "ledger_stage": cell["stage"],
            "intent_registered": claimed,
            "call_intent_registered": claimed,
            "client_call_attempted": client_attempted,
            "http_response_observed": http_observed,
            "request_send_status": ("RESPONSE_OBSERVED" if http_observed else
                                    "UNKNOWN" if claimed else "NOT_RUN"),
            "provider_requests": known.get("provider_requests", None if claimed else 0),
            "application_calls": (1 if "CLIENT_CALL_STARTED" in observed else
                                  None if claimed else 0),
            "missing_evidence": ["FINAL_ROW"] if claimed else [],
            "recovered_world_result": world_result is not None,
        })
    return output


class Ledger:
    """A write handle returned only by an exclusive create_session call."""

    def __init__(self, directory: Path, db: sqlite3.Connection):
        self.dir = directory
        self.path = directory / "session.sqlite3"
        self.db = db
        self._lock = threading.RLock()
        self._closed = False

    @contextmanager
    def _transaction(self):
        with self._lock:
            if self._closed:
                raise LedgerError("SESSION_CLOSED")
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield
                self.db.execute("COMMIT")
            except BaseException:
                if self.db.in_transaction:
                    self.db.execute("ROLLBACK")
                raise

    def _cell(self, cell_id: str) -> sqlite3.Row:
        row = self.db.execute("SELECT * FROM cells WHERE cell_id=?", (cell_id,)).fetchone()
        if row is None:
            raise LedgerError("CELL_NOT_ALLOCATED")
        return row

    def _append(self, cell_id: str, stage: str, data: dict) -> None:
        self.db.execute("INSERT INTO evidence(cell_id,stage,recorded_at,data) VALUES(?,?,?,?)",
                        (cell_id, stage, _utc(), canonical_json(data)))

    def claim(self, cell_id: str) -> str:
        """Reserve permanently before entering client.complete; never refund."""
        with self._transaction():
            cell = self._cell(cell_id)
            if cell["request_id"] is not None or cell["final_row"] is not None:
                raise LedgerError("CELL_ALREADY_CLAIMED_OR_FINISHED")
            count = self.db.execute(
                "SELECT count(*) FROM cells WHERE request_id IS NOT NULL").fetchone()[0]
            if count >= MAX_CELLS:
                raise LedgerError("SESSION_BUDGET_EXHAUSTED")
            session_id = json.loads(self.db.execute(
                "SELECT value FROM meta WHERE key='session_id'").fetchone()[0])
            request_id = "panel:" + digest([session_id, cell_id])
            self.db.execute("UPDATE cells SET request_id=?,stage=? WHERE cell_id=?",
                            (request_id, "CALL_INTENT_REGISTERED", cell_id))
            self._append(cell_id, "CALL_INTENT_REGISTERED", {
                "request_id": request_id, "budget_occupied": 1,
                "session_budget_occupied": count + 1,
            })
            return request_id

    def record(self, cell_id: str, stage: str, data: dict) -> None:
        if stage not in STAGES or stage in {"CALL_INTENT_REGISTERED", "FINAL_ROW"}:
            raise LedgerError("INVALID_EVIDENCE_STAGE")
        safe = _safe_json(data)
        if not isinstance(safe, dict):
            raise ValueError("AUDIT_MAPPING_REQUIRED")
        with self._transaction():
            cell = self._cell(cell_id)
            if cell["request_id"] is None or cell["final_row"] is not None:
                raise LedgerError("CELL_NOT_OPEN_FOR_EVIDENCE")
            if stage == "CLIENT_CALL_STARTED":
                previous = self.db.execute(
                    "SELECT 1 FROM evidence WHERE cell_id=? AND stage=?", (cell_id, stage))
                if previous.fetchone() is not None:
                    raise LedgerError("CELL_CLIENT_CALL_ALREADY_STARTED")
            self._append(cell_id, stage, safe)
            self.db.execute("UPDATE cells SET stage=? WHERE cell_id=?", (stage, cell_id))

    def finish(self, cell_id: str, row: dict) -> None:
        safe = _safe_json(row)
        if not isinstance(safe, dict):
            raise ValueError("AUDIT_MAPPING_REQUIRED")
        if safe.get("cell_id", cell_id) != cell_id:
            raise LedgerError("CELL_ID_MISMATCH")
        with self._transaction():
            cell = self._cell(cell_id)
            if cell["final_row"] is not None:
                raise LedgerError("CELL_ALREADY_FINISHED")
            supplied_id = safe.get("request_id", cell["request_id"])
            if supplied_id != cell["request_id"]:
                raise LedgerError("REQUEST_ID_MISMATCH")
            if cell["request_id"] is None and safe.get("status") != "NOT_RUN":
                raise LedgerError("UNCLAIMED_CELL_RESULT")
            self.db.execute("UPDATE cells SET final_row=?,stage='FINAL_ROW' WHERE cell_id=?",
                            (canonical_json(safe), cell_id))
            self._append(cell_id, "FINAL_ROW", safe)

    @property
    def claimed_count(self) -> int:
        with self._lock:
            return self.db.execute(
                "SELECT count(*) FROM cells WHERE request_id IS NOT NULL").fetchone()[0]

    def rows(self) -> list[dict]:
        with self._lock:
            return _rows(_decoded_cells(self.db), _decoded_evidence(self.db))

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self.db.close()
                self._closed = True

    def __enter__(self) -> Ledger:
        return self

    def __exit__(self, *_args) -> None:
        self.close()


def create_session(registry_root: str | Path, session_id: str, manifest: dict,
                   metadata: dict) -> Ledger:
    """Atomically reserve local identity; existing sessions are not resumable.

    registry_root is a fixed application root, not an output override. Alternate
    roots in tests are dependency injection, not a CLI option.
    """
    session_id = _identifier(session_id, "SESSION_ID")
    safe_manifest, safe_metadata = _safe_json(manifest), _safe_json(metadata)
    if not isinstance(safe_manifest, dict) or not isinstance(safe_metadata, dict):
        raise ValueError("AUDIT_MAPPING_REQUIRED")
    plans = safe_manifest.get("cells")
    if not isinstance(plans, list) or len(plans) != MAX_CELLS:
        raise LedgerError("MANIFEST_REQUIRES_48_CELLS")
    ids = [_identifier(plan.get("cell_id"), "CELL_ID") for plan in plans]
    if len(set(ids)) != MAX_CELLS:
        raise LedgerError("DUPLICATE_CELL_ID")
    root = Path(registry_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    directory = root / session_id
    # This operation is the identity lock. Failed initialization remains reserved
    # instead of deleting evidence and allowing another execution under its ID.
    directory.mkdir(exist_ok=False)
    db = sqlite3.connect(str(directory / "session.sqlite3"), isolation_level=None,
                         timeout=5, check_same_thread=False)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA busy_timeout=5000")
        db.executescript("""
            CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE cells(ordinal INTEGER UNIQUE NOT NULL,
                cell_id TEXT PRIMARY KEY, plan TEXT NOT NULL,
                request_id TEXT UNIQUE, stage TEXT NOT NULL, final_row TEXT);
            CREATE TABLE evidence(seq INTEGER PRIMARY KEY AUTOINCREMENT,
                cell_id TEXT NOT NULL REFERENCES cells(cell_id),
                stage TEXT NOT NULL, recorded_at TEXT NOT NULL, data TEXT NOT NULL);
        """)
        db.execute("BEGIN IMMEDIATE")
        values = {"schema_version": LEDGER_SCHEMA, "session_id": session_id,
                  "manifest": safe_manifest, "manifest_hash": digest(safe_manifest),
                  "metadata": safe_metadata, "created_at": _utc(),
                  "planned_cells": MAX_CELLS, "max_calls": MAX_CELLS,
                  "max_calls_per_cell": 1}
        db.executemany("INSERT INTO meta VALUES(?,?)",
                       [(key, canonical_json(value)) for key, value in values.items()])
        db.executemany("INSERT INTO cells VALUES(?,?,?,NULL,'PLANNED',NULL)",
                       [(index, plan["cell_id"], canonical_json(plan))
                        for index, plan in enumerate(plans, 1)])
        db.execute("COMMIT")
    except BaseException:
        db.close()
        raise
    return Ledger(directory, db)


def read_session(source: str | Path) -> dict:
    """Export source facts only. No provider imports, credentials or mutations."""
    path = Path(source)
    if path.is_dir():
        path = path / "session.sqlite3"
    with _readonly_database(path) as db:
        values = {row["key"]: json.loads(row["value"])
                  for row in db.execute("SELECT * FROM meta")}
        if values.get("schema_version") != LEDGER_SCHEMA:
            raise LedgerError("UNSUPPORTED_LEDGER_SCHEMA")
        if digest(values["manifest"]) != values["manifest_hash"]:
            raise LedgerError("MANIFEST_HASH_MISMATCH")
        cells, evidence = _decoded_cells(db), _decoded_evidence(db)
        if len(cells) != MAX_CELLS:
            raise LedgerError("INCOMPLETE_ALLOCATION")
        plans = values["manifest"].get("cells")
        if not isinstance(plans, list) or len(plans) != MAX_CELLS:
            raise LedgerError("INCOMPLETE_ALLOCATION")
        for index, (cell, plan) in enumerate(zip(cells, plans, strict=True), 1):
            _identifier(cell["cell_id"], "CELL_ID")
            if (cell["ordinal"] != index or cell["plan"] != plan
                    or cell["cell_id"] != plan.get("cell_id")
                    or cell["stage"] not in STAGES | {"PLANNED"}):
                raise LedgerError("ALLOCATION_EVIDENCE_MISMATCH")
            expected_request = "panel:" + digest([values["session_id"], cell["cell_id"]])
            if cell["request_id"] is not None and cell["request_id"] != expected_request:
                raise LedgerError("REQUEST_ID_MISMATCH")
        ids = {cell["cell_id"] for cell in cells}
        if any(event["cell_id"] not in ids or event["stage"] not in STAGES
               for event in evidence):
            raise LedgerError("INVALID_EVIDENCE_STAGE")
        return {**values, "source": str(path.resolve()), "cells": cells,
                "evidence": evidence, "rows": _rows(cells, evidence),
                "claimed_count": sum(cell["request_id"] is not None for cell in cells),
                "read_only": True, "resume_allowed": False}


@contextmanager
def open_readonly_world(source: str | Path):
    """Read adapter reuses existing projections/validation without constructors.

    Neither ContinuityWorld nor StateStore initialization is called: both would
    perform schema/metadata writes. The read-only SQLite connection also rejects
    any accidental domain mutation attempted by the export caller.
    """
    path = Path(source)
    with _readonly_database(path) as db:
        store = object.__new__(StateStore)
        store.path, store.db = str(path), db
        if int(store.meta("schema_version")) != SCHEMA_VERSION:
            raise LedgerError("UNSUPPORTED_WORLD_SCHEMA")
        world = object.__new__(ContinuityWorld)
        world.store = store
        world.parameters = RuleParameters(**json.loads(store.meta("rule_parameters")))
        world._request = ""
        yield world


def read_world(source: str | Path) -> dict:
    """Return durable commands/attempts/events/state; never re-execute actions."""
    with open_readonly_world(source) as world:
        state = world.store.snapshot()
        commands = [{"id": row["id"], "fingerprint": row["fingerprint"],
                     "result": json.loads(row["result"])}
                    for row in world.store.db.execute("SELECT * FROM commands ORDER BY id")]
        attempts = [{"id": row["id"], "status": row["status"],
                     "data": json.loads(row["data"])}
                    for row in world.store.db.execute(
                        "SELECT * FROM decision_attempts ORDER BY id")]
        return {"state": state, "state_hash": digest(state), "commands": commands,
                "decision_attempts": attempts, "events": world.store.events(),
                "read_only": True}
