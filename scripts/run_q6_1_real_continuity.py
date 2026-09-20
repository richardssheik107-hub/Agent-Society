#!/usr/bin/env python3
"""运行 Q6.1 有界真实模型连续性 pilot；默认不发 provider 请求。"""
# ruff: noqa: E402 -- standalone runner adds the integration src path first.
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from social_sim.continuity.benchmark import seed_demo
from social_sim.continuity.engine import ContinuityWorld
from social_sim.continuity.q6_1 import (
    EXPERIMENT_NAME,
    MAX_REAL_DECISIONS,
    Q61PilotRunner,
    environment_record,
    validate_decision_budget,
    write_artifacts,
)


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--allow-provider", action="store_true",
                         help="显式允许最多一次请求/高层决策的真实 provider pilot")
    command.add_argument("--max-decisions", type=int, default=MAX_REAL_DECISIONS)
    command.add_argument("--extended-pilot", action="store_true",
                         help="允许把预算从默认 4 扩展到最多 12；仍需显式 --allow-provider")
    command.add_argument("--output", type=Path,
                         help="新的 artifact 目录；默认写入 run/evaluation/q6_1_real_continuity/")
    return command


def _artifact_path(value: Path | None) -> Path:
    if value is not None:
        return value
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    return ROOT / "run/evaluation/q6_1_real_continuity" / stamp


def _continuity_result(summary: dict) -> str:
    required = (
        summary.get("provider_failures", 0) == 0
        and summary.get("invalid_outputs", 0) == 0
        and summary.get("commitment_failures", 0) == 0
        and summary.get("final_invariants", {}).get("invariants") == "PASS"
        and summary.get("STATE_FEEDBACK_VISIBLE") is True
        and summary.get("STATE_FEEDBACK_CHANGED") is True
    )
    return "SUPPORTED" if required else "UNRESOLVED"


async def run(args: argparse.Namespace) -> int:
    names = ("CONTINUITY_BASE_URL", "CONTINUITY_MODEL", "CONTINUITY_API_KEY")
    if not all(os.environ.get(name) for name in names):
        raise SystemExit("缺少 CONTINUITY_BASE_URL/MODEL/API_KEY；未发送请求。")
    output = _artifact_path(args.output)
    if output.exists():
        raise SystemExit(f"artifact 目录已存在，拒绝覆盖：{output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    from social_sim.continuity.decision import OpenAICompatibleDecisionClient

    client = OpenAICompatibleDecisionClient(
        base_url=os.environ[names[0]],
        model=os.environ[names[1]],
        api_key=os.environ[names[2]],
        minimal_request=True,
        timeout_seconds=60,
    )
    try:
        with ContinuityWorld(output / "world.sqlite3") as world:
            seed_demo(world)
            runner = Q61PilotRunner(
                world,
                client,
                max_decisions=args.max_decisions,
                extended_pilot=args.extended_pilot,
                hard_timeout_seconds=60,
            )
            summary, rows = await runner.run()
            environment = environment_record(
                ROOT, provider_model=os.environ[names[1]], real_provider=True
            )
            summary = {
                **summary,
                "source_commit": environment["git_commit"],
                "provider_model": environment["provider_model"],
                "real_provider_executed": True,
                "short_horizon_state_continuity": _continuity_result(summary),
            }
            write_artifacts(output, world, summary, rows, environment)
    finally:
        await client.aclose()
    print(f"EXPERIMENT={EXPERIMENT_NAME}")
    print("REAL_PROVIDER_EXECUTED=YES")
    print(f"APPLICATION_CALLS={summary['application_calls']}")
    print(f"PROVIDER_REQUESTS={summary['provider_requests']}")
    print(f"TERMINATION_REASON={summary['termination_reason']}")
    print(f"SHORT_HORIZON_STATE_CONTINUITY={summary['short_horizon_state_continuity']}")
    print(f"ARTIFACT_DIR={output}")
    return 0 if summary["termination_reason"] == "BUDGET_COMPLETED" else 1


def main(argv: list[str] | None = None) -> int:
    command = parser()
    args = command.parse_args(argv)
    try:
        validate_decision_budget(args.max_decisions, extended_pilot=args.extended_pilot)
    except ValueError as error:
        command.error(str(error))
    if not args.allow_provider:
        print("Q6_1_REAL_PROVIDER_NOT_AUTHORIZED")
        print("REAL_PROVIDER_EXECUTED=NO")
        print("PROVIDER_REQUESTS=0")
        return 0
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
