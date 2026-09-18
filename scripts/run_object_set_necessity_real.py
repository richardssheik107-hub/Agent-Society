#!/usr/bin/env python3
"""Optional real-provider A/B/C object-choice pilot.

Required environment:
OBJECT_BENCH_BASE_URL
OBJECT_BENCH_API_KEY
OBJECT_BENCH_MODEL

No provider credential is ever written to an artifact.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from social_sim.decision.client import OpenAICompatibleDecisionClient
from social_sim.object_benchmark.catalog import build_synthetic_catalog
from social_sim.object_benchmark.real_pilot import PilotConfig, run_real_pilot


def smoke_gate(summary: dict[str, object], rows: list[dict[str, object]]) -> str:
    """Return PASS only for the preregistered 15-request smoke conditions."""
    if summary.get("scheduled") != 15 or int(summary.get("success", 0)) < 14:
        return "FAIL"
    if int(summary.get("architecture_error", 0)) != 0:
        return "FAIL"
    successful = [row for row in rows if row.get("provider_status") == "SUCCESS"]
    b_rows = [row for row in successful if row.get("arm") == "B_CATALOG_TOPK"]
    c_rows = [row for row in successful if row.get("arm") == "C_HYBRID"]
    if not all(row.get("candidate_compliant") is True and row.get("runtime_executable") for row in b_rows):
        return "FAIL"
    if not all(row.get("novel_created") or row.get("candidate_compliant") for row in c_rows):
        return "FAIL"
    return "PASS"


async def _run(args: argparse.Namespace) -> None:
    for name in ("OBJECT_BENCH_BASE_URL", "OBJECT_BENCH_API_KEY", "OBJECT_BENCH_MODEL"):
        if not os.getenv(name):
            raise SystemExit(f"missing required environment variable: {name}")
    client = OpenAICompatibleDecisionClient(
        base_url=os.environ["OBJECT_BENCH_BASE_URL"],
        api_key=os.environ["OBJECT_BENCH_API_KEY"],
        model=os.environ["OBJECT_BENCH_MODEL"],
        timeout_seconds=60,
        minimal_request=True,
    )
    try:
        rows, summary = await run_real_pilot(
            client,
            build_synthetic_catalog(),
            PilotConfig(
                repetitions=args.repetitions,
                top_k=args.top_k,
                max_scenarios=args.max_scenarios,
            ),
        )
    finally:
        await client.aclose()

    root = Path(__file__).resolve().parents[1]
    output = root / "run/evaluation/object_set_necessity" / f"real_{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}"
    output.mkdir(parents=True, exist_ok=False)
    safe = {
        "config": {
            "repetitions": args.repetitions,
            "top_k": args.top_k,
            "max_scenarios": args.max_scenarios,
            "catalog_objects": 1000,
            "stores_raw_prompt": False,
            "stores_raw_completion": False,
            "stores_hidden_reasoning": False,
        },
        "rows": rows,
        "summary": summary,
    }
    (output / "result.json").write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    print("OBJECT_SET_NECESSITY_REAL_COMPLETE")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    if args.repetitions == 1 and args.max_scenarios == 5:
        print(f"SMOKE_GATE={smoke_gate(summary, rows)}")
    print(f"ARTIFACT_DIR={output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--max-scenarios", type=int)
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
