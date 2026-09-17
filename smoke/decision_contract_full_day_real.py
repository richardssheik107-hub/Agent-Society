"""One gated B0 full-day attempt after the A1.1b contract stress pilot.

The gate decides the output-recovery flag. This file never retries a failed
decision or starts a second day, and its own start marker prevents rerunning.
"""

from __future__ import annotations

import asyncio
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from neutral_day_full_runtime_real import (  # noqa: E402
    _audit_artifacts, _decision_trace, _secret_values, _tick_timeline,
    _write_json_new, forbidden_completion,
)


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "third_party" / "AgentSociety" / ".env")
STRESS_ROOT = ROOT / "run" / "evaluation" / "decision_contract_stress"
STRESS_MARKER = STRESS_ROOT / "real_stress_started.json"
OUTPUT_ROOT = ROOT / "run" / "evaluation" / "decision_contract_full_day"
START_MARKER = OUTPUT_ROOT / "real_day_started.json"
TIMEOUT_SECONDS = 60.0
ALLOWED_REPAIRS = frozenset({
    "STRIP_CODE_FENCE", "EXTRACT_SINGLE_JSON", "ADD_NULL_TARGET",
})

from agentsociety2.society import AgentSociety  # noqa: E402
from social_sim.daily.models import DailyTerminationReason  # noqa: E402
from social_sim.daily.runner import (  # noqa: E402
    MAX_DECISIONS_PER_DAY, DailyEpisodeRunner, neutral_day_initial_world,
)
from social_sim.daily.support import BehaviorSupportPolicy, SupportCondition  # noqa: E402
from social_sim.daily.validation import validate_daily_trajectory  # noqa: E402
from social_sim.decision import OpenAICompatibleDecisionClient  # noqa: E402
from social_sim.decision.config import CODING_PLAN, DecisionProviderConfig  # noqa: E402
from social_sim.evaluation.provider_reliability import decision_client_config_hash  # noqa: E402
from social_sim.router import DeterministicRouter  # noqa: E402
from social_sim.world.env import RuleWorldEnv  # noqa: E402


def _rate(summary: dict[str, object], name: str) -> float:
    value = summary.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise RuntimeError("STRESS_GATE_INVALID")
    return float(value)


def _stress_gate(expected_hash: str) -> tuple[str, bool, dict[str, object]]:
    if not STRESS_MARKER.is_file():
        raise RuntimeError("STRESS_GATE_MISSING")
    marker = json.loads(STRESS_MARKER.read_text(encoding="utf-8"))
    run_name = marker.get("run_directory")
    if not isinstance(run_name, str) or not re.fullmatch(r"real_stress_[0-9TZ]+", run_name):
        raise RuntimeError("STRESS_RUN_ID_INVALID")
    output = (STRESS_ROOT / run_name).resolve()
    if output.parent != STRESS_ROOT.resolve():
        raise RuntimeError("STRESS_RUN_PATH_INVALID")
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    if not isinstance(summary, dict):
        raise RuntimeError("STRESS_GATE_INVALID")
    provider_rate = _rate(summary, "provider_success_rate")
    strict_rate = _rate(summary, "strict_valid_rate")
    recoverable_rate = _rate(summary, "recoverable_valid_rate")
    semantic_rate = _rate(summary, "semantic_invalid_rate")
    if (
        marker.get("decision_client_config_hash") != expected_hash
        or summary.get("decision_client_config_hash") != expected_hash
        or summary.get("requests_total") != 36
        or summary.get("engineering_gate_pass") is not True
        or provider_rate < 0.95
        or recoverable_rate < 0.95
        or semantic_rate > 0.05
        or not 0 <= strict_rate <= recoverable_rate <= 1
    ):
        raise RuntimeError("STRESS_GATE_NOT_PASSED")
    counts = summary.get("repair_applied_counts")
    if not isinstance(counts, dict):
        raise RuntimeError("STRESS_REPAIR_COUNTS_INVALID")
    for repair, count in counts.items():
        if (
            not isinstance(repair, str)
            or not repair
            or any(part not in ALLOWED_REPAIRS for part in repair.split("+"))
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
        ):
            raise RuntimeError("STRESS_UNSAFE_REPAIR")
    use_recovery = strict_rate < recoverable_rate
    if use_recovery and not any(counts.values()):
        raise RuntimeError("STRESS_RECOVERY_METRICS_INCONSISTENT")
    return run_name, use_recovery, summary


