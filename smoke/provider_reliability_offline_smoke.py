"""Thirty sequential fake DecisionClient calls; no network or world runtime."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from social_sim.decision.client import FakeDecisionClient
from social_sim.evaluation.provider_reliability import (
    run_provider_reliability,
    write_provider_reliability_report,
)


ROOT = Path(__file__).resolve().parents[1]


async def main() -> None:
    client = FakeDecisionClient('{"action":"MOVE","target":"home"}')
    result = await run_provider_reliability(client)
    assert len(result.requests) == client.call_count == 30
    assert result.reliability_ok
    assert all(row.success for row in result.requests)
    folder = ROOT / "run" / "evaluation" / "provider_reliability" / (
        "offline_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    )
    write_provider_reliability_report(result, folder)
    print("PROVIDER_RELIABILITY_OFFLINE_OK")
    print("requests=30")
    print("success=30")
    print("timeouts=0")
    print("provider_requests=0")
    print(f"artifact={folder}")


if __name__ == "__main__":
    asyncio.run(main())
