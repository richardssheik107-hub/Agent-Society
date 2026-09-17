"""Run the one-time, 32-episode Phase 8A real-provider context pilot."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values, load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "third_party" / "AgentSociety" / ".env"
OUTPUT_ROOT = ROOT / "run" / "evaluation" / "context_ablation"
load_dotenv(ENV_FILE)

from agentsociety2.society import AgentSociety  # noqa: E402
from social_sim.decision import OpenAICompatibleDecisionClient  # noqa: E402
from social_sim.decision.config import CODING_PLAN, DecisionProviderConfig  # noqa: E402
from social_sim.evaluation.ablation_metrics import aggregate_ablation_metrics  # noqa: E402
from social_sim.evaluation.ablation_report import write_ablation_report  # noqa: E402
from social_sim.evaluation.ablation_runner import (  # noqa: E402
    MAX_REAL_EPISODES,
    MAX_REAL_PROVIDER_REQUESTS,
    POLICY_NAMES,
    REPETITIONS_PER_CELL,
    AblationExperimentRunner,
    ProviderInstabilityError,
    ScheduleEntry,
    build_experiment_config,
    build_interleaved_schedule,
)
from social_sim.evaluation.ablation_scenarios import SCENARIO_VARIANTS  # noqa: E402
from social_sim.evaluation.models import EpisodeResult, world_snapshot  # noqa: E402
from social_sim.evaluation.runner import lunch_initial_world  # noqa: E402
from social_sim.evaluation.validation import validate_trajectory  # noqa: E402
from social_sim.router import DeterministicRouter  # noqa: E402
from social_sim.world.env import RuleWorldEnv  # noqa: E402


class SecretLeakError(RuntimeError):
    """An experiment artifact crossed the frozen privacy boundary."""


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
    forbidden = re.compile(r"(?i)authorization|bearer\s|reasoning_content|<think|api[_-]?key")
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        content = path.read_bytes().decode("utf-8", errors="ignore")
        if forbidden.search(content) or any(secret in content for secret in secrets):
            raise SecretLeakError("SECRET_LEAK_DETECTED")


async def main() -> None:
    if (OUTPUT_ROOT / "real_pilot_started.json").exists():
        raise RuntimeError("PHASE_8A_REAL_PILOT_ALREADY_STARTED")
    config = DecisionProviderConfig.from_env()
    if config.model != "ark-code-latest" or config.base_url_category != CODING_PLAN:
        raise RuntimeError("PHASE_8A_PROVIDER_CONFIG_MISMATCH")
    schedule = build_interleaved_schedule()
    experiment = build_experiment_config(
        provider_alias=config.model,
        decision_client_type="OpenAICompatibleDecisionClient",
        schedule=schedule,
    )
    experiment_hash = str(experiment["experiment_config_hash"])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = OUTPUT_ROOT / f"phase8a_context_ablation_{stamp}"
    secrets = _secret_values(config.api_key)
    _audit_artifacts(OUTPUT_ROOT, secrets)
    provider = OpenAICompatibleDecisionClient(
        base_url=config.api_base,
        api_key=config.api_key,
        model=config.model,
        timeout_seconds=60,
        minimal_request=True,
    )
    world_env = RuleWorldEnv(lunch_initial_world())
    router = DeterministicRouter(env_modules=[world_env])
    router._coder_dispatcher.call = forbidden_completion
    router._summary_dispatcher.call = forbidden_completion
    router.acompletion = forbidden_completion
    router.acompletion_with_system_prompt = forbidden_completion
    router.generate_world_description_from_tools = forbidden_completion
    society: AgentSociety | None = None
    results: list[EpisodeResult] = []
    started = False
    try:
        society = AgentSociety(
            agent_specs=[], agent_class_name="PersonAgent", env_router=router,
            start_t=lunch_initial_world().time,
            run_dir=output / "agentsociety_runtime", enable_replay=False,
        )
        await asyncio.wait_for(society.init(), timeout=90)
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        output.mkdir(parents=True, exist_ok=True)
        _write_json_new(output / "experiment_config.json", experiment)
        (output / "trajectories.jsonl").open("x", encoding="utf-8").close()
        _audit_artifacts(OUTPUT_ROOT, secrets)
        # Global marker makes a second invocation impossible even after a partial run.
        _write_json_new(OUTPUT_ROOT / "real_pilot_started.json", {
            "experiment_id": output.name,
            "experiment_config_hash": experiment_hash,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "planned_episodes": MAX_REAL_EPISODES,
        })
        started = True

        def after_episode(entry: ScheduleEntry, result: EpisodeResult) -> None:
            validate_trajectory(result)
            if result.experiment_config_hash != experiment_hash:
                raise RuntimeError("Experiment hash changed within pilot")
            if result.model_start_state != world_snapshot(lunch_initial_world()):
                raise RuntimeError("Model-start WorldState changed within pilot")
            if result.decision_count > 5 or result.total_provider_requests > 5:
                raise RuntimeError("Per-episode decision/request budget exceeded")
            results.append(result)
            _audit_artifacts(OUTPUT_ROOT, secrets)
            print(
                f"EPISODE={entry.episode_index}/32 "
                f"CELL={entry.context_policy_name}/{entry.scenario_variant.value} "
                f"RESULT={result.termination_reason.value} "
                f"DECISIONS={result.decision_count} "
                f"REQUESTS={result.total_provider_requests}",
                flush=True,
            )

        runner = AblationExperimentRunner(
            provider, output_dir=output,
            experiment_config_hash=experiment_hash,
            decision_policy_name="real_provider", model_name=config.model,
        )
        try:
            await runner.run(schedule, on_episode=after_episode)
        except ProviderInstabilityError:
            _write_json_new(output / "pilot_abort.json", {
                "status": "PHASE 8A INCOMPLETE — PROVIDER INSTABILITY",
                "episodes_completed": len(results),
                "provider_requests": provider.provider_request_count,
            })
            print("PHASE 8A INCOMPLETE — PROVIDER INSTABILITY", flush=True)
            raise
        if len(results) != MAX_REAL_EPISODES:
            raise RuntimeError("Incomplete schedule without an abort")
        scenarios = tuple(item.value for item in SCENARIO_VARIANTS)
        summary = aggregate_ablation_metrics(results, policies=POLICY_NAMES, scenarios=scenarios)
        if summary.total_provider_requests > MAX_REAL_PROVIDER_REQUESTS:
            raise RuntimeError("Overall provider request budget exceeded")
        write_ablation_report(
            output, summary, results, policies=POLICY_NAMES, scenarios=scenarios,
            repetitions_per_cell=REPETITIONS_PER_CELL, provider_alias=config.model,
            experiment_config_hash=experiment_hash,
        )
        _audit_artifacts(OUTPUT_ROOT, secrets)
        env_calls = sum(stat.call_count for stat in router.get_token_usages().values())
        if env_calls:
            raise RuntimeError("Environment unexpectedly used an LLM")
        print("CONTEXT_ABLATION_REAL_PILOT_EXECUTED", flush=True)
        print(f"ARTIFACT_DIR={output}", flush=True)
        print(f"EPISODES={len(results)}", flush=True)
        print(f"SUCCESS={sum(item.success for item in results)}", flush=True)
        print(f"PROVIDER_REQUESTS={summary.total_provider_requests}", flush=True)
        print(f"ACTUAL_MODELS={json.dumps(summary.provider_model_counts, separators=(',', ':'))}", flush=True)
        stable = "UNKNOWN" if summary.model_backend_stable is None else (
            "YES" if summary.model_backend_stable else "NO"
        )
        print(f"MODEL_BACKEND_STABLE={stable}", flush=True)
        print("ENVIRONMENT_LLM=0 RULE_LLM=0 REDUCER_LLM=0 JUDGE_LLM=0", flush=True)
    except Exception as error:
        if started:
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
