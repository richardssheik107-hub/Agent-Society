#!/usr/bin/env python3
"""Prepare Q6.2 A_RAW/B_FEASIBLE; real provider requires explicit opt-in."""
# ruff: noqa: E402 -- standalone runner adds the integration src path first.
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from social_sim.continuity.q6_2_ab import prepare_dry_run, run_ab_session, validate_session_id


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--session-id", required=True, help="新 session 的唯一安全标识")
    command.add_argument("--schedule", choices=("AB", "BA"), default="AB")
    command.add_argument("--output", type=Path, help="新的 artifact 目录，不允许覆盖")
    command.add_argument("--allow-provider", action="store_true",
                         help="显式授权真实 A/B，最多每 arm 四次、总共八次请求")
    return command


async def _real(output: Path, args: argparse.Namespace) -> dict:
    names = ("CONTINUITY_BASE_URL", "CONTINUITY_MODEL", "CONTINUITY_API_KEY")
    if not all(os.environ.get(name) for name in names):
        raise SystemExit("CONTINUITY_PROVIDER_CONFIG_MISSING; PROVIDER_REQUESTS=0")
    from social_sim.decision import OpenAICompatibleDecisionClient

    client = OpenAICompatibleDecisionClient(
        base_url=os.environ[names[0]], model=os.environ[names[1]],
        api_key=os.environ[names[2]], minimal_request=True, timeout_seconds=60,
    )
    try:
        return await run_ab_session(output, session_id=args.session_id,
                                    schedule=args.schedule, client=client,
                                    real_provider=True)
    finally:
        await client.aclose()


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    validate_session_id(args.session_id)
    output = args.output or ROOT / "run/evaluation/q6_2_real_ab" / args.session_id
    if output.exists():
        raise SystemExit("SESSION_ALREADY_EXISTS; PROVIDER_REQUESTS=0")
    if args.allow_provider:
        comparison = asyncio.run(_real(output, args))
    else:
        comparison = prepare_dry_run(output, session_id=args.session_id, schedule=args.schedule)
    print("Q6_2_REAL_AB_READY=YES")
    print(f"Q6_2_REAL_AB_EXECUTED={'YES' if comparison['real_ab_executed'] else 'NO'}")
    print(f"PROVIDER_REQUESTS={comparison['provider_requests']}")
    print(f"ARTIFACT_DIR={output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
