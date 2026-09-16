"""The environment routing path must not make an LLM request."""

import asyncio
import json
from datetime import datetime, timezone

import pytest

from social_sim.router import DeterministicRouter
from social_sim.world import PersonWorldState, WorldState
from social_sim.world.env import RuleWorldEnv


START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_router() -> tuple[WorldState, RuleWorldEnv, DeterministicRouter]:
    world = WorldState(
        time=START,
        people={
            1: PersonWorldState(
                agent_id=1, location="home", money=100.0, hunger=0.8
            )
        },
    )
    env = RuleWorldEnv(world)
    return world, env, DeterministicRouter(env_modules=[env])


def block_llm(monkeypatch: pytest.MonkeyPatch, router: DeterministicRouter) -> None:
    async def forbidden(*args, **kwargs):
        raise AssertionError("DeterministicRouter must not call LLM")

    monkeypatch.setattr(router._coder_dispatcher, "call", forbidden)
    monkeypatch.setattr(router._summary_dispatcher, "call", forbidden)
    monkeypatch.setattr(router, "acompletion", forbidden)
    monkeypatch.setattr(router, "acompletion_with_system_prompt", forbidden)
    monkeypatch.setattr(router, "generate_world_description_from_tools", forbidden)


def assert_zero_usage(router: DeterministicRouter) -> None:
    assert all(stat.call_count == 0 for stat in router.get_token_usages().values())


def test_router_init_has_zero_llm_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, router = make_router()
    block_llm(monkeypatch, router)

    async def run() -> None:
        try:
            assert await router.init(START) is False
            assert router.t == START
            assert_zero_usage(router)
        finally:
            await router.close()

    asyncio.run(run())


def test_router_observe_reads_alice_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world, env, router = make_router()
    block_llm(monkeypatch, router)
    before = WorldState(time=world.time, people=world.people)

    async def run() -> None:
        try:
            await router.init(START)
            ctx, answer = await router.ask(
                {"id": 1}, "<observe>", readonly=True, trace_id="test-trace"
            )
            assert ctx["current_time"]["datetime"] == START.isoformat()
            assert json.loads(answer) == {
                "agent_id": 1,
                "time": START.isoformat(),
                "location": "home",
                "money": 100.0,
                "hunger": 0.8,
            }
            assert env.get_tool_call_history()[-1]["trace_id"] == "test-trace"
            assert world == before
            assert_zero_usage(router)
        finally:
            await router.close()

    asyncio.run(run())


def test_statistics_is_empty_and_zero_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, router = make_router()
    block_llm(monkeypatch, router)

    async def run() -> None:
        try:
            await router.init(START)
            _, answer = await router.ask({}, "<statistics>", readonly=True)
            assert answer == "{}"
            assert_zero_usage(router)
        finally:
            await router.close()

    asyncio.run(run())


def test_world_description_is_static_and_zero_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, router = make_router()
    block_llm(monkeypatch, router)

    async def run() -> None:
        try:
            first = await router.get_world_description()
            second = await router.get_world_description()
            assert first == second
            assert len(first.split()) < 50
            assert_zero_usage(router)
        finally:
            await router.close()

    asyncio.run(run())


def test_unsupported_instruction_does_not_route_to_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, router = make_router()
    block_llm(monkeypatch, router)

    async def run() -> None:
        try:
            _, answer = await router.ask({"id": 1}, "move to the shop")
            assert "not implemented" in answer
            assert_zero_usage(router)
        finally:
            await router.close()

    asyncio.run(run())


def test_missing_agent_id_fails_explicitly(monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, router = make_router()
    block_llm(monkeypatch, router)

    async def run() -> None:
        try:
            with pytest.raises(ValueError, match="requires agent_id"):
                await router.ask({}, "<observe>", readonly=True)
            assert_zero_usage(router)
        finally:
            await router.close()

    asyncio.run(run())