def _write_report(output: Path, result, stress_run: str, use_recovery: bool,
                  client_hash: str, provider_requests: int) -> dict[str, object]:
    steps = result.trajectory.steps
    output_failures = list(result.output_failures)
    provider_failures = list(result.provider_failures)
    strict_valid_outputs = sum(step.strict_valid is True for step in steps)
    recovered_outputs = sum(step.output_recovered for step in steps)
    semantic_invalid_outputs = sum(
        failure.get("failure_category") == "SEMANTIC_FAILURE"
        for failure in output_failures
    )
    summary = {
        "experiment_type": "decision_output_contract_full_day",
        "decision_client_config_hash": client_hash,
        "stress_run_directory": stress_run,
        "support_condition": SupportCondition.B0_NONE.value,
        "simulation_start": "06:00",
        "simulation_end_target": "24:00",
        "allow_deterministic_output_recovery": use_recovery,
        "termination": result.termination_reason.value,
        "day_outcome": result.day_outcome.value,
        "day_completed": result.day_completed,
        "behavior_metrics_valid": result.behavior_metrics_valid,
        "observed_minutes": result.observed_minutes,
        "observed_ticks": result.observed_ticks,
        "decision_count": result.decision_count,
        "provider_request_count": provider_requests,
        "decision_outputs_total": len(steps) + len(output_failures),
        "strict_valid_outputs": strict_valid_outputs,
        "recovered_outputs": recovered_outputs,
        "legacy_non_strict_accepted_outputs": sum(
            step.legacy_non_strict_acceptance for step in steps
        ),
        "semantic_invalid_outputs": semantic_invalid_outputs,
        "output_failures": output_failures,
        "provider_failures": provider_failures,
        "full_day_behavior_metrics": result.full_day_behavior_metrics if result.behavior_metrics_valid else None,
        "partial_window_metrics": result.partial_window_metrics if not result.behavior_metrics_valid else None,
        "environment_llm_calls": 0,
        "rule_llm_calls": 0,
        "reducer_llm_calls": 0,
        "judge_llm_calls": 0,
        "hidden_reasoning_stored": False,
        "raw_prompts_stored": False,
        "no_claim_of_human_realism": True,
    }
    _write_json_new(output / "full_day_output_contract_summary.json", summary)
    trace = _decision_trace(result)
    for failure in output_failures:
        trace.append({
            "decision_index": failure["decision_index"],
            "simulation_time": failure["simulation_time"],
            "trigger_reason": failure["trigger_reason"],
            "action": None,
            "target": None,
            "accepted": None,
            "reason_code": failure["failure_type"],
            "failure_category": failure["failure_category"],
            "strict_valid": failure["strict_valid"],
            "recoverable_valid": failure["recoverable_valid"],
            "activity_duration_minutes": None,
            "provider_latency_seconds": failure["latency_seconds"],
            "context_chars": None,
            "prompt_chars": None,
        })
    _write_json_new(
        output / "compact_decision_trace.json",
        sorted(trace, key=lambda row: row["decision_index"]),
    )
    _write_json_new(output / "compact_tick_timeline.json", _tick_timeline(result))
    lines = [
        "# Research A1.1b — Full-Day Output Contract", "",
        f"Stress run: {stress_run}",
        f"Recovery enabled: {use_recovery}",
        f"Day completed: {result.day_completed}",
        f"Termination: {result.termination_reason.value}",
        f"Decisions/provider requests: {result.decision_count}/{provider_requests}",
        f"Decision outputs: {summary['decision_outputs_total']}",
        f"Strict valid outputs: {strict_valid_outputs}",
        f"Recovered outputs: {recovered_outputs}",
        f"Legacy non-strict accepted outputs: {summary['legacy_non_strict_accepted_outputs']}",
        f"Semantic invalid outputs: {semantic_invalid_outputs}",
        "", "No human-likeness conclusion is drawn.",
    ]
    with (output / "full_day_output_contract_summary.md").open("x", encoding="utf-8") as target:
        target.write("\n".join(lines) + "\n")
    return summary


