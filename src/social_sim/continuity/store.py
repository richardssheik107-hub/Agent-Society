"""同事务保存事实、活动状态、幂等请求和领域事件。不是 AS2 的 replay 数据库。"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .models import SCHEMA_VERSION, canonical_json, initial_link


class StateStore:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, isolation_level=None, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS actors(id INTEGER PRIMARY KEY, data TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS objects(id TEXT PRIMARY KEY, data TEXT NOT NULL,
                                            stock INTEGER NOT NULL CHECK(stock>=0),
                                            available INTEGER NOT NULL DEFAULT 1 CHECK(available IN (0,1)));
          CREATE TABLE IF NOT EXISTS aliases(name TEXT PRIMARY KEY, object_id TEXT NOT NULL
                                             REFERENCES objects(id));
          CREATE TABLE IF NOT EXISTS links(actor_id INTEGER NOT NULL REFERENCES actors(id),
              object_id TEXT NOT NULL REFERENCES objects(id), data TEXT NOT NULL,
              PRIMARY KEY(actor_id, object_id));
          CREATE TABLE IF NOT EXISTS commitments(id TEXT PRIMARY KEY,
              actor_id INTEGER NOT NULL REFERENCES actors(id), status TEXT NOT NULL,
              data TEXT NOT NULL);
          CREATE UNIQUE INDEX IF NOT EXISTS one_commitment ON commitments(actor_id)
              WHERE status IN ('ACTIVE','PAUSED');
          CREATE TABLE IF NOT EXISTS commands(id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
                                            result TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS decision_attempts(id TEXT PRIMARY KEY,
              status TEXT NOT NULL, data TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,
              command_id TEXT NOT NULL, minute INTEGER NOT NULL, kind TEXT NOT NULL,
              payload TEXT NOT NULL);
        """)
        with self.transaction():
            self.db.execute("INSERT OR IGNORE INTO meta VALUES('schema_version',?)",
                            (str(SCHEMA_VERSION),))
            if int(self.meta("schema_version")) != SCHEMA_VERSION:
                raise ValueError("unsupported state schema; explicit migration required")
            self.db.execute("INSERT OR IGNORE INTO meta VALUES('minute','0')")

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> StateStore:
        return self

    def __exit__(self, *args) -> None:
        self.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise

    @contextmanager
    def read_snapshot(self):
        """一致的只读事务；SQL 写入被 query_only 拒绝，不靠写后回滚预演。"""
        owned = not self.db.in_transaction
        previous = self.db.execute("PRAGMA query_only").fetchone()[0]
        self.db.execute("PRAGMA query_only=ON")
        try:
            if owned:
                self.db.execute("BEGIN")
            yield
        finally:
            if owned and self.db.in_transaction:
                self.db.execute("ROLLBACK")
            self.db.execute(f"PRAGMA query_only={int(previous)}")

    def meta(self, key: str) -> str:
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        if row is None:
            raise KeyError(key)
        return row[0]

    @property
    def minute(self) -> int:
        return int(self.meta("minute"))

    def set_minute(self, value: int) -> None:
        self.db.execute("UPDATE meta SET value=? WHERE key='minute'", (str(value),))

    def actor(self, actor_id: int) -> dict:
        row = self.db.execute("SELECT data FROM actors WHERE id=?", (actor_id,)).fetchone()
        if row is None:
            raise KeyError("ACTOR_NOT_FOUND")
        return json.loads(row[0])

    def put_actor(self, actor: dict) -> None:
        self.db.execute("UPDATE actors SET data=? WHERE id=?",
                        (canonical_json(actor), actor["actor_id"]))

    def actor_ids(self) -> list[int]:
        return [r[0] for r in self.db.execute("SELECT id FROM actors ORDER BY id")]

    def object(self, object_id: str) -> dict:
        row = self.db.execute("SELECT data,stock,available FROM objects WHERE id=?", (object_id,)).fetchone()
        if row is None:
            raise KeyError("OBJECT_NOT_FOUND")
        return {**json.loads(row[0]), "stock": row[1], "available": bool(row[2])}

    def link(self, actor_id: int, object_id: str) -> dict:
        row = self.db.execute("SELECT data FROM links WHERE actor_id=? AND object_id=?",
                              (actor_id, object_id)).fetchone()
        return json.loads(row[0]) if row else initial_link()

    def put_link(self, actor_id: int, object_id: str, link: dict) -> None:
        self.db.execute("INSERT INTO links VALUES(?,?,?) ON CONFLICT(actor_id,object_id) "
                        "DO UPDATE SET data=excluded.data",
                        (actor_id, object_id, canonical_json(link)))

    def commitment(self, actor_id: int) -> dict | None:
        row = self.db.execute("SELECT data FROM commitments WHERE actor_id=? AND "
                              "status IN ('ACTIVE','PAUSED')", (actor_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def get_commitment(self, commitment_id: str) -> dict:
        row = self.db.execute("SELECT data FROM commitments WHERE id=?", (commitment_id,)).fetchone()
        if row is None:
            raise KeyError("COMMITMENT_NOT_FOUND")
        return json.loads(row[0])

    def put_commitment(self, value: dict) -> None:
        self.db.execute("INSERT INTO commitments VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE "
                        "SET status=excluded.status,data=excluded.data",
                        (value["id"], value["actor_id"], value["status"], canonical_json(value)))

    def emit(self, command: str, kind: str, payload: dict) -> None:
        self.db.execute("INSERT INTO events(command_id,minute,kind,payload) VALUES(?,?,?,?)",
                        (command, self.minute, kind, canonical_json(payload)))

    def events(self, after_seq: int = 0) -> list[dict]:
        return [{**dict(row), "payload": json.loads(row["payload"])} for row in
                self.db.execute("SELECT * FROM events WHERE seq>? ORDER BY seq", (after_seq,))]

    def snapshot(self) -> dict:
        """测试/备份用全量快照；决策上下文不调用此接口。"""
        owned = not self.db.in_transaction
        if owned:
            self.db.execute("BEGIN")
        try:
            data = {"minute": self.minute, "rules": json.loads(self.meta("rule_parameters")),
                    "actors": [self.actor(i) for i in self.actor_ids()],
                    "objects": [self.object(r[0]) for r in self.db.execute("SELECT id FROM objects ORDER BY id")],
                    "links": [{"actor_id": r[0], "object_id": r[1], "state": json.loads(r[2])}
                              for r in self.db.execute("SELECT * FROM links ORDER BY actor_id,object_id")],
                    "commitments": [json.loads(r[0]) for r in
                                    self.db.execute("SELECT data FROM commitments ORDER BY id")]}
        finally:
            if owned:
                self.db.execute("COMMIT")
        return data

    def backup(self, destination: str | Path) -> None:
        """通过 SQLite backup API 复制一致快照；不直接复制正在写入的文件。"""
        path = Path(destination)
        if path.exists():
            raise FileExistsError(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        target = sqlite3.connect(str(path))
        try:
            self.db.backup(target)
        finally:
            target.close()
