"""One-time 30-request provider reliability probe; no world or Ray runtime."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values, load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "third_party" / "AgentSociety" / ".env"
OUTPUT_ROOT = ROOT / "run" / "evaluation" / "provider_reliability"
START_MARKER = OUTPUT_ROOT / "real_30_started.json"
TIMEOUT_SECONDS = 60.0
load_dotenv(ENV_FILE)

from social_sim.decision import OpenAICompatibleDecisionClient  # noqa: E402
from social_sim.decision.config import CODING_PLAN, DecisionProviderConfig  # noqa: E402
from social_sim.evaluation.provider_reliability import (  # noqa: E402
    RELIABILITY_REQUESTS,
    ProviderRequestResult,
    decision_client_config_hash,
    run_provider_reliability,
    write_provider_reliability_report,
)


def _write_json_new(path: Path, data: object) -> None:
    with path.open("x", encoding="utf-8") as target:
        json.dump(data, target, ensure_ascii=False, indent=2, allow_nan=False)
        target.write("\n")


def _secret_values(api_key: str) -> tuple[str, ...]:
    values = {api_key}
    for name, value in dotenv_values(ENV_FILE).items():
        if value and len(value) >= 12 and any(
            term in name.upper() for term in ("KEY", "SECRET", "TOKEN", "PASSWORD")
        ):
            values.add(value)
    return tuple(values)


def _audit_artifacts(directory: Path, secrets: tuple[str, ...]) -> None:
    forbidden = re.compile(r"(?i)authorization|bearer\s|reasoning_content|<think|api[_-]?key")
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        if path.name == ".env":
            raise RuntimeError("SECRET_OR_REASONING_LEAK_DETECTED")
        content = path.read_bytes().decode("utf-8", errors="ignore")
        if forbidden.search(content) or any(secret in content for secret in secrets):
            raise RuntimeError("SECRET_OR_REASONING_LEAK_DETECTED")


async def main() -> None:
    if START_MARKER.exists():
        raise RuntimeError("PROVIDER_RELIABILITY_ALREADY_STARTED")
    config = DecisionProviderConfig.from_env()
    if config.model != "ark-code-latest" or config.base_url_category != CODING_PLAN:
        raise RuntimeError("PROVIDER_CONFIG_MISMATCH")
    client_hash = decision_client_config_hash(
        config, timeout_seconds=TIMEOUT_SECONDS,
        request_mode="MODEL_MESSAGES_ONLY", max_retries=0,
    )
    secrets = _secret_values(config.api_key)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = OUTPUT_ROOT / f"real_30_{stamp}"
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=False)
    _write_json_new(output / "decision_client_config.json", {
        "decision_client_config_hash": client_hash,
        "provider_base_category": config.base_url_category,
        "model_alias": config.model,
        "request_mode": "MODEL_MESSAGES_ONLY",
        "timeout_seconds": TIMEOUT_SECONDS,
        "max_retries": 0,
        "client_class": "OpenAICompatibleDecisionClient",
    })
    _audit_artifacts(output, secrets)
    client = OpenAICompatibleDecisionClient(
        base_url=config.api_base, api_key=config.api_key, model=config.model,
        timeout_seconds=TIMEOUT_SECONDS, minimal_request=True,
    )
    started = False
    try:
        # Global marker precedes the first request. Failed requests are never rerun.
        _write_json_new(START_MARKER, {
            "run_directory": output.name,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "planned_requests": RELIABILITY_REQUESTS,
            "decision_client_config_hash": client_hash,
        })
        started = True
        with (output / "provider_requests.jsonl").open("x", encoding="utf-8") as records:
            def on_result(item: ProviderRequestResult) -> None:
                records.write(json.dumps(item.to_dict(), ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
                records.flush()
                print(
                    f"REQUEST={item.request_index}/{RELIABILITY_REQUESTS} "
                    f"SUCCESS={'YES' if item.success else 'NO'} "
                    f"FAILURE={item.failure_type or 'NONE'} "
                    f"LATENCY_SECONDS={item.latency_seconds:.2f}",
                    flush=True,
                )

            result = await run_provider_reliability(
                client, requests=RELIABILITY_REQUESTS,
                config_hash=client_hash, on_result=on_result,
            )
        if client.provider_request_count != RELIABILITY_REQUESTS:
            raise RuntimeError("PROVIDER_REQUEST_ACCOUNTING_MISMATCH")
        write_provider_reliability_report(result, output)
        summary = result.summary()
        _write_json_new(output / "reliability_gate.json", {
            "decision_client_config_hash": client_hash,
            "requests_total": summary["requests_total"],
            "reliability_ok": result.reliability_ok,
            "gate_result": summary["reliability_result"],
        })
        _audit_artifacts(output, secrets)
        print("PROVIDER_RELIABILITY_RESULT", flush=True)
        print(f"ARTIFACT_DIR={output}", flush=True)
        print(f"REQUESTS={summary['requests_total']}", flush=True)
        print(f"SUCCESS={summary['requests_success']}", flush=True)
        print(f"SUCCESS_RATE={summary['success_rate']:.3f}", flush=True)
        print(f"TIMEOUTS={summary['timeout_count']}", flush=True)
        print(f"TIMEOUT_RATE={summary['timeout_rate']:.3f}", flush=True)
        print(f"AVG_LATENCY={summary['avg_latency']:.2f}", flush=True)
        print(f"P50_LATENCY={summary['p50_latency']:.2f}", flush=True)
        print(f"P95_LATENCY={summary['p95_latency']:.2f}", flush=True)
        print(f"PROVIDER_MODELS={json.dumps(summary['provider_model_counts'], separators=(',', ':'))}", flush=True)
        print(f"MODEL_BACKEND_STABLE={summary['model_backend_stable']}", flush=True)
        print(f"RELIABILITY_OK={'YES' if result.reliability_ok else 'NO'}", flush=True)
    except Exception as error:
        if started:
            request_log = output / "provider_requests.jsonl"
            attempts_persisted = 0
            if request_log.exists():
                with request_log.open(encoding="utf-8") as source:
                    attempts_persisted = sum(1 for _ in source)
            _write_json_new(output / "reliability_abort.json", {
                "reason_type": type(error).__name__,
                "attempts_persisted": attempts_persisted,
            })
            print(f"PROVIDER_RELIABILITY_STOPPED={type(error).__name__}", flush=True)
            print(f"ARTIFACT_DIR={output}", flush=True)
        raise
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
