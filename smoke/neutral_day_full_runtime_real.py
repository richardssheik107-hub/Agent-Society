"""One B0 real-day attempt, gated by the separate provider reliability probe."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values, load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "third_party" / "AgentSociety" / ".env"
RELIABILITY_ROOT = ROOT / "run" / "evaluation" / "provider_reliability"
OUTPUT_ROOT = ROOT / "run" / "evaluation" / "neutral_day_stability"
START_MARKER = OUTPUT_ROOT / "real_day_started.json"
TIMEOUT_SECONDS = 60.0
load_dotenv(ENV_FILE)

from agentsociety2.society import AgentSociety  # noqa: E402
from social_sim.daily.models import DailyTerminationReason  # noqa: E402
from social_sim.daily.runner import (  # noqa: E402
    MAX_DECISIONS_PER_DAY, DailyEpisodeRunner, neutral_day_initial_world,
)
from social_sim.daily.support import BehaviorSupportPolicy, SupportCondition  # noqa: E402
from social_sim.daily.validation import validate_daily_trajectory  # noqa: E402
from social_sim.decision import OpenAICompatibleDecisionClient  # noqa: E402
from social_sim.decision.config import CODING_PLAN, DecisionProviderConfig  # noqa: E402
from social_sim.evaluation.provider_reliability import (  # noqa: E402
    RELIABILITY_REQUESTS, decision_client_config_hash,
)
from social_sim.router import DeterministicRouter  # noqa: E402
from social_sim.world.env import RuleWorldEnv  # noqa: E402


async def forbidden_completion(*args: object, **kwargs: object) -> None:
    raise AssertionError("A deterministic subsystem attempted an LLM call")


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


def _reliability_gate(expected_hash: str) -> dict[str, object]:
    marker = json.loads((RELIABILITY_ROOT / "real_30_started.json").read_text(encoding="utf-8"))
    run_name = marker.get("run_directory")
    if not isinstance(run_name, str) or not re.fullmatch(r"real_30_[0-9TZ]+", run_name):
        raise RuntimeError("RELIABILITY_RUN_ID_INVALID")
    gate = json.loads((RELIABILITY_ROOT / run_name / "reliability_gate.json").read_text(encoding="utf-8"))
    if (
        gate.get("reliability_ok") is not True
        or gate.get("requests_total") != RELIABILITY_REQUESTS
        or gate.get("decision_client_config_hash") != expected_hash
        or marker.get("decision_client_config_hash") != expected_hash
    ):
        raise RuntimeError("PROVIDER_RELIABILITY_GATE_NOT_PASSED")
    return {"run_directory": run_name, "decision_client_config_hash": expected_hash}


def _decision_trace(result) -> list[dict[str, object]]:
    trace = []
    for step in result.trajectory.steps:
        duration = 0
        if step.rule_allowed:
            for effect in step.effects:
                if effect.get("type") == "START_ACTIVITY":
                    duration = int((
                        datetime.fromisoformat(effect["end_time"])
                        - datetime.fromisoformat(step.simulation_time)
                    ).total_seconds() // 60)
        trace.append({
            "decision_index": step.step_index,
            "simulation_time": step.simulation_time,
            "trigger_reason": step.trigger_reason,
            "action": step.proposal["action"],
            "target": step.proposal["target"],
            "accepted": step.rule_allowed,
            "reason_code": step.rule_reason_code,
            "activity_duration_minutes": duration,
            "provider_latency_seconds": step.decision_latency_seconds,
            "context_chars": step.context_chars,
            "prompt_chars": step.prompt_chars,
        })
    for failure in result.provider_failures:
        trace.append({
            "decision_index": failure["decision_index"],
            "simulation_time": failure["simulation_time"],
            "trigger_reason": failure["trigger_reason"],
            "action": None,
            "target": None,
            "accepted": None,
            "reason_code": failure["failure_type"],
            "activity_duration_minutes": None,
            "provider_latency_seconds": failure["latency_seconds"],
            "context_chars": None,
            "prompt_chars": None,
        })
    return sorted(trace, key=lambda row: row["decision_index"])


def _tick_timeline(result) -> list[dict[str, object]]:
    return [{
        "time": tick.simulation_time,
        "end_time": tick.end_time,
        "activity": tick.active_activity,
        "activity_active": tick.active_activity is not None,
        "decision_triggered": tick.decision_step_index is not None,
        "trigger_reason": tick.trigger_reason,
        "completion_activities": list(tick.completed_activities),
    } for tick in result.ticks]


def _write_runtime_report(output: Path, result, client_hash: str, reliability_run: str) -> dict[str, object]:
    audit = result.activity_metrics
    summary = {
        "experiment_type": "neutral_day_full_runtime_stability",
        "decision_client_config_hash": client_hash,
        "reliability_run_directory": reliability_run,
        "support_condition": SupportCondition.B0_NONE.value,
        "simulation_start": "06:00",
        "simulation_end_target": "24:00",
        "termination": result.termination_reason.value,
        "day_outcome": result.day_outcome.value,
        "day_completed": result.day_completed,
        "behavior_metrics_valid": result.behavior_metrics_valid,
        "truncation_reason": result.truncation_reason,
        "observed_minutes": result.observed_minutes,
        "observed_ticks": result.observed_ticks,
        "decision_count": result.decision_count,
        "provider_request_count": result.provider_request_count,
        "decision_burst_count": audit["decision_burst_count"],
        "same_state_decision_count": audit["same_state_decision_count"],
        "decisions_per_sim_hour": audit["decisions_per_sim_hour"],
        "ticks_per_decision": audit["ticks_per_decision"],
        "active_minutes_per_decision": audit["active_minutes_per_decision"],
        "trigger_reason_counts": audit["trigger_reason_counts"],
        "high_decision_frequency_warning": audit["high_decision_frequency_warning"],
        "provider_failures": [dict(failure) for failure in result.provider_failures],
        "full_day_behavior_metrics": result.full_day_behavior_metrics if result.behavior_metrics_valid else None,
        "partial_window_metrics": result.partial_window_metrics if not result.behavior_metrics_valid else None,
        "hidden_reasoning_stored": False,
        "raw_prompts_stored": False,
        "no_claim_of_human_realism": True,
    }
    _write_json_new(output / "full_day_runtime_summary.json", summary)
    _write_json_new(output / "compact_decision_trace.json", _decision_trace(result))
    _write_json_new(output / "compact_tick_timeline.json", _tick_timeline(result))
    lines = [
        "# Research A1.1 — Full-Day Runtime Stability", "",
        "No claim of human realism.",
        f"Day outcome: {result.day_outcome.value}",
        f"Termination: {result.termination_reason.value}",
        f"Observed ticks/minutes: {result.observed_ticks}/{result.observed_minutes}",
        f"Decision attempts/provider requests: {result.decision_count}/{result.provider_request_count}",
        f"Decision bursts: {audit['decision_burst_count']}",
        f"Same-state decisions: {audit['same_state_decision_count']}",
        f"Behavior metrics valid: {'YES' if result.behavior_metrics_valid else 'NO'}",
        "",
    ]
    if result.behavior_metrics_valid:
        lines.extend(["## Full-day behavior metrics", ""])
        lines.extend(f"- {key}: {value}" for key, value in result.full_day_behavior_metrics.items())
    else:
        lines.extend(["## Partial observed window only", ""])
        lines.extend(f"- {key}: {value}" for key, value in result.partial_window_metrics.items())
        lines.append("No full-day idle, activity-mix, need, or obligation metric is valid.")
    with (output / "full_day_runtime_summary.md").open("x", encoding="utf-8") as target:
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
    gate = _reliability_gate(client_hash)
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
            "client_class": "OpenAICompatibleDecisionClient",
        })
        _audit_artifacts(output, secrets)
        _write_json_new(START_MARKER, {
            "run_directory": output.name,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "planned_real_days": 1,
            "decision_client_config_hash": client_hash,
            "reliability_run_directory": gate["run_directory"],
        })
        started = True
        print("FULL_DAY_RUNTIME_START", flush=True)
        print("SIM_START=06:00", flush=True)
        print("SIM_END_TARGET=24:00", flush=True)
        runner = DailyEpisodeRunner(
            provider, output_dir=output,
            support_policy=BehaviorSupportPolicy(SupportCondition.B0_NONE),
            max_decisions_per_day=MAX_DECISIONS_PER_DAY,
            model_name=config.model,
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
        _write_runtime_report(output, result, client_hash, gate["run_directory"])
        _audit_artifacts(output, secrets)
        if result.day_completed and result.termination_reason is DailyTerminationReason.DAY_END:
            print("FULL_DAY_RUNTIME_PASS", flush=True)
        elif result.day_outcome.value == "DAY_TRUNCATED_PROVIDER":
            print("FULL_DAY_RUNTIME_TRUNCATED_PROVIDER", flush=True)
        else:
            print(f"FULL_DAY_RUNTIME_TRUNCATED={result.day_outcome.value}", flush=True)
        print(f"ARTIFACT_DIR={output}", flush=True)
        print(f"TERMINATION={result.termination_reason.value}", flush=True)
        print(f"DAY_COMPLETED={'YES' if result.day_completed else 'NO'}", flush=True)
        print(f"BEHAVIOR_METRICS_VALID={'YES' if result.behavior_metrics_valid else 'NO'}", flush=True)
        print(f"OBSERVED_MINUTES={result.observed_minutes}", flush=True)
        print(f"TICKS={result.observed_ticks}", flush=True)
        print(f"DECISIONS={result.decision_count}", flush=True)
        print(f"PROVIDER_REQUESTS={result.provider_request_count}", flush=True)
        print(f"DECISION_BURSTS={result.activity_metrics['decision_burst_count']}", flush=True)
        print(f"SAME_STATE_DECISIONS={result.activity_metrics['same_state_decision_count']}", flush=True)
        print("ENVIRONMENT_LLM=0 RULE_LLM=0 REDUCER_LLM=0 JUDGE_LLM=0", flush=True)
    except Exception as error:
        if started:
            if not (output / "runtime_abort.json").exists():
                _write_json_new(output / "runtime_abort.json", {
                    "status": "A1.1_RUNTIME_ABORTED",
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
