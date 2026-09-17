"""Offline A2.0 full-day regression: three profiles, no provider requests."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from social_sim.daily.profiles import SOURCE, load_experiment_profiles
from social_sim.daily.runner import DailyEpisodeRunner
from social_sim.daily.scripted import ScriptedNormalDayClient
from social_sim.daily.validation import validate_daily_trajectory
from social_sim.decision.client import DecisionReply


class Core7ScriptedClient(ScriptedNormalDayClient):
    async def complete(self, system_prompt: str, user_prompt: str) -> DecisionReply:
        context = json.loads(user_prompt.split("Context:", 1)[1])
        state = context["s"]
        hour = datetime.fromisoformat(state["t"]).hour
        minute = datetime.fromisoformat(state["t"]).minute
        if state["loc"] == "home" and hour == 6 and minute == 0:
            self.call_count += 1
            return DecisionReply('{"action":"PERSONAL_CARE","target":null}')
        if state["loc"] == "home" and hour == 6 and minute == 30:
            self.call_count += 1
            return DecisionReply('{"action":"CHORES","target":null}')
        return await super().complete(system_prompt, user_prompt)


async def main() -> None:
    root = Path(__file__).resolve().parents[1]
    profiles = load_experiment_profiles()
    source_hash_before = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    output = root / "run/evaluation/calibrated_neutral_day" / f"offline_{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}"
    for number, profile in enumerate(profiles, 1):
        client = Core7ScriptedClient() if profile.experimental_actions_enabled else ScriptedNormalDayClient()
        result = await DailyEpisodeRunner(client, output_dir=output, behavior_profile=profile).run_episode(number)
        assert result.day_completed and len(result.ticks) == 72 and result.provider_request_count == 0
        assert validate_daily_trajectory(result)
        if profile.experimental_actions_enabled:
            assert result.activity_counts["PERSONAL_CARE"] and result.activity_counts["CHORES"]
        print(f"{profile.name}=PASS decisions={result.decision_count} hash={profile.profile_hash}", flush=True)
    assert len({profile.profile_hash for profile in profiles}) == 3
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == source_hash_before
    print("OFFLINE_FULL_DAY=PASS PROVIDER_REQUESTS=0 PRODUCTION_CONFIG=UNCHANGED", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
