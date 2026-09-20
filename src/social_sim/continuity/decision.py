"""可替换决策客户端：每个活动最多一次模型请求，活动执行期间零请求。"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from .context import decision_prompt, observe, parse_proposal
from .engine import ContinuityWorld


class ActivityDecisionRunner:
    def __init__(self, world: ContinuityWorld, client, *, max_calls: int = 4,
                 hard_timeout_seconds: float = 60, journal_path: str | Path | None = None):
        if not 1 <= max_calls <= 100 or not 0 < hard_timeout_seconds <= 120:
            raise ValueError("invalid decision budget")
        self.world, self.client = world, client
        self.max_calls, self.timeout = max_calls, hard_timeout_seconds
        self.journal = Path(journal_path) if journal_path is not None else None
        self.calls = world.store.db.execute("SELECT count(*) FROM decision_attempts").fetchone()[0]
        self.records = []

    def _record(self, row: dict) -> None:
        self.records.append(row)
        if self.journal:
            self.journal.parent.mkdir(parents=True, exist_ok=True)
            with self.journal.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
                f.flush()

    async def decide(self, request_id: str, actor_id: int = 1) -> dict:
        if self.world.store.commitment(actor_id):
            return {"status": "COMMITMENT_PRESENT", "application_calls": 0}
        if self.calls >= self.max_calls:
            return {"status": "REQUEST_BUDGET_EXHAUSTED", "application_calls": 0}
        existing = self.world.store.db.execute("SELECT result FROM commands WHERE id=?", (request_id,)).fetchone()
        if existing:
            return {"status": "ALREADY_RECORDED", "result": json.loads(existing[0]), "application_calls": 0}
        attempt = self.world.store.db.execute("SELECT status FROM decision_attempts WHERE id=?", (request_id,)).fetchone()
        if attempt:
            return {"status": "ALREADY_ATTEMPTED", "previous_status": attempt[0], "application_calls": 0}
        system, user = decision_prompt(self.world, actor_id)
        version = self.world.store.actor(actor_id)["version"]
        with self.world.store.transaction():
            claimed = self.world.store.db.execute(
                "INSERT OR IGNORE INTO decision_attempts VALUES(?,?,?)",
                (request_id, "REQUEST_STARTED", "{}"))
            if not claimed.rowcount:
                return {"status": "ALREADY_ATTEMPTED", "application_calls": 0}
        self.calls += 1
        self._record({"request_id": request_id, "status": "REQUEST_STARTED",
                      "minute": self.world.minute, "application_call": self.calls,
                      "prompt_chars": len(system) + len(user)})
        started = time.perf_counter()
        row = {"request_id": request_id, "application_calls": 1,
               "input_tokens": None, "output_tokens": None, "reasoning_tokens": None,
               "provider_model": None, "http_status": None}
        try:
            reply = await asyncio.wait_for(self.client.complete(system, user), timeout=self.timeout)
        except (TimeoutError, asyncio.TimeoutError):
            row["status"] = "PROVIDER_TIMEOUT"
        except Exception:
            row["status"] = "PROVIDER_ERROR"
            metadata = getattr(self.client, "last_metadata", None)
            status = getattr(metadata, "http_status", None)
            if isinstance(status, int) and 100 <= status <= 599:
                row["http_status"] = status
        else:
            for field in ("input_tokens", "output_tokens", "reasoning_tokens"):
                value = getattr(reply, field, None)
                if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                    row[field] = value
            model = getattr(reply, "provider_model", None)
            if isinstance(model, str) and len(model) <= 80 and all(c.isalnum() or c in "-_.:/" for c in model):
                row["provider_model"] = model
            try:
                proposal = parse_proposal(reply.raw_text)
            except (ValueError, TypeError, AttributeError):
                row["status"] = "INVALID_MODEL_OUTPUT"
            else:
                target = proposal["target"]
                allowed = {o["id"] for o in observe(self.world, actor_id)["objects"]}
                allowed.update(("home", "restaurant", "office", "park"))
                if target is not None and target not in allowed:
                    row["status"] = "OUTSIDE_CATALOG"
                else:
                    result = self.world.start(request_id, actor_id, proposal["activity"], target,
                                              expected_version=version)
                    status = "DECISION_ACCEPTED" if result["accepted"] else "RULE_REJECTED"
                    if result.get("commitment_status") == "FAILED":
                        status = "COMMITMENT_FAILED"
                    row.update(status=status, proposal=proposal, result=result)
        row["latency_seconds"] = round(time.perf_counter() - started, 6)
        with self.world.store.transaction():
            self.world.store.db.execute("UPDATE decision_attempts SET status=?,data=? WHERE id=?",
                                        (row["status"], json.dumps(row, ensure_ascii=False), request_id))
        self._record(row)
        return row
