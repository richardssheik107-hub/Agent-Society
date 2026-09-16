"""Single-agent smoke test based on the current AgentSociety 2 Quick Start."""

import asyncio
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(WORKSPACE_ROOT / "third_party" / "AgentSociety" / ".env")

# Fail before importing the package or contacting an API when the copied
# upstream template has not been configured with real credentials.
if not os.getenv("AGENTSOCIETY_LLM_API_KEY") or os.getenv(
    "AGENTSOCIETY_LLM_API_KEY"
) == "your_api_key":
    raise RuntimeError("AGENTSOCIETY_LLM_API_KEY is missing; configure the ignored upstream .env")

from agentsociety2.contrib.env import SimpleSocialSpace  # noqa: E402
from agentsociety2.env import CodeGenRouter  # noqa: E402
from agentsociety2.society import AgentSociety  # noqa: E402


async def main() -> None:
    agent_specs = [{"id": 1, "profile": {"name": "Alice"}, "config": {}}]
    env = CodeGenRouter(
        env_modules=[SimpleSocialSpace(agent_id_name_pairs=[(1, "Alice")])]
    )
    society = AgentSociety(
        agent_specs=agent_specs,
        agent_class_name="PersonAgent",
        env_router=env,
        start_t=datetime.now(),
        run_dir=WORKSPACE_ROOT / "run" / "agentsociety2_smoke_linux",
    )

    try:
        await society.init()
        print("INIT_OK")
        response = await society.ask(
            "Ask Alice (agent id 1) directly: What's your name? "
            "Report Alice's answer, not the helper's identity."
        )
        print("RESPONSE:")
        print(response)
        if not response or "alice" not in response.lower():
            raise AssertionError("The response did not identify Alice")
    finally:
        await society.close()
        print("CLOSE_OK")


if __name__ == "__main__":
    asyncio.run(main())
