"""One real compact decision request; the returned proposal is never executed."""

import asyncio
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "third_party" / "AgentSociety" / ".env")

from social_sim.context import ContextCompiler  # noqa: E402
from social_sim.decision.config import DecisionProviderConfig  # noqa: E402
from social_sim.decision import (  # noqa: E402
    CompactDecisionService,
    DecisionParseError,
    OpenAICompatibleDecisionClient,
)
from social_sim.decision.prompt import build_decision_prompt  # noqa: E402
from social_sim.world import ObservationBuilder, PersonWorldState, WorldState  # noqa: E402


def snapshot(world: WorldState) -> dict:
    alice = world.get_person(1)
    return {
        "time": world.time.isoformat(),
        "agent_id": alice.agent_id,
        "location": alice.location,
        "money": alice.money,
        "hunger": alice.hunger,
    }


def safe_preview(raw: str) -> str:
    preview = raw.replace("\n", " ")[:120]
    preview = re.sub(r"ark-[0-9a-f-]{20,}", "[REDACTED]", preview, flags=re.I)
    return repr(preview)


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
    observation = ObservationBuilder(world).build(1)
    assert observation.location == "home"
    print("OBSERVATION_OK", flush=True)

    actions = ("WAIT", "REST", "MOVE")
    targets = ("park", "restaurant")
    compiler = ContextCompiler(max_chars=2000)
    context = compiler.compile(
        {"name": "Alice"}, observation,
        available_actions=actions,
        available_targets=targets,
    )
    prompt = build_decision_prompt(context)
    assert len(context) < 1000
    assert prompt.prompt_chars < 1500
    print("CONTEXT_COMPILED_OK", flush=True)
    print(f"CONTEXT_CHARS={len(context)}", flush=True)
    print(f"PROMPT_CHARS={prompt.prompt_chars}", flush=True)

    try:
        config = DecisionProviderConfig.from_env()
    except ValueError:
        raise RuntimeError("Missing model configuration in the ignored upstream .env")
    client = OpenAICompatibleDecisionClient(
        base_url=config.api_base,
        api_key=config.api_key,
        model=config.model,
        timeout_seconds=60,
        max_tokens=64,
        temperature=0.0,
    )
    service = CompactDecisionService(client, compiler)

    print("DECISION_CALL_START", flush=True)
    started = time.perf_counter()
    try:
        result = await service.decide(
            {"name": "Alice"}, observation,
            available_actions=actions,
            available_targets=targets,
        )
    except DecisionParseError:
        raw = client.last_raw_text or ""
        print("INVALID_MODEL_OUTPUT", flush=True)
        print(f"RAW_OUTPUT_CHARS={len(raw)}", flush=True)
        print(f"RAW_OUTPUT_PREVIEW={safe_preview(raw)}", flush=True)
        raise
    finally:
        elapsed = time.perf_counter() - started
        await client.aclose()
        print("DECISION_CALL_END", flush=True)
        print(f"DECISION_CALLS={service.decision_call_count}", flush=True)
        print(f"DECISION_LATENCY_SECONDS={elapsed:.3f}", flush=True)
        after = snapshot(world)
        print(f"WORLD_BEFORE={before}", flush=True)
        print(f"WORLD_AFTER={after}", flush=True)
        assert before == after
        print("WORLD_STATE_UNCHANGED", flush=True)

    assert service.decision_call_count == client.call_count == 1
    assert result.context_chars == len(context)
    assert result.prompt_chars == prompt.prompt_chars
    print("DECISION_VALID", flush=True)
    print(
        "DECISION="
        + json.dumps(
            {"action": result.proposal.action.value, "target": result.proposal.target},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        flush=True,
    )
    print(f"RAW_OUTPUT_CHARS={result.raw_output_chars}", flush=True)
    if result.raw_output_chars > 500:
        print("OUTPUT_TOO_VERBOSE_WARNING", flush=True)
    if result.input_tokens is not None or result.output_tokens is not None:
        print(f"INPUT_TOKENS={result.input_tokens}", flush=True)
        print(f"OUTPUT_TOKENS={result.output_tokens}", flush=True)
    print("ENVIRONMENT_LLM_CALLS=0", flush=True)
    print("PHASE2_SMOKE_OK", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
