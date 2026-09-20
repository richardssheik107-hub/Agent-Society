#!/usr/bin/env python3
"""显式授权的小规模真实决策入口；不自动调用、不自动重试、不自动续跑。"""
from __future__ import annotations
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


async def run(args):
    from social_sim.continuity import ContinuityWorld, validate_world
    from social_sim.continuity.benchmark import seed_demo
    from social_sim.continuity.decision import ActivityDecisionRunner
    from social_sim.decision.client import OpenAICompatibleDecisionClient
    names = ("CONTINUITY_BASE_URL", "CONTINUITY_MODEL", "CONTINUITY_API_KEY")
    if not all(os.environ.get(n) for n in names):
        raise SystemExit("缺少 CONTINUITY_BASE_URL/MODEL/API_KEY；未发送请求。")
    output = ROOT / "run/evaluation/continuity" / datetime.now(timezone.utc).strftime("real_%Y%m%dT%H%M%S%fZ")
    output.mkdir(parents=True, exist_ok=False)
    client = OpenAICompatibleDecisionClient(base_url=os.environ[names[0]],
        model=os.environ[names[1]], api_key=os.environ[names[2]],
        minimal_request=True, timeout_seconds=60)
    rows = []
    try:
        with ContinuityWorld(output / "world.sqlite3") as world:
            seed_demo(world)
            runner = ActivityDecisionRunner(world, client, max_calls=args.max_decisions,
                                             journal_path=output / "decisions.jsonl")
            for index in range(args.max_decisions):
                row = await runner.decide(f"real:{index}")
                rows.append(row)
                print(f"decision={index+1} status={row['status']}", flush=True)
                if row["status"] != "DECISION_ACCEPTED":
                    break
                while c := world.store.commitment(1):
                    target = world.minute + min(c["remaining_min"], 15)
                    world.advance(f"real:{index}:t{target}", target)
                validate_world(world)
            summary = {"mode": "REAL_BOUNDED_PILOT", "application_calls": runner.calls,
                       "provider_requests": getattr(client, "provider_request_count", None),
                       "rows": rows, "validation": validate_world(world),
                       "full_day_behavior_validated": False}
            (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        await client.aclose()
    print(f"ARTIFACT_DIR={output}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--allow-provider", action="store_true")
    p.add_argument("--max-decisions", type=int, default=4)
    a = p.parse_args()
    if not a.allow_provider:
        p.error("必须显式传入 --allow-provider；默认不调用模型")
    if not 1 <= a.max_decisions <= 12:
        p.error("真实小样本预算必须在 1..12 之间")
    asyncio.run(run(a))


if __name__ == "__main__":
    main()
