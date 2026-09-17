"""One-shot 36-request real Decision Output Contract stress pilot.

Run with the AgentSociety virtual environment and project PYTHONPATH. The
global marker is created before the first provider call, so no failed case is
automatically repeated and a second real pilot is refused.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values, load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "third_party" / "AgentSociety" / ".env"
OUTPUT_ROOT = ROOT / "run" / "evaluation" / "decision_contract_stress"
START_MARKER = OUTPUT_ROOT / "real_stress_started.json"
TIMEOUT_SECONDS = 60.0
load_dotenv(ENV_FILE)

from social_sim.decision import OpenAICompatibleDecisionClient  # noqa: E402
from social_sim.decision.config import CODING_PLAN, DecisionProviderConfig  # noqa: E402
from social_sim.evaluation.decision_contract_stress import (  # noqa: E402
    STRESS_CASES, STRESS_REQUESTS, StressRequestResult,
    run_decision_contract_stress, stress_schedule,
)
from social_sim.evaluation.provider_reliability import decision_client_config_hash  # noqa: E402


def _write_json_new(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as target:
        json.dump(value, target, ensure_ascii=False, indent=2, allow_nan=False)
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


def _summary_markdown(summary: dict[str, object]) -> str:
    lines = [
        "# Research A1.1b — Decision Contract Stress",
        "",
        f"Result: {'PASS' if summary['engineering_gate_pass'] else 'FAIL'}",
        "Engineering gate only; 36 sequential requests are not a statistical claim.",
        "Prepared Neutral-Day contexts use the production ContextCompiler and PromptBuilder; no world execution or RuleEngine runs.",
        "Each case has three interleaved single-attempt requests; no provider retry, LLM repair, or hidden reasoning storage.",
        "",
        f"Requests: {summary['requests_total']}",
        f"Provider success rate: {summary['provider_success_rate']}",
        f"Strict valid rate: {summary['strict_valid_rate']}",
        f"Recoverable valid rate: {summary['recoverable_valid_rate']}",
        f"Semantic invalid rate: {summary['semantic_invalid_rate']}",
        f"Format failure rate: {summary['format_failure_rate']}",
        f"Failure types: {json.dumps(summary['failure_type_counts'], sort_keys=True)}",
        f"Repair types: {json.dumps(summary['repair_applied_counts'], sort_keys=True)}",
        f"Latency avg / p50 / p95 (seconds): {summary['avg_latency']} / {summary['p50_latency']} / {summary['p95_latency']}",
        f"Backend models: {json.dumps(summary['provider_model_counts'], sort_keys=True)}",
        f"Backend stable: {summary['model_backend_stable']}",
        f"Input / output / reasoning tokens: {summary['input_tokens']} / {summary['output_tokens']} / {summary['reasoning_tokens']}",
        f"Recovery recommended for full-day: {summary['recovery_recommended_for_full_day']}",
        f"Decision client config hash: {summary['decision_client_config_hash']}",
        "",
        "Only a redacted, at-most-500-character assistant-final excerpt is retained per request; prompt bodies, headers, secrets, and hidden reasoning text are omitted.",
    ]
    return "\n".join(lines) + "\n"


async def main() -> None:
    if START_MARKER.exists():
        raise RuntimeError("DECISION_CONTRACT_STRESS_ALREADY_STARTED")
    config = DecisionProviderConfig.from_env()
    if config.model != "ark-code-latest" or config.base_url_category != CODING_PLAN:
        raise RuntimeError("PROVIDER_CONFIG_MISMATCH")
    config_hash = decision_client_config_hash(
        config, timeout_seconds=TIMEOUT_SECONDS,
        request_mode="MODEL_MESSAGES_ONLY", max_retries=0,
    )
    secrets = _secret_values(config.api_key)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = OUTPUT_ROOT / f"real_stress_{stamp}"
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=False)
    schedule = stress_schedule()
    _write_json_new(output / "config.json", {
        "experiment_type": "decision_output_contract_stress",
        "decision_client_config_hash": config_hash,
        "provider_base_category": config.base_url_category,
        "model_alias": config.model,
        "request_mode": "MODEL_MESSAGES_ONLY",
        "timeout_seconds": TIMEOUT_SECONDS,
        "max_retries": 0,
        "cases": len(STRESS_CASES),
        "repetitions": 3,
        "planned_requests": STRESS_REQUESTS,
        "world_execution": False,
    })
    schedule_data = [item.to_dict() for item in schedule]
    _write_json_new(output / "schedule.json", schedule_data)
    # Both names are requested in the phase specification; contents match.
    _write_json_new(output / "stress_schedule.json", schedule_data)
    _audit_artifacts(output, secrets)
    client = OpenAICompatibleDecisionClient(
        base_url=config.api_base, api_key=config.api_key, model=config.model,
        timeout_seconds=TIMEOUT_SECONDS, minimal_request=True,
    )
    started = False
    try:
        _write_json_new(START_MARKER, {
            "run_directory": output.name,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "planned_requests": STRESS_REQUESTS,
            "decision_client_config_hash": config_hash,
        })
        started = True
        with (output / "requests.jsonl").open("x", encoding="utf-8") as records:
            def on_result(item: StressRequestResult) -> None:
                records.write(json.dumps(item.to_dict(), ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
                records.flush()
                print(
                    f"REQUEST={item.request_index}/{STRESS_REQUESTS} CASE={item.case_id} "
                    f"PROVIDER={'OK' if item.provider_success else 'FAIL'} "
                    f"STRICT={int(item.strict_valid)} RECOVERABLE={int(item.recoverable_valid)} "
                    f"FAILURE={item.failure_type or 'NONE'} LATENCY_SECONDS={item.latency_seconds:.2f}",
                    flush=True,
                )

            result = await run_decision_contract_stress(
                client, schedule=schedule, secrets=secrets, on_result=on_result,
            )
        if client.provider_request_count != STRESS_REQUESTS:
            raise RuntimeError("PROVIDER_REQUEST_ACCOUNTING_MISMATCH")
        summary = result.summary()
        summary["decision_client_config_hash"] = config_hash
        _write_json_new(output / "summary.json", summary)
        with (output / "summary.md").open("x", encoding="utf-8") as report:
            report.write(_summary_markdown(summary))
        _audit_artifacts(output, secrets)
        print("DECISION_CONTRACT_STRESS_RESULT", flush=True)
        print(f"ARTIFACT_DIR={output}", flush=True)
        print(f"ENGINEERING_GATE={'PASS' if summary['engineering_gate_pass'] else 'FAIL'}", flush=True)
        print(f"PROVIDER_SUCCESS_RATE={summary['provider_success_rate']:.3f}", flush=True)
        print(f"STRICT_VALID_RATE={summary['strict_valid_rate']:.3f}", flush=True)
        print(f"RECOVERABLE_VALID_RATE={summary['recoverable_valid_rate']:.3f}", flush=True)
        print(f"SEMANTIC_INVALID_RATE={summary['semantic_invalid_rate']:.3f}", flush=True)
        print(f"RECOVERY_RECOMMENDED={'YES' if summary['recovery_recommended_for_full_day'] else 'NO'}", flush=True)
    except Exception as error:
        if started:
            log = output / "requests.jsonl"
            attempts_persisted = 0
            if log.exists():
                with log.open(encoding="utf-8") as source:
                    attempts_persisted = sum(1 for _ in source)
            _write_json_new(output / "stress_abort.json", {
                "reason_type": type(error).__name__,
                "attempts_persisted": attempts_persisted,
            })
            print(f"DECISION_CONTRACT_STRESS_STOPPED={type(error).__name__}", flush=True)
            print(f"ARTIFACT_DIR={output}", flush=True)
        raise
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
