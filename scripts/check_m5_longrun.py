#!/usr/bin/env python3
"""实际执行新 M5 Runtime 7/30 日与多次重启对照；全部为合成离线证据。"""
# ruff: noqa: E402 -- standalone source path
from __future__ import annotations

import argparse
import asyncio
import json
import platform
import re
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from social_sim.continuity.models import digest
from social_sim.longrun.config import LongRunConfig
from social_sim.longrun.evaluation import check_invariants_full
from social_sim.longrun.policy import FakeLongRunPolicy
from social_sim.longrun.reporting import export_reports
from social_sim.longrun.runner import LongRunRunner
from social_sim.longrun.session import LongRunSession
from social_sim.provider_runtime.safety import write_json


@contextmanager
def offline_network_guard():
    def refused(*args, **kwargs):
        raise RuntimeError("M5_OFFLINE_NETWORK_FORBIDDEN")
    with (patch.object(socket.socket, "connect", refused),
          patch.object(socket.socket, "connect_ex", refused),
          patch.object(socket, "create_connection", refused),
          patch.object(socket, "getaddrinfo", refused)):
        yield


def memory_sample() -> dict:
    """Observe Linux RSS and process peak, rather than claiming infinite bounds."""
    data = {"rss_kib": None, "peak_rss_kib": None, "source": "NOT_AVAILABLE"}
    try:
        import resource
        data["peak_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        data["source"] = "LINUX_PROC_STATUS_AND_GETRUSAGE" if sys.platform == "linux" else "GETRUSAGE_PLATFORM_DEPENDENT"
        if sys.platform == "linux":
            for line in Path("/proc/self/status").read_text().splitlines():
                if line.startswith("VmRSS:"):
                    data["rss_kib"] = int(line.split()[1])
    except (ImportError, OSError, ValueError):
        pass
    return data


def semantic_evidence(data: dict) -> dict:
    """Compare facts and event order, not session labels, API timing or resume count."""
    own = data["session"]["session_id"]
    prefix = "m5:" + own + ":"
    def normalize(value):
        if isinstance(value, str) and value.startswith(prefix):
            return "m5:<SESSION>:" + value[len(prefix):]
        if isinstance(value, dict):
            return {key: normalize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [normalize(item) for item in value]
        return value
    events = [{key: event[key] for key in ("seq", "minute", "kind", "payload")}
              for event in data["events"]]
    requests = [{key: row.get(key) for key in
                 ("ordinal", "minute", "status", "proposal", "result", "expected_version")}
                for row in data["requests"]]
    return normalize({"world": data["world"], "events": events, "requests": requests,
                      "committed_command_count": len(data["commands"])})


def source_provenance() -> dict:
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    return {"execution_commit": git("rev-parse", "HEAD"),
            "worktree_clean": git("status", "--porcelain") == "",
            "python_version": platform.python_version(),
            "driver_source": "SYNTHETIC_STATE_BASED_COVERAGE_POLICY_V1"}


async def run_one(root: Path, days: int, *, restarted: bool, provenance: dict,
                  restart_interval: int = 97) -> tuple[dict, dict]:
    name = f"day{days}-" + ("restarted" if restarted else "plain")
    config = replace(LongRunConfig.load(ROOT / "config/experimental/m5_longrun_v1.json"),
                     sim_days=days)
    session = LongRunSession.create(root, name, config, provenance)
    samples = []
    started = time.perf_counter()
    try:
        while True:
            client = FakeLongRunPolicy(session.world, config)
            def checkpoint_sample(stage, data, bound_session=session):
                if stage == "CHECKPOINTED":
                    samples.append({"minute": bound_session.world.minute, **memory_sample()})
            result = await LongRunRunner(session, client, fault_hook=checkpoint_sample).run(
                max_steps=restart_interval if restarted else None)
            if result["state"] != "PAUSED":
                break
            old_dir = session.dir
            session.close()
            session = LongRunSession.open(old_dir, resume=True)
        audit = check_invariants_full(session.world)
        data = session.export_data()
        data["session"]["invariants"] = audit
        summary = export_reports(session)
        coverage = summary["evaluation"]["L2"]["goal_progress"]["observed_coverage"]
        required = ("WORK", "MEAL", "SLEEP", "TRAVEL", "LEISURE", "ACQUIRE", "PLAY", "WATCH")
        samples.append({"minute": session.world.minute, **memory_sample()})
        resource_evidence = {
            "result_class": "SCRIPTED_OR_FAKE_LONG_RUN", "days": days,
            "simulation_minutes": session.world.minute,
            "elapsed_wall_seconds_including_export": round(time.perf_counter() - started, 6),
            "runtime_wall_seconds": session.load()["wall_seconds"],
            "database_bytes": session.path.stat().st_size,
            "events": len(data["events"]), "micro_steps": result["micro_steps"],
            "decisions": result["decisions"], "resume_count": result["resume_count"],
            "stop_reason": result["stop_reason"], "horizon_reached": summary["horizon_reached"],
            "samples": samples, "provider_requests": 0,
            "memory_claim": "FINITE_7_30_DAY_OBSERVATION_NOT_UNLIMITED_DURATION_PROOF",
            "full_ledger_audit": audit,
        }
        write_json(session.dir / "resources.json", resource_evidence)
        # Even a budget-truncated validation retains reports and observed
        # resources before rejecting the pass gate; never silently lose evidence.
        if result["stop_reason"] != "SIMULATION_HORIZON_REACHED" or session.world.minute != days * 1440:
            write_json(session.dir / "validation_failure.json", {
                "result": "FAIL", "reason": "M5_ACTUAL_HORIZON_NOT_REACHED",
                "simulation_minutes": session.world.minute, "stop_reason": result["stop_reason"],
                "provider_requests": 0,
            })
            raise AssertionError("M5_ACTUAL_HORIZON_NOT_REACHED")
        if any(coverage.get(activity) != "EXERCISED" for activity in required):
            raise AssertionError("M5_REQUIRED_COVERAGE_NOT_EXERCISED")
        if client.provider_request_count != 0 or result["provider_requests_reserved"] != 0:
            raise AssertionError("M5_OFFLINE_PROVIDER_BUDGET_VIOLATED")
        return {"runtime": result, "resources": resource_evidence,
                "context": {"max_chars": summary["max_context_chars"],
                            "max_token_upper_bound": summary["max_context_token_upper_bound"],
                            "accounting": summary["context_token_accounting"]}, "coverage": coverage,
                "semantic_hash": digest(semantic_evidence(data)),
                "artifacts": str(session.dir)}, semantic_evidence(data)
    finally:
        session.close()


async def validate(root: Path, session_id: str, *, days=(7, 30)) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", session_id):
        raise ValueError("INVALID_VALIDATION_SESSION")
    output = root / session_id
    output.mkdir(parents=True, exist_ok=False)
    provenance = source_provenance()
    results = []
    with offline_network_guard():
        for day_count in days:
            plain, plain_facts = await run_one(output, day_count, restarted=False,
                                                provenance=provenance)
            resumed, resumed_facts = await run_one(output, day_count, restarted=True,
                                                    provenance=provenance)
            equal = plain_facts == resumed_facts
            row = {"days": day_count, "uninterrupted": plain, "restarted": resumed,
                   "final_semantic_state_and_event_ledger_equal": equal,
                   "result": "PASS" if equal else "FAIL"}
            results.append(row)
            write_json(output / "progress.json", {"results": results, "provider_requests": 0})
            print("M5_VALIDATION=" + json.dumps({"days": day_count,
                "minutes": resumed["runtime"]["simulation_minutes"],
                "decisions": resumed["runtime"]["decisions"],
                "restarts": resumed["runtime"]["resume_count"],
                "recovery_equivalent": equal, "provider_requests": 0}), flush=True)
            if not equal:
                raise AssertionError("M5_RESTART_SEMANTIC_OR_LEDGER_MISMATCH")
    payload = {"schema": "M5_LONGRUN_VALIDATION_V1", "provenance": provenance,
               "result_class": "SCRIPTED_OR_FAKE_LONG_RUN", "results": results,
               "provider_requests": 0, "NEW_REAL_PROVIDER_REQUESTS": 0,
               "HUMAN_LIKENESS_PROVEN": "NO", "REAL_MODEL_SEVEN_DAY_VALIDATED": "NO",
               "result": "PASS"}
    write_json(output / "summary.json", payload)
    print(f"M5_LONGRUN_VALIDATION_PASS\nARTIFACT_DIR={output}", flush=True)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--output-root", type=Path, default=ROOT / "run/evaluation/m5_longrun")
    args = parser.parse_args()
    asyncio.run(validate(args.output_root, args.session_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
