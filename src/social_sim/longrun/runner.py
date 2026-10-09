"""Long-horizon decisions, deterministic microsteps, and conservative recovery.

Model output can only start the existing world controller. A durable request
reservation is never refunded or resent; a parsed intent can be resumed without
a model call, and an already committed command is reconciled by fingerprint.
"""
from __future__ import annotations

import asyncio
import json
import time

import httpx

from social_sim.continuity.context import observe
from social_sim.continuity.m2_acquire import parse_m2_proposal
from social_sim.continuity.models import Rejected, canonical_json, digest, integer
from social_sim.provider_runtime.safety import atom, exception_type

from .session import SessionError, _safe_data, _transaction, _world_snapshot


class LongRunRunner:
    def __init__(self, session, client, *, context_builder=None, invariant_checker=None,
                 fault_hook=None, clock=time.monotonic):
        self.session, self.world, self.client = session, session.world, client
        self.config = session.config
        if getattr(client, "mode", None) != self.config.mode:
            raise SessionError("CLIENT_MODE_MISMATCH")
        if self.config.mode == "offline" and getattr(client, "provider_request_count", 0) != 0:
            raise SessionError("OFFLINE_CLIENT_HAS_PROVIDER_REQUESTS")
        if context_builder is None:
            from .context import build_context
            context_builder = build_context
        if invariant_checker is None:
            from .evaluation import check_invariants
            invariant_checker = check_invariants
        self.context_builder = context_builder
        self.invariant_checker = invariant_checker
        self.fault_hook, self.clock = fault_hook, clock

    def _hook(self, stage: str, data: dict):
        if self.fault_hook is not None:
            self.fault_hook(stage, data)

    def _stop(self, reason: str, state="STOPPED_BY_FAILURE"):
        self.session.transition(state, reason)

    def _audit(self):
        return self.invariant_checker(self.world)

    def _state(self):
        """Bounded facts: previous commitments already live in events/requests."""
        with self.world.store.read_snapshot():
            return _world_snapshot(self.session.db, active_only=True)

    def _metadata(self, reply=None):
        data = {"input_tokens": None, "output_tokens": None, "reasoning_tokens": None,
                "provider_model": None, "http_status": None, "http_response_observed": None}
        sources = [getattr(self.client, "last_metadata", None), reply,
                   getattr(self.client, "safe_evidence", {})]
        for source in sources:
            if source is None:
                continue
            getter = source.get if isinstance(source, dict) else lambda key, s=source: getattr(s, key, None)
            for key in ("input_tokens", "output_tokens", "reasoning_tokens"):
                value = getter(key)
                if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                    data[key] = value
            value = getter("http_status")
            if isinstance(value, int) and not isinstance(value, bool) and 100 <= value <= 599:
                data.update(http_status=value, http_response_observed=True)
            for key in ("provider_model", "request_alias", "actual_response_backend",
                        "failure_category", "exception_type", "finish_reason"):
                value = getter(key)
                safe = atom(value, getattr(self.client, "_redaction_secret", None))
                if safe is not None:
                    data[key] = safe
            safe = atom(getter("response_backend"), getattr(self.client, "_redaction_secret", None))
            if safe is not None:
                data["actual_response_backend"] = safe
            count = getter("unknown_field_count")
            if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
                data["unknown_field_count"] = count
            value = getter("latency_seconds")
            if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value < 86400:
                data["latency_seconds"] = value
        return data

    def _finalize(self, request_id: str, status: str, *, recovered=False):
        self.session.record_request(request_id, "FINALIZED", {
            "status": status, "request_send_status": "OBSERVED",
            "recovered_world_result": recovered})
        record = self.session.request(request_id)
        self._hook("FINALIZED", record)
        return record

    def _resolve_proposal(self, proposal: dict) -> dict:
        target = proposal["target"]
        if proposal["activity"] == "TRAVEL":
            if target not in json.loads(self.world.store.meta("locations")):
                raise ValueError("OUTSIDE_CATALOG")
        elif target is not None:
            try:
                target = self.world.resolve(target)
            except Rejected as error:
                raise ValueError("OUTSIDE_CATALOG") from error
            allowed = {obj["id"] for obj in observe(self.world, 1)["objects"]}
            if target not in allowed:
                raise ValueError("OUTSIDE_CATALOG")
        return {"activity": proposal["activity"], "target": target}

    @staticmethod
    def _start_payload(record):
        proposal = record["proposal"]
        return {"op": "start", "actor_id": record["actor_id"],
                "activity": proposal["activity"], "target": proposal["target"],
                "episode": None, "rewatch": False, "expected_version": record["expected_version"]}

    def _commit_proposal(self, record: dict):
        request_id = record["request_id"]
        existing = self.session.db.execute(
            "SELECT fingerprint,result FROM commands WHERE id=?", (request_id,)).fetchone()
        recovered = existing is not None
        if existing:
            if existing[0] != digest(self._start_payload(record)):
                raise SessionError("REQUEST_ID_REUSE")
            result = json.loads(existing[1])
        else:
            if self.session.charge_wall() >= self.config.max_wall_seconds:
                self._stop("WALL_CLOCK_LIMIT", "STOPPED_BY_BUDGET")
                return None
            proposal = record["proposal"]
            result = self.world.start(request_id, record["actor_id"], proposal["activity"],
                                      proposal["target"], expected_version=record["expected_version"])
            # Deliberately before the session write: recovery must discover world commit.
            self._hook("WORLD_EFFECT_COMMITTED", {"request_id": request_id, "result": result})
        invariants = self._audit()
        self.session.record_request(request_id, "WORLD_COMMITTED", {
            "result": result, "invariants": invariants,
            "after_state": self._state(), "recovered_world_result": recovered})
        self._hook("WORLD_COMMITTED", self.session.request(request_id))
        status = "DECISION_ACCEPTED" if result["accepted"] else "RULE_REJECTED"
        if result.get("commitment_status") == "FAILED":
            status = "COMMITMENT_FAILED"
        return self._finalize(request_id, status, recovered=recovered)

    def _recover_requests(self):
        for record in self.session.pending_requests():
            if record["phase"] in {"REQUEST_REGISTERED", "RESPONSE_OBSERVED"}:
                # Safe envelope evidence does not contain the raw output. It cannot
                # establish a valid proposal, and never authorizes another call.
                self._stop("UNCERTAIN_REQUEST_STATE", "RECOVERY_REQUIRED")
                return False
            if record["phase"] == "PROPOSAL_PARSED":
                if self._commit_proposal(record) is None:
                    return False
            elif record["phase"] == "WORLD_COMMITTED":
                result = record["result"]
                status = "DECISION_ACCEPTED" if result["accepted"] else "RULE_REJECTED"
                if result.get("commitment_status") == "FAILED":
                    status = "COMMITMENT_FAILED"
                self._finalize(record["request_id"], status, recovered=True)
        return True

    async def _decide(self):
        try:
            with self.world.store.read_snapshot():
                system, user, metrics = self.context_builder(self.world, self.config)
                version = self.world.store.actor(1)["version"]
                before = self._state()
        except ValueError:
            self._stop("CONTEXT_BUDGET_EXCEEDED")
            return None
        remaining_wall = self.config.max_wall_seconds - self.session.charge_wall()
        if remaining_wall <= 0:
            self._stop("WALL_CLOCK_LIMIT", "STOPPED_BY_BUDGET")
            return None
        try:
            record = self.session.register_request(version, metrics)
        except SessionError as error:
            if str(error) != "REQUEST_BUDGET_REACHED":
                raise
            self._stop("REQUEST_BUDGET_REACHED", "STOPPED_BY_BUDGET")
            return None
        request_id = record["request_id"]
        self._hook("REQUEST_REGISTERED", record)
        self.session.record_request(request_id, "REQUEST_REGISTERED", {
            "application_calls": 1, "before_state": before})
        started = self.clock()
        provider_before = getattr(self.client, "provider_request_count", None)
        try:
            reply = await asyncio.wait_for(self.client.complete(system, user),
                timeout=min(self.config.request_timeout_seconds, remaining_wall))
        except asyncio.CancelledError:
            self.session.record_request(request_id, "REQUEST_REGISTERED", {
                "exception_type": "CancelledError", "interruption_reason": "USER_INTERRUPTED"})
            self._stop("USER_INTERRUPTED", "PAUSED")
            raise
        except Exception as error:
            metadata = self._metadata()
            provider_after = getattr(self.client, "provider_request_count", None)
            if isinstance(provider_before, int) and isinstance(provider_after, int):
                metadata["provider_requests"] = max(0, provider_after - provider_before)
            timeout = isinstance(error, (TimeoutError, httpx.TimeoutException))
            category = metadata.get("failure_category")
            reason = "PROVIDER_TIMEOUT" if timeout else "PROVIDER_ERROR"
            if timeout and remaining_wall <= self.config.request_timeout_seconds:
                reason = "WALL_CLOCK_LIMIT"
            if category == "INVALID_MODEL_OUTPUT":
                reason = category
            metadata.update(exception_type=exception_type(error),
                            latency_seconds=max(0.0, self.clock() - started))
            if metadata["http_response_observed"] is True:
                self.session.record_request(request_id, "RESPONSE_OBSERVED", metadata)
                self._finalize(request_id, reason)
            else:
                self.session.record_request(request_id, "REQUEST_REGISTERED", {
                    **metadata, "interruption_reason": reason})
            self._stop(reason, "STOPPED_BY_BUDGET" if reason == "WALL_CLOCK_LIMIT"
                       else "STOPPED_BY_FAILURE")
            return None
        metadata = self._metadata(reply)
        metadata.update(latency_seconds=max(0.0, self.clock() - started),
                        service_contract_valid=isinstance(getattr(reply, "raw_text", None), str),
                        provider_requests=getattr(reply, "provider_request_count", None))
        if self.config.mode == "offline":
            metadata["provider_requests"] = 0
        self.session.record_request(request_id, "RESPONSE_OBSERVED", metadata)
        self._hook("RESPONSE_OBSERVED", self.session.request(request_id))
        try:
            proposal = parse_m2_proposal(reply.raw_text)
            proposal = self._resolve_proposal(proposal)
        except (ValueError, TypeError, AttributeError):
            return self._finalize(request_id, "INVALID_MODEL_OUTPUT")
        self.session.record_request(request_id, "PROPOSAL_PARSED", {
            "proposal": proposal, "strict_json_valid": True, "catalog_valid": True})
        self._hook("PROPOSAL_PARSED", self.session.request(request_id))
        return self._commit_proposal(self.session.request(request_id))

    def _reconcile_step(self, command_id: str, data: dict):
        existing = self.session.db.execute(
            "SELECT fingerprint,result FROM commands WHERE id=?", (command_id,)).fetchone()
        expected = digest({"op": "advance", "to_minute": data["to_minute"]})
        if existing:
            if existing[0] != expected:
                raise SessionError("REQUEST_ID_REUSE")
            result = json.loads(existing[1])
        else:
            if self.session.charge_wall() >= self.config.max_wall_seconds:
                self._stop("WALL_CLOCK_LIMIT", "STOPPED_BY_BUDGET")
                return False
            result = self.world.advance(command_id, data["to_minute"])
        self._hook("MICRO_WORLD_COMMITTED", {"command_id": command_id, "result": result})
        if not result["accepted"]:
            raise SessionError("MICRO_STEP_REJECTED")
        data.update(after_state=self._state(), invariants=self._audit(),
                    event_seq_to=self.session.db.execute(
                        "SELECT coalesce(max(seq),0) FROM events").fetchone()[0],
                    actual_to_minute=self.world.minute)
        _safe_data(data)
        with _transaction(self.session.db):
            self.session.db.execute("UPDATE m5_steps SET status='COMMITTED',data=? WHERE id=?",
                                    (canonical_json(data), command_id))
            saved = self.session.load()
            saved["micro_steps"] += 1
            if self.world.minute > data["from_minute"]:
                saved["no_progress"] = 0
            self.session.db.execute("UPDATE m5_session SET data=? WHERE id=1", (canonical_json(saved),))
        self._hook("MICRO_STEP_COMMITTED", {"command_id": command_id, **data})
        c = self.world.store.get_commitment(data["commitment_id"])
        if c["status"] == "FAILED":
            self._stop("COMMITMENT_FAILED")
            return False
        return True

    def _recover_steps(self):
        pending = list(self.session.db.execute(
            "SELECT id,data FROM m5_steps WHERE status='REGISTERED' ORDER BY ordinal"))
        for row in pending:
            if not self._reconcile_step(row[0], json.loads(row[1])):
                return False
        return True

    def _advance(self, commitment: dict):
        db = self.session.db
        count = db.execute("SELECT count(*) FROM m5_steps WHERE json_extract(data,'$.commitment_id')=?",
                           (commitment["id"],)).fetchone()[0]
        if count >= self.config.max_micro_steps:
            self._stop("MICRO_STEP_BUDGET_REACHED", "STOPPED_BY_BUDGET")
            return False
        minute = self.world.minute
        horizon = self.session.load()["horizon_minute"]
        midnight = ((minute // 1440) + 1) * 1440
        to_minute = min(minute + min(commitment["remaining_min"], self.config.step_minutes),
                        horizon, midnight)
        data = {"commitment_id": commitment["id"], "activity": commitment["activity"],
                "phase": commitment["phase"], "from_minute": minute, "to_minute": to_minute,
                "before_state": self._state(), "event_seq_from": db.execute(
                    "SELECT coalesce(max(seq),0) FROM events").fetchone()[0]}
        command_id = "m5-tick:" + digest({"commitment": commitment, "minute": minute,
                                          "to_minute": to_minute})
        with _transaction(db):
            ordinal = db.execute("SELECT count(*) FROM m5_steps").fetchone()[0] + 1
            db.execute("INSERT INTO m5_steps VALUES(?,?,'REGISTERED',?)",
                       (command_id, ordinal, canonical_json(data)))
        self._hook("MICRO_STEP_REGISTERED", {"command_id": command_id, **data})
        return self._reconcile_step(command_id, data)

    def _checkpoint_boundary(self):
        minute = self.world.minute
        if minute and minute % 1440 == 0 and not self.session.db.execute(
                "SELECT 1 FROM m5_checkpoints WHERE minute=?", (minute,)).fetchone():
            checkpoint = self.session.checkpoint()
            self._hook("CHECKPOINTED", checkpoint)
            self._export_daily(checkpoint)

    def _export_daily(self, checkpoint):
        from .reporting import export_daily_checkpoint
        receipt = export_daily_checkpoint(self.session, checkpoint)
        self._hook("DAILY_REPORT_WRITTEN", receipt)

    def _recover_daily_reports(self):
        """A checkpoint's missing report is recoverable without another world effect."""
        rows = self.session.db.execute("SELECT data FROM m5_checkpoints ORDER BY minute").fetchall()
        for row in rows:
            checkpoint = json.loads(row[0])
            if checkpoint.get("kind") == "DAILY":
                self._export_daily(checkpoint)

    def _account_decision(self, record):
        saved = self.session.load()
        if saved["no_progress"] >= self.config.max_no_progress:
            self._stop("NO_SIMULATION_PROGRESS")
            return False
        if saved["consecutive_errors"] >= self.config.max_consecutive_errors:
            self._stop(record["status"])
            return False
        return True

    async def run(self, max_steps: int | None = None) -> dict:
        """Run until horizon/budget/failure. max_steps pauses without changing activities."""
        if max_steps is not None:
            integer(max_steps, "max_steps", 1)
        self.session.begin_wall(self.clock)
        steps = 0
        summary = None
        try:
            saved = self.session.load()
            self._audit()
            self._recover_daily_reports()
            if saved["state"] == "COMPLETED":
                summary = self.session.summary()
                return summary
            self.session.transition("RUNNING")
            if not self._recover_requests() or not self._recover_steps():
                summary = self.session.summary()
                return summary
            self._checkpoint_boundary()
            while True:
                saved = self.session.load()
                if self.world.minute >= saved["horizon_minute"]:
                    self._stop("SIMULATION_HORIZON_REACHED", "COMPLETED")
                    break
                if self.session.charge_wall() >= self.config.max_wall_seconds:
                    self._stop("WALL_CLOCK_LIMIT", "STOPPED_BY_BUDGET")
                    break
                if max_steps is not None and steps >= max_steps:
                    self._stop("USER_INTERRUPTED", "PAUSED")
                    break
                if saved["no_progress"] >= self.config.max_no_progress:
                    self._stop("NO_SIMULATION_PROGRESS")
                    break
                if saved["consecutive_errors"] >= self.config.max_consecutive_errors:
                    self._stop("REPEATED_DECISION_FAILURE")
                    break
                commitment = self.world.store.commitment(1)
                if commitment:
                    self.session.transition("COMMITMENT_ACTIVE")
                    if commitment["status"] == "PAUSED":
                        self._stop("USER_INTERRUPTED", "PAUSED")
                        break
                    if not self._advance(commitment):
                        break
                    steps += 1
                    self._checkpoint_boundary()
                else:
                    record = await self._decide()
                    if record is None:
                        break
                    if not self._account_decision(record):
                        break
            summary = self.session.summary()
            return summary
        except AssertionError:
            self._stop("INVARIANT_FAILED")
            summary = self.session.summary()
            return summary
        except (KeyboardInterrupt, asyncio.CancelledError):
            self._stop("USER_INTERRUPTED", "PAUSED")
            raise
        except BaseException:
            self._stop("RUNTIME_INTERRUPTED", "RECOVERY_REQUIRED")
            raise
        finally:
            elapsed = self.session.charge_wall(finish=True)
            if summary is not None:
                summary["wall_seconds"] = elapsed
