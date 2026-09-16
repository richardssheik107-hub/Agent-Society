"""One request to inspect the provider's final-text decision contract."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "third_party" / "AgentSociety" / ".env")

from social_sim.context import ContextCompiler  # noqa: E402
from social_sim.decision.config import DecisionProviderConfig  # noqa: E402
from social_sim.decision import (  # noqa: E402
    ActionType,
    DecisionClientError,
    DecisionParseError,
    DecisionParser,
    OpenAICompatibleDecisionClient,
    ProviderContractError,
)
from social_sim.decision.prompt import build_decision_prompt  # noqa: E402
from social_sim.world import (  # noqa: E402
    ObservationBuilder,
    OfferState,
    PersonWorldState,
    WorldState,
)


MAX_OUTPUT_TOKENS = 128
ACTIONS = (
    ActionType.WAIT,
    ActionType.REST,
    ActionType.MOVE,
    ActionType.BUY,
    ActionType.EAT,
)


def compact_prompt() -> tuple[str, str, int, int, tuple[str, ...]]:
    world = WorldState(
        time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        people={1: PersonWorldState(1, "home", 100.0, 0.8)},
        venues={"restaurant": {"meal": OfferState("meal", 20.0, 10)}},
    )
    observation = ObservationBuilder(world).build(1)
    targets = tuple(sorted(set(world.locations) | {"meal"}))
    context = ContextCompiler(max_chars=2000).compile(
        {"name": "Alice", "goal": "reduce hunger by obtaining and eating a meal"},
        observation,
        available_actions=[action.value for action in ACTIONS],
        available_targets=targets,
    )
    prompt = build_decision_prompt(context)
    return prompt.system, prompt.user, prompt.context_chars, prompt.prompt_chars, targets


def parse_category(error: DecisionParseError) -> str:
    message = str(error)
    if message.startswith(("Unknown action", "Proposed action")):
        return "INVALID_ACTION"
    return "INVALID_JSON"


async def main() -> int:
    try:
        config = DecisionProviderConfig.from_env()
    except ValueError:
        print("PROVIDER CONTRACT INCOMPLETE: CONFIG_MISSING", flush=True)
        return 1
    system, user, context_chars, prompt_chars, targets = compact_prompt()
    print("PROVIDER CONTRACT START", flush=True)
    print("API_MODE=Chat Completions", flush=True)
    print(f"REQUEST_MODEL={config.model}", flush=True)
    print("THINKING=disabled", flush=True)
    print(f"MAX_OUTPUT_TOKENS={MAX_OUTPUT_TOKENS}", flush=True)
    print(f"CONTEXT_CHARS={context_chars}", flush=True)
    print(f"PROMPT_CHARS={prompt_chars}", flush=True)

    client = OpenAICompatibleDecisionClient(
        base_url=config.api_base,
        api_key=config.api_key,
        model=config.model,
        timeout_seconds=60,
        max_tokens=MAX_OUTPUT_TOKENS,
        temperature=0.0,
        thinking_disabled=True,
    )
    try:
        request_start = datetime.now(timezone.utc)
        started = time.perf_counter()
        print(f"REQUEST_START={request_start.isoformat()}", flush=True)
        reply = None
        request_error: Exception | None = None
        try:
            reply = await client.complete(system, user)
        except Exception as error:
            request_error = error
        request_end = datetime.now(timezone.utc)
        elapsed = time.perf_counter() - started
        print(f"REQUEST_END={request_end.isoformat()}", flush=True)
        print(f"DECISION_LATENCY_SECONDS={elapsed:.3f}", flush=True)
        print(f"PROVIDER_LATENCY_SECONDS={client.last_latency_seconds}", flush=True)
        print(f"APPLICATION_CALLS={client.call_count}", flush=True)
        print(f"PROVIDER_ATTEMPTS={client.call_count}", flush=True)
        metadata = client.last_metadata
        print(
            "RESPONSE_METADATA="
            + json.dumps(metadata.safe_dict() if metadata else {}, separators=(",", ":")),
            flush=True,
        )
        if request_error is not None:
            if isinstance(request_error, ProviderContractError):
                category = request_error.category
            elif isinstance(request_error, httpx.TimeoutException):
                category = "TIMEOUT"
            elif isinstance(request_error, (DecisionClientError, httpx.HTTPError)):
                category = "PROVIDER"
            else:
                category = "PROVIDER_SCHEMA_MISMATCH"
            print(f"PROVIDER CONTRACT INCOMPLETE: {category}", flush=True)
            print("PARSER_REACHED=NO", flush=True)
            return 1
        assert reply is not None
        try:
            proposal = DecisionParser().parse(reply.raw_text)
        except DecisionParseError as error:
            category = parse_category(error)
            if metadata and metadata.finish_reason == "length":
                category = "OUTPUT_BUDGET_EXHAUSTED"
            print(f"PROVIDER CONTRACT INCOMPLETE: {category}", flush=True)
            print("PARSER_REACHED=YES", flush=True)
            return 1
        if proposal.action not in ACTIONS or (
            proposal.action in (ActionType.MOVE, ActionType.BUY, ActionType.EAT)
            and proposal.target not in targets
        ):
            print("PROVIDER CONTRACT INCOMPLETE: INVALID_ACTION", flush=True)
            print("PARSER_REACHED=YES", flush=True)
            return 1
        print("PARSER_REACHED=YES", flush=True)
        print(
            "PROPOSAL=" + json.dumps(
                {"action": proposal.action.value, "target": proposal.target},
                separators=(",", ":"),
            ),
            flush=True,
        )
        print("PROVIDER CONTRACT PASS", flush=True)
        return 0
    finally:
        await client.aclose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
