#!/usr/bin/env python3
"""显式授权的有限真实决策入口；失败停止，不自动补动作、重试或续跑。"""
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
    if not all(os.environ.get(name) for name in names):
        raise SystemExit("缺少 CONTINUITY_BASE_URL/MODEL/API_KEY；未发送请求。")
    output = ROOT / "run/evaluation/continuity" / datetime.now(timezone.utc).strftime("real_%Y%m%dT%H%M%S%fZ")
    output.mkdir(parents=True, exist_ok=False)
    client = OpenAICompatibleDecisionClient(base_url=os.environ[names[0]],
        model=os.environ[names[1]], api_key=os.environ[names[2]],
        minimal_request=True, timeout_seconds=60)
    rows = []
    stop_reason = "BUDGET_COMPLETED"
    try:
        with ContinuityWorld(output / "world.sqlite3") as world:
            seed_demo(world)
            runner = ActivityDecisionRunner(world, client, max_calls=args.max_decisions,
                                            journal_path=output / "decisions.jsonl")
            try:
                for index in range(args.max_decisions):
                    command = f"real:{index}"
                    row = await runner.decide(command)
                    rows.append(row)
                    print(f"decision={index+1} status={row['status']}", flush=True)
                    if row["status"] != "DECISION_ACCEPTED":
                        stop_reason = row["status"]
                        break
                    while c := world.store.commitment(1):
                        if c["status"] != "ACTIVE" or c["remaining_min"] <= 0:
                            raise RuntimeError("invalid active phase")
                        target = world.minute + min(c["remaining_min"], 15)
                        tick = world.advance(f"{command}:t{target}", target)
                        if not tick["accepted"]:
                            raise RuntimeError("clock command rejected")
                    final = world.store.get_commitment(command)
                    row["execution_status"] = final["status"]
                    row["execution_failure_reason"] = final["failure_reason"]
                    row["finished_minute"] = world.minute
                    with (output / "executions.jsonl").open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps({"request_id": command,
                            "execution_status": final["status"], "minute": world.minute,
                            "failure_reason": final["failure_reason"]}, ensure_ascii=False) + "\n")
                    validate_world(world)
                    if final["status"] != "COMPLETED":
                        stop_reason = "COMMITMENT_FAILED"
                        break
            except Exception:
                # 不将异常正文、凭据或原始模型文本写入产物或 stderr。
                stop_reason = "ARCHITECTURE_ERROR"
            try:
                validation = validate_world(world)
            except Exception:
                validation = {"invariants": "FAIL"}
                stop_reason = "ARCHITECTURE_ERROR"
            summary = {"mode": "REAL_BOUNDED_PILOT", "application_calls": runner.calls,
                       "provider_requests": getattr(client, "provider_request_count", None),
                       "rows": rows, "termination_reason": stop_reason,
                       "validation": validation, "full_day_behavior_validated": False}
            (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        await client.aclose()
    print(f"TERMINATION_REASON={stop_reason}")
    print(f"ARTIFACT_DIR={output}")
    return 0 if stop_reason == "BUDGET_COMPLETED" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-provider", action="store_true")
    parser.add_argument("--max-decisions", type=int, default=4)
    args = parser.parse_args()
    if not args.allow_provider:
        parser.error("必须显式传入 --allow-provider；默认不调用模型")
    if not 1 <= args.max_decisions <= 12:
        parser.error("真实小样本预算必须在 1..12 之间")
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