async def main() -> None:
    if START_MARKER.exists():
        raise RuntimeError("FULL_DAY_REAL_ATTEMPT_ALREADY_STARTED")
    config = DecisionProviderConfig.from_env()
    if config.model != "ark-code-latest" or config.base_url_category != CODING_PLAN:
        raise RuntimeError("PROVIDER_CONFIG_MISMATCH")
    client_hash = decision_client_config_hash(
        config, timeout_seconds=TIMEOUT_SECONDS,
        request_mode="MODEL_MESSAGES_ONLY", max_retries=0,
    )
    stress_run, use_recovery, _ = _stress_gate(client_hash)
    secrets = _secret_values(config.api_key)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = OUTPUT_ROOT / f"real_day_{stamp}"
    provider = OpenAICompatibleDecisionClient(
        base_url=config.api_base, api_key=config.api_key, model=config.model,
        timeout_seconds=TIMEOUT_SECONDS, minimal_request=True,
    )
    world_env = RuleWorldEnv(neutral_day_initial_world())
    router = DeterministicRouter(env_modules=[world_env])
    router._coder_dispatcher.call = forbidden_completion
    router._summary_dispatcher.call = forbidden_completion
    router.acompletion = forbidden_completion
    router.acompletion_with_system_prompt = forbidden_completion
    router.generate_world_description_from_tools = forbidden_completion
    society: AgentSociety | None = None
    started = False
    try:
        society = AgentSociety(
            agent_specs=[], agent_class_name="PersonAgent", env_router=router,
            start_t=neutral_day_initial_world().time,
            run_dir=output / "agentsociety_runtime", enable_replay=False,
        )
        await asyncio.wait_for(society.init(), timeout=90)
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        output.mkdir(parents=True, exist_ok=True)
        _write_json_new(output / "decision_client_config.json", {
            "decision_client_config_hash": client_hash,
            "provider_base_category": config.base_url_category,
            "model_alias": config.model,
            "request_mode": "MODEL_MESSAGES_ONLY",
            "timeout_seconds": TIMEOUT_SECONDS,
            "max_retries": 0,
            "allow_deterministic_output_recovery": use_recovery,
        })
        _audit_artifacts(output, secrets)
        _write_json_new(START_MARKER, {
            "run_directory": output.name,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "planned_real_days": 1,
            "stress_run_directory": stress_run,
            "decision_client_config_hash": client_hash,
            "allow_deterministic_output_recovery": use_recovery,
        })
        started = True
        print("FULL_DAY_OUTPUT_CONTRACT_START", flush=True)
        runner = DailyEpisodeRunner(
            provider, output_dir=output,
            support_policy=BehaviorSupportPolicy(SupportCondition.B0_NONE),
            max_decisions_per_day=MAX_DECISIONS_PER_DAY,
            model_name=config.model,
            allow_deterministic_output_recovery=use_recovery,
        )
        result = await runner.run_episode(1)
        validate_daily_trajectory(result)
        if result.provider_request_count != provider.provider_request_count:
            raise RuntimeError("PROVIDER_REQUEST_ACCOUNTING_MISMATCH")
        if result.decision_count > MAX_DECISIONS_PER_DAY:
            raise RuntimeError("DECISION_SAFETY_CAP_EXCEEDED")
        env_calls = sum(stat.call_count for stat in router.get_token_usages().values())
        if env_calls:
            raise RuntimeError("ENVIRONMENT_LLM_NONZERO")
        summary = _write_report(
            output, result, stress_run, use_recovery, client_hash,
            provider.provider_request_count,
        )
        _audit_artifacts(output, secrets)
        if result.day_completed and result.termination_reason is DailyTerminationReason.DAY_END:
            print("FULL_DAY_RUNTIME_PASS", flush=True)
        elif result.termination_reason is DailyTerminationReason.INVALID_MODEL_OUTPUT:
            print("FULL_DAY_RUNTIME_TRUNCATED_MODEL_OUTPUT", flush=True)
        elif result.day_outcome.value == "DAY_TRUNCATED_PROVIDER":
            print("FULL_DAY_RUNTIME_TRUNCATED_PROVIDER", flush=True)
        else:
            print(f"FULL_DAY_RUNTIME_TRUNCATED={result.day_outcome.value}", flush=True)
        print(f"ARTIFACT_DIR={output}", flush=True)
        print(f"TERMINATION={result.termination_reason.value}", flush=True)
        print(f"DAY_COMPLETED={'YES' if result.day_completed else 'NO'}", flush=True)
        print(f"BEHAVIOR_METRICS_VALID={'YES' if result.behavior_metrics_valid else 'NO'}", flush=True)
        print(f"DECISIONS={result.decision_count}", flush=True)
        print(f"PROVIDER_REQUESTS={provider.provider_request_count}", flush=True)
        print(f"STRICT_VALID_OUTPUTS={summary['strict_valid_outputs']}", flush=True)
        print(f"RECOVERED_OUTPUTS={summary['recovered_outputs']}", flush=True)
        print(f"SEMANTIC_INVALID_OUTPUTS={summary['semantic_invalid_outputs']}", flush=True)
        if result.output_failures:
            failure = result.output_failures[0]
            for key in (
                "simulation_time", "decision_index", "failure_type", "strict_valid",
                "recoverable_valid", "finish_reason", "content_chars", "latency_seconds",
                "input_tokens", "output_tokens", "reasoning_tokens",
            ):
                print(f"OUTPUT_FAILURE_{key.upper()}={failure.get(key)}", flush=True)
        print("ENVIRONMENT_LLM=0 RULE_LLM=0 REDUCER_LLM=0 JUDGE_LLM=0", flush=True)
    except Exception as error:
        if started:
            if not (output / "runtime_abort.json").exists():
                _write_json_new(output / "runtime_abort.json", {
                    "status": "A1.1B_RUNTIME_ABORTED",
                    "reason_type": type(error).__name__,
                    "provider_requests": provider.provider_request_count,
                })
            print(f"FULL_DAY_RUNTIME_STOPPED={type(error).__name__}", flush=True)
            print(f"ARTIFACT_DIR={output}", flush=True)
        raise
    finally:
        try:
            if society is not None:
                await asyncio.wait_for(society.close(), timeout=45)
        finally:
            await provider.aclose()


if __name__ == "__main__":
    asyncio.run(main())
