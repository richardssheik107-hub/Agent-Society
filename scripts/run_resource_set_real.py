#!/usr/bin/env python3
"""Run the Q4 smoke or full provider pilot exactly once per scheduled cell."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from social_sim.behavior_prior.index import BehaviorPriorIndex
from social_sim.behavior_prior.query import PriorQuery
from social_sim.decision.client import OpenAICompatibleDecisionClient
from social_sim.a2_final.corpus import HeldoutScorer, split_worker_diaries
from social_sim.resource_benchmark import (
    build_schedule,
    build_scenarios,
    smoke_scenarios,
)
from social_sim.resource_benchmark.real_pilot import run_real_pilot


def _load_env(path: Path) -> None:
    """Load existing dotenv values in memory; never print or write credentials."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _provider_config() -> tuple[str, str, str]:
    _load_env(Path(__file__).resolve().parents[1] / "third_party/AgentSociety/.env")
    base_url = os.getenv("OBJECT_BENCH_BASE_URL") or os.getenv("AGENTSOCIETY_LLM_API_BASE")
    api_key = os.getenv("OBJECT_BENCH_API_KEY") or os.getenv("AGENTSOCIETY_LLM_API_KEY")
    model = os.getenv("OBJECT_BENCH_MODEL") or os.getenv("AGENTSOCIETY_LLM_MODEL")
    if not base_url or not api_key or not model:
        raise SystemExit("missing provider configuration in existing secure .env")
    return base_url, api_key, model


def smoke_gate(summary: dict[str, object], rows: list[dict[str, object]]) -> str:
    if summary.get("scheduled") != 16 or int(summary.get("success", 0)) < 15:
        return "FAIL"
    if int(summary.get("architecture_error", 0)) != 0:
        return "FAIL"
    successful = [row for row in rows if row.get("provider_status") == "SUCCESS"]
    if not all(row.get("strict_parse_valid") and row.get("resource_projection_valid") for row in successful):
        return "FAIL"
    return "PASS"


async def _run(args: argparse.Namespace) -> None:
    base_url, api_key, model = _provider_config()
    corpora, eval_days, split = split_worker_diaries()
    prior_index = BehaviorPriorIndex.build(corpora["BTRAIN_ALL"])
    scenarios = build_scenarios(prior_index)
    chosen = smoke_scenarios(scenarios) if args.phase == "smoke" else scenarios
    repetitions = 1 if args.phase == "smoke" else 2
    schedule = build_schedule(chosen, repetitions=repetitions)
    heldout = HeldoutScorer(eval_days)
    distributions = {
        scenario.scenario_id: heldout.distribution(
            PriorQuery.at(__import__("datetime").datetime.fromisoformat(scenario.time), scenario.previous_activity)
        )
        for scenario in chosen
    }
    root = Path(__file__).resolve().parents[1]
    output = root / "run/evaluation/resource_set_size" / f"real_{args.attempt_id}_{args.phase}_{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}"
    output.mkdir(parents=True, exist_ok=False)
    client = OpenAICompatibleDecisionClient(
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout_seconds=60,
        minimal_request=True,
    )
    completed = 0

    def on_progress(row: dict[str, object]) -> None:
        nonlocal completed
        completed += 1
        if completed % 4 == 0 or completed == len(schedule):
            print(f"completed={completed}/{len(schedule)} success={sum(r.get('provider_status') == 'SUCCESS' for r in rows_seen)} timeout={sum(r.get('provider_status') == 'TIMEOUT' for r in rows_seen)}", flush=True)
        rows_seen.append(row)

    rows_seen: list[dict[str, object]] = []
    try:
        rows, summary = await run_real_pilot(
            client, chosen, schedule,
            progress_path=output / "progress.jsonl",
            heldout_distributions=distributions,
            on_progress=on_progress,
        )
    finally:
        await client.aclose()
    summary = {
        **summary,
        "experiment": "resource_set_size",
        "attempt": args.attempt_id,
        "phase": args.phase,
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "scenario_count": len(chosen),
        "schedule_repetitions": repetitions,
        "prior": {"corpus": "BTRAIN_ALL", "train_diaries": 2572, "prior_limit": 1},
        "heldout": {"eval_diaries": 643, "split_hash": split["split_hash"]},
        "object_architecture": "Catalog + Top-K (fixed from Q3)",
        "raw_prompt_stored": False,
        "raw_completion_stored": False,
        "hidden_reasoning_stored": False,
    }
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "result.json").write_text(json.dumps({"config": {"phase": args.phase, "attempt_id": args.attempt_id, "scenario_count": len(chosen), "repetitions": repetitions}, "summary": summary, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RESOURCE_SET_REAL_COMPLETE")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    if args.phase == "smoke":
        print(f"SMOKE_GATE={smoke_gate(summary, rows)}")
    print(f"ARTIFACT_DIR={output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("smoke", "full"), required=True)
    parser.add_argument("--attempt-id", default="q4_attempt_1")
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
