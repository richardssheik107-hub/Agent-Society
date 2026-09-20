#!/usr/bin/env python3
"""真实 AS2 EnvBase/DeterministicRouter 的无模型专项；不启动 PersonAgent。"""
from __future__ import annotations
import asyncio
import json
import os
import socket
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ["AGENTSOCIETY_LLM_API_KEY"] = "offline-placeholder-not-a-secret"
os.environ["AGENTSOCIETY_LLM_API_BASE"] = "http://127.0.0.1:9/v1"
os.environ["AGENTSOCIETY_LLM_MODEL"] = "openai/offline-placeholder"
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"


def denied(*args, **kwargs):
    raise RuntimeError("AS2 integration smoke forbids external network")


async def main():
    socket.socket.connect = denied
    socket.create_connection = denied
    from social_sim.continuity.agentsociety_adapter import ContinuityEnv
    from social_sim.continuity.benchmark import seed_demo
    from social_sim.continuity.validation import validate_world
    from social_sim.router.deterministic import DeterministicRouter
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        env = ContinuityEnv(str(root / "live.sqlite3"))
        seed_demo(env.runtime)
        await env.init(env.epoch)
        router = DeterministicRouter([env])
        _, text = await router.ask({"agent_id": 1}, "<observe>", readonly=True)
        assert json.loads(text)["actor"]["location"] == "home"
        env.runtime.start("watch", 1, "WATCH", "series_a")
        await env.step(600, env.epoch + timedelta(minutes=10))
        await env.to_workspace(root / "env_workspace")
        expected = env.runtime.store.snapshot()
        await env.close()
        restored = ContinuityEnv(str(root / "fresh.sqlite3"))
        try:
            assert await restored.restore(root / "env_workspace")
            assert restored.runtime.store.snapshot() == expected
            await restored.step(1200, restored.epoch + timedelta(minutes=30))
            second = DeterministicRouter([restored])
            _, text = await second.ask({"agent_id": 1}, "<observe>", readonly=True)
            media = next(x for x in json.loads(text)["objects"] if x["id"] == "series_a")
            assert media["next_episode"] == 2
            validate_world(restored.runtime)
        finally:
            await restored.close()
        print("AS2_CONTINUITY_ADAPTER_PASS")
        print("LLM_CALLS=0 PROVIDER_REQUESTS=0")


if __name__ == "__main__":
    asyncio.run(main())
