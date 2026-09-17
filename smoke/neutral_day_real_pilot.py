"""Run the one-time, three-day Research A1 B0 real-provider pilot.

This entry point is deliberately separate from the offline benchmark. Run it
only after the full test suite and neutral-day offline smoke have passed.
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
OUTPUT_ROOT = ROOT / "run" / "evaluation" / "neutral_day"
START_MARKER = OUTPUT_ROOT / "real_b0_started.json"
REAL_DAYS = 3
REQUEST_TIMEOUT_SECONDS = 60
load_dotenv(ENV_FILE)

from agentsociety2.society import AgentSociety  # noqa: E402
from social_sim.daily.models import DailyEpisodeResult, DailyTerminationReason  # noqa: E402
from social_sim.daily.report import write_daily_report  # noqa: E402
from social_sim.daily.runner import (  # noqa: E402
    MAX_DECISIONS_PER_DAY, DailyEpisodeRunner, neutral_day_initial_world,
)
from social_sim.daily.support import (  # noqa: E402
    BehaviorSupportPolicy, SupportCondition, TOY_UNCALIBRATED_PRIORS,
)
from social_sim.daily.validation import validate_daily_trajectory  # noqa: E402
from social_sim.decision import OpenAICompatibleDecisionClient  # noqa: E402
from social_sim.decision.config import CODING_PLAN, DecisionProviderConfig  # noqa: E402
from social_sim.router import DeterministicRouter  # noqa: E402
from social_sim.world.env import RuleWorldEnv  # noqa: E402


class SecretLeakError(RuntimeError):
    """A pilot artifact crossed the no-secret/no-reasoning boundary."""


class ArchitectureFailure(RuntimeError):
    """A deterministic invariant failed; do not attempt the next real day."""


async def forbidden_completion(*args: object, **kwargs: object) -> None:
    raise AssertionError("A deterministic subsystem attempted an LLM call")


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
    """Inspect only this run's artifacts; never echo offending content."""
    forbidden = re.compile(r"(?i)authorization|bearer\s|reasoning_content|<think|api[_-]?key")
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        content = path.read_bytes().decode("utf-8", errors="ignore")
        if forbidden.search(content) or any(secret in content for secret in secrets):
            raise SecretLeakError("SECRET_LEAK_DETECTED")


def _validate_day(result: DailyEpisodeResult, day_number: int) -> None:
    validate_daily_trajectory(result)
    if result.episode_id != f"neutral-day-{day_number:06d}":
        raise ArchitectureFailure("episode identity changed")
    if result.decision_count > MAX_DECISIONS_PER_DAY:
        raise ArchitectureFailure("per-day decision cap exceeded")
    if result.provider_request_count > MAX_DECISIONS_PER_DAY:
        raise ArchitectureFailure("per-day provider request cap exceeded")
    if result.provider_request_count > result.decision_count:
        raise ArchitectureFailure("more provider requests than decisions")
    if result.termination_reason is DailyTerminationReason.DAY_END and len(result.ticks) != 72:
        raise ArchitectureFailure("DAY_END without 72 ticks")
    if any(step.prompt is not None for step in result.trajectory.steps):
        raise ArchitectureFailure("raw prompt was retained")


