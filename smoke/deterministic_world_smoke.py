"""Zero-LLM AgentSociety initialization with the deterministic world router."""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "third_party" / "AgentSociety" / ".env")

from agentsociety2.society import AgentSociety  # noqa: E402
from social_sim.context import ContextCompiler  # noqa: E402
from social_sim.router import DeterministicRouter  # noqa: E402
from social_sim.world import PersonWorldState, WorldState  # noqa: E402
from social_sim.world.env import RuleWorldEnv  # noqa: E402


def snapshot(world: WorldState) -> dict:
    person = world.get_person(1)
    return {
        "time": world.time.isoformat(),
        "agent_id": person.agent_id,
        "location": person.location,
        "money": person.money,
        "hunger": person.hunger,
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
    before = snapshot(world)
    print("WORLD_INIT_OK", flush=True)

    world_env = RuleWorldEnv(world)
    router = DeterministicRouter(env_modules=[world_env])

    async def forbidden_completion(*args, **kwargs):
        raise AssertionError("DeterministicRouter must not call LLM")

    # Smoke-only tripwires catch unexpected env-side calls even if token usage
    # would remain zero after a failed request.
    router._coder_dispatcher.call = forbidden_completion
    router._summary_dispatcher.call = forbidden_completion
    router.acompletion = forbidden_completion
    router.acompletion_with_system_prompt = forbidden_completion
    router.generate_world_description_from_tools = forbidden_completion

    society = AgentSociety(
        agent_specs=[
            {"id": 1, "profile": {"name": "Alice"}, "config": {"max_react_turns": 3}}
        ],
        agent_class_name="PersonAgent",
        env_router=router,
        start_t=world.time,
        run_dir=ROOT / "run" / "deterministic_world_smoke",
    )

    try:
        await society.init()
        print("ROUTER_INIT_OK", flush=True)
        print("AGENTSOCIETY_INIT_OK", flush=True)

        _, answer = await router.ask({"id": 1}, "<observe>", readonly=True)
        observed = json.loads(answer)
        assert observed == {"agent_id": 1, **before}
        print("DIRECT_OBSERVE_OK", flush=True)

        _, statistics = await router.ask({}, "<statistics>", readonly=True)
        assert statistics == "{}"
        print("STATISTICS_OK", flush=True)

        description = await router.get_world_description()
        assert description == await router.get_world_description()
        assert len(description.split()) < 50
        print("WORLD_DESCRIPTION_OK", flush=True)

        compact_context = ContextCompiler(max_chars=1500).compile(
            {"name": "Alice"}, world_env.observation_builder.build(1)
        )
        assert len(compact_context) < 1500
        print(f"COMPACT_CONTEXT_CHARS: {len(compact_context)}", flush=True)

        usage = router.get_token_usages()
        call_count = sum(stat.call_count for stat in usage.values())
        assert call_count == 0, f"Router LLM calls: {call_count}"
        print(f"ROUTER_LLM_CALLS: {call_count}", flush=True)
        print("ZERO_ROUTER_LLM_CALLS_OK", flush=True)

    finally:
        await society.close()
        print("CLOSE_OK", flush=True)

    after = snapshot(world)
    print(f"WORLD_BEFORE: {before}", flush=True)
    print(f"WORLD_AFTER: {after}", flush=True)
    assert before == after
    print("WORLD_STATE_UNCHANGED", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
