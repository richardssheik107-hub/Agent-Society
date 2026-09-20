"""受控高层决策：持久请求预算、失败分类、并发去重和有界上下文。"""
from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path

import httpx

from social_sim.decision.client import ProviderContractError

from .context import decision_prompt, observe
from .context import parse_proposal
from .engine import ContinuityWorld
from .models import identity, integer


class ActivityDecisionRunner:
    def __init__(self, world: ContinuityWorld, client, *, max_calls: int = 4,
                 hard_timeout_seconds: float = 60, journal_path: str | Path | None = None):
        integer(max_calls, "max_calls", 1, 100)
        if not 0 < hard_timeout_seconds <= 120:
            raise ValueError("invalid timeout")
        self.world, self.client = world, client
        self.max_calls, self.timeout = max_calls, hard_timeout_seconds
        self.journal = Path(journal_path) if journal_path is not None else None
        self.calls = self._call_count()
        self.records = []

    def _call_count(self) -> int:
        return self.world.store.db.execute("SELECT count(*) FROM decision_attempts").fetchone()[0]

    def _record(self, row: dict) -> None:
        self.records.append(row)
        if self.journal:
            self.journal.parent.mkdir(parents=True, exist_ok=True)
            with self.journal.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
                stream.flush()

    def _safe_metadata(self, source) -> dict:
        output = {}
        for name in ("input_tokens", "output_tokens", "reasoning_tokens"):
            value = getattr(source, name, None)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                output[name] = value
        status = getattr(source, "http_status", None)
        if isinstance(status, int) and 100 <= status <= 599:
            output["http_status"] = status
        finish_reason = getattr(source, "finish_reason", None)
        if isinstance(finish_reason, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", finish_reason):
            output["finish_reason"] = finish_reason
        model = getattr(source, "provider_model", None)
        if (isinstance(model, str) and re.fullmatch(r"[A-Za-z0-9_.:/-]{1,80}", model)
                and not model.startswith(("sk-", "ark-"))
                and model != getattr(self.client, "_redaction_secret", None)):
            output["provider_model"] = model
        return output

    async def decide(self, request_id: str, actor_id: int = 1) -> dict:
        request_id = identity(request_id)
        integer(actor_id, "actor_id", 1)
        store = self.world.store
        if store.commitment(actor_id):
            return {"status": "COMMITMENT_PRESENT", "application_calls": 0}
        existing = store.db.execute("SELECT result FROM commands WHERE id=?", (request_id,)).fetchone()
        if existing:
            return {"status": "ALREADY_RECORDED", "result": json.loads(existing[0]),
                    "application_calls": 0}
        attempt = store.db.execute("SELECT status FROM decision_attempts WHERE id=?", (request_id,)).fetchone()
        if attempt:
            return {"status": "ALREADY_ATTEMPTED", "previous_status": attempt[0],
                    "application_calls": 0}
        system, user = decision_prompt(self.world, actor_id)
        version = store.actor(actor_id)["version"]
        # 在同一事务内重查预算与请求 ID；多个 runner 不能用各自旧计数超发请求。
        with store.transaction():
            self.calls = self._call_count()
            if self.calls >= self.max_calls:
                return {"status": "REQUEST_BUDGET_EXHAUSTED", "application_calls": 0}
            claimed = store.db.execute(
                "INSERT OR IGNORE INTO decision_attempts VALUES(?,?,?)",
                (request_id, "REQUEST_STARTED", json.dumps({"actor_id": actor_id})))
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
        cancelled = False
        try:
            reply = await asyncio.wait_for(self.client.complete(system, user), timeout=self.timeout)
        except (TimeoutError, httpx.TimeoutException):
            row["status"] = "PROVIDER_TIMEOUT"
        except asyncio.CancelledError:
            row["status"] = "REQUEST_CANCELLED"
            cancelled = True
        except ProviderContractError as error:
            row["status"] = "PROVIDER_CONTRACT_ERROR"
            if re.fullmatch(r"[A-Z0-9_]{1,64}", error.category):
                row["failure_category"] = error.category
            row.update(self._safe_metadata(error.metadata))
        except Exception:
            row["status"] = "PROVIDER_ERROR"
            row.update(self._safe_metadata(getattr(self.client, "last_metadata", None)))
        else:
            row.update(self._safe_metadata(reply))
            try:
                proposal = parse_proposal(reply.raw_text)
            except (ValueError, TypeError, AttributeError):
                row["status"] = "INVALID_MODEL_OUTPUT"
            else:
                target = proposal["target"]
                allowed = {item["id"] for item in observe(self.world, actor_id)["objects"]}
                allowed.update(("home", "restaurant", "office", "park"))
                if target is not None and target not in allowed:
                    row["status"] = "OUTSIDE_CATALOG"
                else:
                    try:
                        result = self.world.start(request_id, actor_id, proposal["activity"], target,
                                                  expected_version=version)
                    except Exception:
                        row["status"] = "ARCHITECTURE_ERROR"
                    else:
                        status = "DECISION_ACCEPTED" if result["accepted"] else "RULE_REJECTED"
                        if result.get("commitment_status") == "FAILED":
                            status = "COMMITMENT_FAILED"
                        row.update(status=status, proposal=proposal, result=result)
        row["latency_seconds"] = round(time.perf_counter() - started, 6)
        with store.transaction():
            store.db.execute("UPDATE decision_attempts SET status=?,data=? WHERE id=?",
                             (row["status"], json.dumps(row, ensure_ascii=False), request_id))
        self._record(row)
        if cancelled:
            raise asyncio.CancelledError
        return row
