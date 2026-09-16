"""One minimal Coding Plan Chat Completions request; no lunch simulation."""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "third_party" / "AgentSociety" / ".env")

from social_sim.decision import (  # noqa: E402
    DecisionClientError,
    DecisionParseError,
    DecisionParser,
    OpenAICompatibleDecisionClient,
    ProviderContractError,
)
from social_sim.decision.config import (  # noqa: E402
    DecisionConfigError,
    DecisionProviderConfig,
)


SYSTEM = "Return only the requested JSON. Do not explain."
USER = (
    "Return exactly one valid next-action JSON object using this schema:\n"
    '{"action":"WAIT","target":null}'
)


def failure_category(error: Exception, status: int | None, code: str | None) -> str:
    if status in (401, 403):
        return "AUTH_CONFIGURATION"
    if code == "model_not_found":
        return "MODEL_CONFIGURATION"
    if isinstance(error, ProviderContractError):
        return error.category
    if isinstance(error, httpx.TimeoutException):
        return "TIMEOUT"
    if isinstance(error, (DecisionClientError, httpx.HTTPError)):
        return "PROVIDER_HTTP_ERROR"
    return "PROVIDER_SCHEMA_MISMATCH"


def safe_base_url_display(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return "[INVALID_URL]"
    return f"{parsed.scheme}://{parsed.hostname}{parsed.path.rstrip('/')}"


async def main() -> int:
    try:
        config = DecisionProviderConfig.from_env(os.environ)
    except DecisionConfigError as error:
        print(f"PHASE 6.5B PROVIDER BASE CONTRACT INCOMPLETE: {error.code}", flush=True)
        return 1

    # This audit is local and happens before any network request.
    print("ZERO_NETWORK_CONFIG_AUDIT", flush=True)
    print(f"DECISION_BASE_URL={safe_base_url_display(config.api_base)}", flush=True)
    print(f"BASE_URL_CATEGORY={config.base_url_category}", flush=True)
    print(f"MODEL={config.model}", flush=True)
    print("API_MODE=Chat Completions", flush=True)
    print(f"CREDENTIAL_SOURCE_CATEGORY={config.credential_category}", flush=True)
    print("THINKING_CONFIGURED=NO", flush=True)
    print("TEMPERATURE_CONFIGURED=NO", flush=True)
    print("MAX_TOKENS_CONFIGURED=NO", flush=True)
    print("OPTIONAL_PARAMS_COUNT=0", flush=True)
    print(f"PROMPT_CHARS={len(SYSTEM) + len(USER)}", flush=True)

    client = OpenAICompatibleDecisionClient(
        base_url=config.api_base,
        api_key=config.api_key,
        model=config.model,
        timeout_seconds=60,
        minimal_request=True,
    )
    try:
        start = datetime.now(timezone.utc)
        started = time.perf_counter()
        print(f"REQUEST_START={start.isoformat()}", flush=True)
        reply = None
        request_error: Exception | None = None
        try:
            reply = await client.complete(SYSTEM, USER)
        except Exception as error:
            request_error = error
        end = datetime.now(timezone.utc)
        print(f"REQUEST_END={end.isoformat()}", flush=True)
        print(f"LATENCY_SECONDS={time.perf_counter() - started:.3f}", flush=True)
        print(f"PROVIDER_REQUESTS={client.call_count}", flush=True)
        metadata = client.last_metadata
        print("RESPONSE_METADATA=" + json.dumps(
            metadata.safe_dict() if metadata else {}, separators=(",", ":")
        ), flush=True)
        if metadata is not None:
            print(f"HTTP_STATUS={metadata.http_status}", flush=True)
            print(f"ERROR_TYPE={metadata.http_error_type}", flush=True)
            print(f"ERROR_CODE={metadata.http_error_code}", flush=True)
            print(f"ERROR_PARAM={metadata.http_error_param}", flush=True)
            print(f"REQUEST_ID={metadata.request_id}", flush=True)
            print(f"SANITIZED_MESSAGE={metadata.sanitized_error_message}", flush=True)

        if request_error is not None:
            category = failure_category(
                request_error,
                metadata.http_status if metadata else None,
                metadata.http_error_code if metadata else None,
            )
            print(f"PHASE 6.5B PROVIDER BASE CONTRACT INCOMPLETE: {category}", flush=True)
            print("PARSER=NOT_REACHED", flush=True)
            return 1

        assert reply is not None
        try:
            proposal = DecisionParser().parse(reply.raw_text)
        except DecisionParseError:
            print("PHASE 6.5B PROVIDER BASE CONTRACT INCOMPLETE: INVALID_JSON", flush=True)
            print("PARSER=FAIL", flush=True)
            return 1
        print("PARSER=PASS", flush=True)
        print("PROPOSAL=" + json.dumps(
            {"action": proposal.action.value, "target": proposal.target},
            separators=(",", ":"),
        ), flush=True)
        print("PHASE 6.5B PROVIDER BASE CONTRACT PASS", flush=True)
        return 0
    finally:
        await client.aclose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