async def main() -> None:
    if START_MARKER.exists():
        raise RuntimeError("RESEARCH_A1_REAL_B0_ALREADY_STARTED")
    config = DecisionProviderConfig.from_env()
    if config.model != "ark-code-latest" or config.base_url_category != CODING_PLAN:
        raise RuntimeError("RESEARCH_A1_PROVIDER_CONFIG_MISMATCH")
    secrets = _secret_values(config.api_key)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = OUTPUT_ROOT / f"real_b0_{stamp}"
    provider = OpenAICompatibleDecisionClient(
        base_url=config.api_base,
        api_key=config.api_key,
        model=config.model,
        timeout_seconds=REQUEST_TIMEOUT_SECONDS,
        minimal_request=True,
    )
    world_env = RuleWorldEnv(neutral_day_initial_world())
    router = DeterministicRouter(env_modules=[world_env])
    router._coder_dispatcher.call = forbidden_completion
    router._summary_dispatcher.call = forbidden_completion
    router.acompletion = forbidden_completion
    router.acompletion_with_system_prompt = forbidden_completion
    router.generate_world_description_from_tools = forbidden_completion
    society: AgentSociety | None = None
    results: list[DailyEpisodeResult] = []
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
        _write_json_new(output / "experiment_config.json", {
            "experiment_type": "neutral_day_idle_benchmark",
            "planned_days": REAL_DAYS,
            "support_condition": SupportCondition.B0_NONE.value,
            "support_source": TOY_UNCALIBRATED_PRIORS,
            "real_behavior_corpus_used": False,
            "provider_alias": config.model,
            "decision_client_type": "OpenAICompatibleDecisionClient",
            "minimal_request": True,
            "request_fields": ["model", "messages"],
            "request_timeout_seconds": REQUEST_TIMEOUT_SECONDS,
            "transport_retries": 0,
            "max_decisions_per_day": MAX_DECISIONS_PER_DAY,
            "max_provider_requests_total": REAL_DAYS * MAX_DECISIONS_PER_DAY,
            "simulation_start": "06:00",
            "simulation_end": "24:00",
            "tick_minutes": 15,
            "needs_parameter_status": "UNCALIBRATED_BASELINE",
        })
        _audit_artifacts(output, secrets)
        # This global marker precedes the first model call, so an interrupted
        # or poor pilot cannot silently be rerun as a fresh three-day sample.
        _write_json_new(START_MARKER, {
            "experiment_id": output.name,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "planned_days": REAL_DAYS,
            "support_condition": SupportCondition.B0_NONE.value,
        })
        started = True
        runner = DailyEpisodeRunner(
            provider,
            output_dir=output,
            support_policy=BehaviorSupportPolicy(SupportCondition.B0_NONE),
            max_decisions_per_day=MAX_DECISIONS_PER_DAY,
            model_name=config.model,
        )
        for day_number in range(1, REAL_DAYS + 1):
            result = await runner.run_episode(day_number)
            _validate_day(result, day_number)
            results.append(result)
            _audit_artifacts(output, secrets)
            print(
                f"DAY={day_number}/{REAL_DAYS} "
                f"TERMINATION={result.termination_reason.value} "
                f"TICKS={len(result.ticks)} "
                f"DECISIONS={result.decision_count} "
                f"REQUESTS={result.provider_request_count} "
                f"IDLE_MINUTES={result.idle_metrics['idle_minutes']}",
                flush=True,
            )
            if result.termination_reason is DailyTerminationReason.ARCHITECTURE_ERROR:
                raise ArchitectureFailure("deterministic decision pipeline failed")
        if len(results) != REAL_DAYS:
            raise ArchitectureFailure("pilot did not execute three days")
        write_daily_report(output, results, provider_alias=config.model)
        _audit_artifacts(output, secrets)
        env_calls = sum(stat.call_count for stat in router.get_token_usages().values())
        if env_calls:
            raise ArchitectureFailure("environment unexpectedly used an LLM")
        total_requests = sum(day.provider_request_count for day in results)
        if total_requests != provider.provider_request_count:
            raise ArchitectureFailure("provider request accounting mismatch")
        if total_requests > REAL_DAYS * MAX_DECISIONS_PER_DAY:
            raise ArchitectureFailure("pilot request budget exceeded")
        print("NEUTRAL_DAY_REAL_B0_EXECUTED", flush=True)
        print(f"ARTIFACT_DIR={output}", flush=True)
        print(f"DAYS={len(results)}", flush=True)
        print(f"PROVIDER_REQUESTS={total_requests}", flush=True)
        print("ENVIRONMENT_LLM=0 RULE_LLM=0 REDUCER_LLM=0 JUDGE_LLM=0", flush=True)
    except Exception as error:
        if started:
            if not (output / "pilot_abort.json").exists():
                _write_json_new(output / "pilot_abort.json", {
                    "status": "RESEARCH_A1_INCOMPLETE",
                    "reason_type": type(error).__name__,
                    "days_recorded": len(results),
                    "recorded_day_terminations": [
                        day.termination_reason.value for day in results
                    ],
                    "recorded_day_ticks": [len(day.ticks) for day in results],
                    "provider_requests": provider.provider_request_count,
                })
            print(f"PILOT_STOPPED={type(error).__name__}", flush=True)
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
