"""No-network Research A1 normal-day wiring acceptance."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from social_sim.daily.models import DailyTerminationReason
from social_sim.daily.runner import DailyEpisodeRunner
from social_sim.daily.scripted import ScriptedNormalDayClient
from social_sim.daily.time import DAY_END, DAY_START
from social_sim.daily.validation import validate_daily_trajectory


ROOT = Path(__file__).resolve().parents[1]


async def main() -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = ROOT / "run" / "evaluation" / "neutral_day" / f"offline_{stamp}"
    client = ScriptedNormalDayClient()
    result = await DailyEpisodeRunner(client, output_dir=output).run_episode(1)
    if result.termination_reason is not DailyTerminationReason.DAY_END:
        raise AssertionError("scripted day did not reach DAY_END")
    if len(result.ticks) != 72 or result.simulated_minutes != 1080:
        raise AssertionError("scripted day did not execute 72 fifteen-minute ticks")
    if result.idle_metrics["idle_minutes"] or result.idle_metrics["repeated_invalid_count"]:
        raise AssertionError("scripted day has idle or repeated invalid actions")
    if result.trajectory.rejected_actions or result.provider_request_count:
        raise AssertionError("scripted day has rejected actions or provider requests")
    if result.trajectory.max_context_chars >= 800:
        raise AssertionError("scripted daily context exceeded the 800-char target")
    if not validate_daily_trajectory(result):
        raise AssertionError("daily trajectory validation failed")
    print("NEUTRAL_DAY_OFFLINE_OK")
    print(f"SIM_START={DAY_START}")
    print(f"SIM_END={DAY_END}")
    print(f"DECISIONS={result.decision_count}")
    print(f"IDLE_MINUTES={result.idle_metrics['idle_minutes']}")
    print(f"MAX_IDLE_STREAK={result.idle_metrics['max_idle_streak_minutes']}")
    print(f"ACTIVITY_COUNTS={json.dumps(result.activity_counts, sort_keys=True, separators=(',', ':'))}")
    print(f"PROVIDER_REQUESTS={result.provider_request_count}")
    print("TRAJECTORY_VALIDATION=PASS")
    print(f"MAX_CONTEXT_CHARS={result.trajectory.max_context_chars}")
    print(f"ARTIFACT_DIR={output}")


if __name__ == "__main__":
    asyncio.run(main())
