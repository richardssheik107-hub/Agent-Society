"""Real single-Alice AgentSociety smoke for the read-only Phase 1 world."""

import asyncio
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "third_party" / "AgentSociety" / ".env")
if not os.getenv("AGENTSOCIETY_LLM_API_KEY") or os.getenv(
    "AGENTSOCIETY_LLM_API_KEY"
) == "your_api_key":
    raise RuntimeError("Configure the ignored upstream .env with real credentials")

from agentsociety2.env import CodeGenRouter  # noqa: E402
from agentsociety2.society import AgentSociety  # noqa: E402
from social_sim.world import PersonWorldState, WorldState  # noqa: E402
from social_sim.world.env import RuleWorldEnv  # noqa: E402


def state_snapshot(world: WorldState) -> dict:
    alice = world.get_person(1)
    return {
        "time": world.time.isoformat(),
        "agent_id": alice.agent_id,
        "location": alice.location,
        "money": alice.money,
        "hunger": alice.hunger,
    }


async def main() -> None:
    world = WorldState(
        time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        people={
            1: PersonWorldState(
                agent_id=1, location="home", money=100.0, hunger=0.8
            )
        },
    )
    world_env = RuleWorldEnv(world)
    before = state_snapshot(world)
    direct = world_env.observe_person(1)
    assert direct == {"agent_id": 1, **before}
    assert state_snapshot(world) == before
    print("DIRECT_OBSERVE_OK", flush=True)

    router = CodeGenRouter(env_modules=[world_env])
    assert router._tools_pyi_dict[(True, "observe")].find("observe_person") >= 0
    society = AgentSociety(
        agent_specs=[
            {"id": 1, "profile": {"name": "Alice"}, "config": {"max_react_turns": 3}}
        ],
        agent_class_name="PersonAgent",
        env_router=router,
        start_t=world.time,
        run_dir=ROOT / "run" / "custom_world_smoke",
    )

    try:
        await society.init()
        print("INIT_OK", flush=True)
        response = await society.ask(
            "Ask Alice (agent id 1) directly to observe her current environment. "
            "Have Alice briefly report where she is, how much money she has, and "
            "her hunger level. Use the environment, not her profile or guesses, "
            "as the source of truth. Report Alice's answer, not the helper's state."
        )
        print("ALICE_RESPONSE:", flush=True)
        print(response, flush=True)
        observed_ids = [
            record.get("kwargs", {}).get("agent_id")
            for record in world_env.get_tool_call_history()
            if record.get("function_name") == "observe_person"
            and not record.get("exception_occurred")
        ]
        assert 1 in observed_ids, f"No actual observe_person call for Alice: {observed_ids}"
        print("ALICE_ENV_TOOL_CALL_OK", flush=True)

        answer = str(response).lower()
        assert "home" in answer, "Alice did not report home"
        assert re.search(r"\b100(?:\.0+)?\b", answer), "Alice did not report 100"
        assert re.search(r"\b0\.8\b|\b80\s*(?:%|percent)\b", answer), (
            "Alice did not report hunger 0.8 (or 80%)"
        )
        print("ALICE_OBSERVATION_OK", flush=True)

        after = state_snapshot(world)
        print(f"STATE_BEFORE: {before}", flush=True)
        print(f"STATE_AFTER: {after}", flush=True)
        assert before == after, "WorldState changed during read-only smoke"
        print("WORLD_UNCHANGED_OK", flush=True)
    finally:
        await society.close()
        print("CLOSE_OK", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
