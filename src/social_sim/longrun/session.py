"""Durable M5 session bookkeeping alongside the unchanged continuity world.

The lock is held for the whole writable session. Read-only export opens SQLite
with mode=ro and never constructs StateStore or ContinuityWorld.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from pathlib import Path

from social_sim.continuity.engine import ContinuityWorld
from social_sim.continuity.models import canonical_json, digest


SESSION_VERSION = "M5_LONGRUN_SESSION_V1"
SESSION_STATES = frozenset({
    "CREATED", "RUNNING", "COMMITMENT_ACTIVE", "CHECKPOINTED", "PAUSED", "COMPLETED",
    "STOPPED_BY_BUDGET", "STOPPED_BY_FAILURE", "RECOVERY_REQUIRED",
})
REQUEST_PHASES = ("REQUEST_REGISTERED", "RESPONSE_OBSERVED", "PROPOSAL_PARSED",
                  "WORLD_COMMITTED", "FINALIZED")


class SessionError(RuntimeError):
    """A session cannot safely be opened, resumed, or changed."""


def _safe_data(value):
    """Reject sensitive payload keys before any audit write."""
    forbidden = {"raw_text", "raw_completion", "completion", "reasoning_content", "headers",
                 "authorization", "api_key", "apikey", "secret", "prompt", "exception_body",
                 "system_prompt", "user_prompt", "env_file", "endpoint", "base_url"}
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or key.casefold() in forbidden:
                raise ValueError("UNSAFE_AUDIT_FIELD")
            _safe_data(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _safe_data(item)
    canonical_json(value)
    return value


def _config_dict(config) -> dict:
    if is_dataclass(config):
        return asdict(config)
    if hasattr(config, "to_dict"):
        return config.to_dict()
    raise TypeError("LongRunConfig required")


@contextmanager
def _transaction(db):
    db.execute("BEGIN IMMEDIATE")
    try:
        yield
        db.execute("COMMIT")
    except BaseException:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise


class _SessionLock:
    def __init__(self, path: Path):
        self.file = path.open("a+b")
        try:
            if os.name == "nt":
                import msvcrt
                if self.file.seek(0, 2) == 0:
                    self.file.write(b"0")
                    self.file.flush()
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError) as error:
            self.file.close()
            raise SessionError("SESSION_ALREADY_RUNNING") from error

    def close(self):
        if self.file.closed:
            return
        try:
            if os.name == "nt":
                import msvcrt
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
        finally:
            self.file.close()


def _world_snapshot(db, *, active_only=False) -> dict:
    def meta(key):
        return db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()[0]
    return {
        "minute": int(meta("minute")), "rules": json.loads(meta("rule_parameters")),
        "actors": [json.loads(r[0]) for r in db.execute("SELECT data FROM actors ORDER BY id")],
        "objects": [{**json.loads(r[0]), "stock": r[1], "available": bool(r[2])}
                    for r in db.execute("SELECT data,stock,available FROM objects ORDER BY id")],
        "links": [{"actor_id": r[0], "object_id": r[1], "state": json.loads(r[2])}
                  for r in db.execute("SELECT actor_id,object_id,data FROM links ORDER BY actor_id,object_id")],
        "commitments": [json.loads(r[0]) for r in db.execute(
            "SELECT data FROM commitments "
            + ("WHERE status IN ('ACTIVE','PAUSED') " if active_only else "") + "ORDER BY id")],
    }


def _export(db) -> dict:
    saved = json.loads(db.execute("SELECT data FROM m5_session WHERE id=1").fetchone()[0])
    requests = [{"request_id": r[0], "phase": r[1], **json.loads(r[2])}
                for r in db.execute("SELECT id,phase,data FROM m5_requests ORDER BY ordinal")]
    steps = [{"command_id": r[0], "status": r[1], **json.loads(r[2])}
             for r in db.execute("SELECT id,status,data FROM m5_steps ORDER BY ordinal")]
    receipts = [{"seq": r[0], "request_id": r[1], "stage": r[2], "data": json.loads(r[3])}
                for r in db.execute("SELECT seq,request_id,stage,data FROM m5_receipts ORDER BY seq")]
    events = [{**dict(r), "payload": json.loads(r["payload"])}
              for r in db.execute("SELECT * FROM events ORDER BY seq")]
    step_counts = {}
    for step in steps:
        if step["status"] == "COMMITTED":
            cid = step["commitment_id"]
            step_counts[cid] = step_counts.get(cid, 0) + 1
    commitments = {r[0]: json.loads(r[1]) for r in db.execute("SELECT id,data FROM commitments")}
    for request in requests:
        cid = request["request_id"]
        request["micro_steps"] = step_counts.get(cid, 0)
        if cid in commitments:
            request.update(activity_status=commitments[cid]["status"],
                           activity_elapsed_minutes=commitments[cid]["elapsed_min"],
                           activity_failure_reason=commitments[cid]["failure_reason"])
    return {
        "manifest": saved["manifest"], "metadata": saved["provenance"], "session": saved,
        "requests": requests, "receipts": receipts, "steps": steps,
        "checkpoints": [json.loads(r[0]) for r in
                        db.execute("SELECT data FROM m5_checkpoints ORDER BY minute")],
        "world": _world_snapshot(db), "events": events,
        "commands": [{"id": r[0], "fingerprint": r[1], "result": json.loads(r[2])}
                     for r in db.execute("SELECT id,fingerprint,result FROM commands ORDER BY id")],
    }


class LongRunSession:
    """A unique world and its immutable request allocation and recoverable receipts."""
    def __init__(self, directory: Path, world: ContinuityWorld, lock: _SessionLock, config):
        self.dir = directory
        self.path = directory / "world.sqlite3"
        self.world, self.db, self.config = world, world.store.db, config
        self._lock = lock
        self._closed = False
        self._wall_clock = None
        self._wall_last = None

    @classmethod
    def create(cls, root, session_id: str, config, provenance: dict, *, seed_world=None):
        if (not isinstance(session_id, str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", session_id)):
            raise ValueError("INVALID_SESSION_ID")
        frozen = _config_dict(config)
        _safe_data(provenance)
        protocol_hash = getattr(config, "protocol_hash", None)
        if callable(protocol_hash):
            protocol_hash = protocol_hash()
        if protocol_hash is None:
            protocol_hash = digest(frozen)
        if config.mode == "real":
            auth = provenance.get("execution_authorization", {})
            acceptance = auth.get("acceptance", {})
            policy = auth.get("request_policy", {})
            if (auth.get("authorization_type") != "EXPLICIT_USER_SESSION_AUTHORIZATION"
                    or auth.get("approved") is not True or auth.get("session_id") != session_id
                    or not isinstance(auth.get("max_provider_requests"), int)
                    or isinstance(auth.get("max_provider_requests"), bool)
                    or auth.get("max_provider_requests", 0) < config.max_provider_requests
                    or auth.get("protocol_hash") != protocol_hash
                    or auth.get("execution_commit") != provenance.get("execution_commit")
                    or acceptance.get("execution_commit") != provenance.get("execution_commit")
                    or acceptance.get("result") != "PASS"
                    or policy.get("retry") is not False or policy.get("fallback") is not False
                    or auth.get("resume") is not False
                    or config.max_provider_requests <= 0):
                raise SessionError("REAL_EXECUTION_NOT_AUTHORIZED")
        directory = Path(root).resolve() / session_id
        directory.mkdir(parents=True, exist_ok=False)
        lock = _SessionLock(directory / ".session.lock")
        world = None
        try:
            world = ContinuityWorld(directory / "world.sqlite3",
                                    acquire_enabled=config.acquire_enabled)
            if seed_world is None:
                from .policy import seed_world
            seed_world(world, config)
            world.store.db.executescript("""
              CREATE TABLE m5_session(id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL);
              CREATE TABLE m5_requests(id TEXT PRIMARY KEY, ordinal INTEGER UNIQUE NOT NULL,
                phase TEXT NOT NULL, data TEXT NOT NULL);
              CREATE TABLE m5_receipts(seq INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL, stage TEXT NOT NULL, data TEXT NOT NULL);
              CREATE TABLE m5_steps(id TEXT PRIMARY KEY, ordinal INTEGER UNIQUE NOT NULL,
                status TEXT NOT NULL, data TEXT NOT NULL);
              CREATE TABLE m5_checkpoints(minute INTEGER PRIMARY KEY, data TEXT NOT NULL);
            """)
            initial = world.store.snapshot()
            saved = {
                "schema": SESSION_VERSION, "session_id": session_id, "state": "CREATED",
                "stop_reason": None, "manifest": {"protocol_version": SESSION_VERSION,
                    "protocol_hash": protocol_hash, "config": frozen},
                "provenance": provenance, "initial_state": initial,
                "initial_state_hash": digest(initial), "initial_minute": world.minute,
                "horizon_minute": world.minute + config.sim_days * 1440,
                "decisions": 0, "provider_requests_reserved": 0, "micro_steps": 0,
                "wall_seconds": 0.0, "wall_last_epoch": None,
                "consecutive_errors": 0, "no_progress": 0, "resume_count": 0,
            }
            with world.store.transaction():
                world.store.db.execute("INSERT INTO m5_session VALUES(1,?)", (canonical_json(saved),))
                world.store.db.execute("INSERT INTO m5_checkpoints VALUES(?,?)", (world.minute,
                    canonical_json({"kind": "INITIAL", "minute": world.minute, "day": 0,
                                    "state": initial, "state_hash": digest(initial)})))
            return cls(directory, world, lock, config)
        except BaseException:
            if world is not None:
                world.close()
            lock.close()
            raise

    @classmethod
    def open(cls, session_dir, *, resume: bool = False):
        if not resume:
            raise SessionError("EXPLICIT_RESUME_REQUIRED")
        directory = Path(session_dir).resolve()
        path = directory / "world.sqlite3"
        if not path.is_file():
            raise FileNotFoundError(path)
        lock = _SessionLock(directory / ".session.lock")
        world = None
        try:
            with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
                saved = json.loads(db.execute("SELECT data FROM m5_session WHERE id=1").fetchone()[0])
            if saved.get("schema") != SESSION_VERSION:
                raise SessionError("UNSUPPORTED_SESSION_PROTOCOL")
            from .config import LongRunConfig
            frozen = dict(saved["manifest"]["config"])
            config = LongRunConfig.from_dict(frozen)
            if config.protocol_hash != saved["manifest"]["protocol_hash"]:
                raise SessionError("SESSION_PROTOCOL_HASH_MISMATCH")
            world = ContinuityWorld(path, acquire_enabled=config.acquire_enabled)
            session = cls(directory, world, lock, config)
            # A crashed process may not have charged its last interval. Conservatively
            # include it, rather than allowing restarts to replenish the wall budget.
            if saved.get("wall_last_epoch") is not None:
                saved["wall_seconds"] += max(0.0, time.time() - saved["wall_last_epoch"])
                saved["wall_last_epoch"] = None
            saved["resume_count"] += 1
            session.save(saved)
            return session
        except BaseException:
            if world is not None:
                world.close()
            lock.close()
            raise

    @staticmethod
    def export_only(session_dir) -> dict:
        path = Path(session_dir).resolve() / "world.sqlite3"
        if not path.is_file():
            raise FileNotFoundError(path)
        db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            return _export(db)
        finally:
            if db.in_transaction:
                db.execute("ROLLBACK")
            db.close()

    def load(self) -> dict:
        return json.loads(self.db.execute("SELECT data FROM m5_session WHERE id=1").fetchone()[0])

    def save(self, value: dict):
        _safe_data(value)
        with _transaction(self.db):
            self.db.execute("UPDATE m5_session SET data=? WHERE id=1", (canonical_json(value),))

    def transition(self, state: str, reason=None):
        if state not in SESSION_STATES:
            raise ValueError("INVALID_SESSION_STATE")
        data = self.load()
        data.update(state=state, stop_reason=reason)
        self.save(data)

    def begin_wall(self, clock):
        if self._wall_last is not None:
            raise SessionError("RUN_ALREADY_ACTIVE")
        self._wall_clock = clock
        self._wall_last = clock()
        data = self.load()
        data["wall_last_epoch"] = time.time()
        self.save(data)

    def charge_wall(self, *, finish=False):
        if self._wall_last is None:
            return self.load()["wall_seconds"]
        now = self._wall_clock()
        data = self.load()
        data["wall_seconds"] += max(0.0, now - self._wall_last)
        data["wall_last_epoch"] = None if finish else time.time()
        self.save(data)
        self._wall_last = None if finish else now
        return data["wall_seconds"]

    def register_request(self, version: int, metrics: dict, *, actor_id: int = 1) -> dict:
        _safe_data(metrics)
        with _transaction(self.db):
            data = self.load()
            if data["decisions"] >= self.config.max_decisions:
                raise SessionError("REQUEST_BUDGET_REACHED")
            real = self.config.mode == "real"
            if real and data["provider_requests_reserved"] >= self.config.max_provider_requests:
                raise SessionError("REQUEST_BUDGET_REACHED")
            ordinal = data["decisions"] + 1
            request_id = f"m5:{data['session_id']}:{ordinal:06d}"
            record = {"ordinal": ordinal, "actor_id": actor_id, "expected_version": version,
                "minute": self.world.minute, "status": "UNKNOWN", "request_send_status": "UNKNOWN",
                "context": metrics, "input_tokens": None, "output_tokens": None,
                "reasoning_tokens": None, "provider_model": None, "http_status": None,
                "application_calls": None, "provider_requests": None if real else 0,
                "provider_requests_reserved": 1 if real else 0,
                "micro_steps": 0, "proposal": None, "result": None}
            self.db.execute("INSERT INTO m5_requests VALUES(?,?,?,?)",
                (request_id, ordinal, "REQUEST_REGISTERED", canonical_json(record)))
            self.db.execute("INSERT INTO m5_receipts(request_id,stage,data) VALUES(?,?,?)",
                (request_id, "REQUEST_REGISTERED", canonical_json(record)))
            data["decisions"] = ordinal
            data["provider_requests_reserved"] += int(real)
            self.db.execute("UPDATE m5_session SET data=? WHERE id=1", (canonical_json(data),))
        return {"request_id": request_id, "phase": "REQUEST_REGISTERED", **record}

    def request(self, request_id: str) -> dict:
        row = self.db.execute("SELECT phase,data FROM m5_requests WHERE id=?", (request_id,)).fetchone()
        if row is None:
            raise KeyError(request_id)
        return {"request_id": request_id, "phase": row[0], **json.loads(row[1])}

    def record_request(self, request_id: str, phase: str, update: dict):
        if phase not in REQUEST_PHASES:
            raise ValueError("INVALID_REQUEST_PHASE")
        _safe_data(update)
        with _transaction(self.db):
            record = self.request(request_id)
            previous = record.pop("phase")
            record.pop("request_id")
            if previous == "FINALIZED":
                raise SessionError("REQUEST_ALREADY_FINALIZED")
            if REQUEST_PHASES.index(phase) < REQUEST_PHASES.index(previous):
                raise SessionError("REQUEST_PHASE_REVERSAL")
            record.update(update)
            self.db.execute("UPDATE m5_requests SET phase=?,data=? WHERE id=?",
                            (phase, canonical_json(record), request_id))
            self.db.execute("INSERT INTO m5_receipts(request_id,stage,data) VALUES(?,?,?)",
                            (request_id, phase, canonical_json(update)))
            if phase == "FINALIZED":
                saved = self.load()
                failed = record["status"] != "DECISION_ACCEPTED"
                saved["consecutive_errors"] = saved["consecutive_errors"] + 1 if failed else 0
                saved["no_progress"] += 1
                self.db.execute("UPDATE m5_session SET data=? WHERE id=1", (canonical_json(saved),))

    def pending_requests(self):
        return [self.request(r[0]) for r in self.db.execute(
            "SELECT id FROM m5_requests WHERE phase!='FINALIZED' ORDER BY ordinal")]

    def checkpoint(self, kind="DAILY") -> dict:
        with self.world.store.read_snapshot():
            state = _world_snapshot(self.db, active_only=True)
        minute = self.world.minute
        initial = self.load()["initial_minute"]
        data = {"kind": kind, "minute": minute, "day": (minute - initial) // 1440,
                "state": state, "state_hash": digest(state),
                "event_seq": self.db.execute("SELECT coalesce(max(seq),0) FROM events").fetchone()[0]}
        with _transaction(self.db):
            self.db.execute("INSERT OR IGNORE INTO m5_checkpoints VALUES(?,?)",
                            (minute, canonical_json(data)))
        self.transition("CHECKPOINTED")
        return data

    def export_data(self) -> dict:
        self.db.execute("BEGIN")
        try:
            return _export(self.db)
        finally:
            self.db.execute("ROLLBACK")

    def summary(self) -> dict:
        data = self.load()
        return {"session_id": data["session_id"], "state": data["state"],
            "stop_reason": data["stop_reason"], "simulation_minutes": self.world.minute - data["initial_minute"],
            "simulation_days": (self.world.minute - data["initial_minute"]) / 1440,
            "minute": self.world.minute, "horizon_minute": data["horizon_minute"],
            "decisions": data["decisions"], "provider_requests_reserved": data["provider_requests_reserved"],
            "micro_steps": data["micro_steps"], "wall_seconds": data["wall_seconds"],
            "resume_count": data["resume_count"], "active_commitment": self.world.store.commitment(1),
            "result_class": "REAL_MODEL_AUTONOMOUS_LONG_RUN" if self.config.mode == "real"
                            else "SCRIPTED_OR_FAKE_LONG_RUN"}

    def close(self):
        if self._closed:
            return
        try:
            self.charge_wall(finish=True)
        finally:
            try:
                self.world.close()
            finally:
                self._lock.close()
                self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
