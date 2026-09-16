"""Exactly three sequential real-provider lunch episodes, with no retry."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "run" / "evaluation" / "real_pilot"
REAL_EPISODES = 3
load_dotenv(ROOT / "third_party" / "AgentSociety" / ".env")

from agentsociety2.society import AgentSociety  # noqa: E402
from social_sim.decision import OpenAICompatibleDecisionClient  # noqa: E402
from social_sim.decision.config import DecisionProviderConfig  # noqa: E402
from social_sim.evaluation.metrics import MetricsAggregator, trajectory_signature  # noqa: E402
from social_sim.evaluation.report import write_benchmark_report  # noqa: E402
from social_sim.evaluation.runner import EpisodeRunner, LunchBenchmarkScenario, lunch_initial_world  # noqa: E402
from social_sim.evaluation.validation import validate_trajectory  # noqa: E402
from social_sim.router import DeterministicRouter  # noqa: E402
from social_sim.world.env import RuleWorldEnv  # noqa: E402


async def forbidden_completion(*args: object, **kwargs: object) -> None:
    raise AssertionError("The deterministic environment must not call an LLM")


async def main() -> None:
    config = DecisionProviderConfig.from_env()
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
    try:
        society = AgentSociety(
            agent_specs=[],
            agent_class_name="PersonAgent",
            env_router=router,
            start_t=lunch_initial_world().time,
            run_dir=OUTPUT / "agentsociety_runtime",
            enable_replay=False,
        )
        await asyncio.wait_for(society.init(), timeout=90)
        # A marker prevents an accidental second real pilot, including after a
        # partial first run. It contains only a timestamp, never credentials.
        OUTPUT.mkdir(parents=True, exist_ok=True)
        marker = OUTPUT / "pilot_started.json"
        with marker.open("x", encoding="utf-8") as handle:
            json.dump({"started_at": datetime.now(timezone.utc).isoformat(), "episodes": REAL_EPISODES}, handle)
            handle.write("\n")
        runner = EpisodeRunner(
            LunchBenchmarkScenario(), provider, output_dir=OUTPUT,
            decision_policy_name="real_provider", model_name=config.model,
        )
        episodes = []
        for number in range(1, REAL_EPISODES + 1):
            result = await runner.run_episode(number)
            if not validate_trajectory(result):
                raise AssertionError("trajectory validation failed")
            episodes.append(result)
            print(f"EPISODE {number}", flush=True)
            print("SUCCESS" if result.success else result.termination_reason.value, flush=True)
            print(f"decisions={result.decision_count}", flush=True)
            print(f"trajectory={trajectory_signature(result)}", flush=True)

        metrics = MetricsAggregator().aggregate(episodes)
        if metrics.episodes_total != REAL_EPISODES or metrics.total_provider_requests > 15:
            raise AssertionError("real pilot request budget exceeded")
        if metrics.max_context_chars >= 2000 or metrics.max_prompt_chars >= 3000:
            raise AssertionError("context or prompt exceeded hard budget")
        write_benchmark_report(
            OUTPUT, metrics, episodes, scenario_name="lunch",
            decision_client_type="OpenAICompatibleDecisionClient", model_name=config.model,
        )
        print("BENCHMARK SUMMARY", flush=True)
        print(f"episodes_total={metrics.episodes_total}", flush=True)
        print(f"completion_rate={metrics.completion_rate:.3f}", flush=True)
        print(f"avg_decisions={metrics.avg_decisions:.3f}", flush=True)
        print(f"rejection_rate={metrics.rejection_rate:.3f}", flush=True)
        print(f"invalid_output_count={metrics.invalid_output_count}", flush=True)
        print(f"provider_error_count={metrics.provider_error_count}", flush=True)
        print(f"avg_context_chars={metrics.avg_context_chars:.1f}", flush=True)
        print(f"avg_prompt_chars={metrics.avg_prompt_chars:.1f}", flush=True)
        print(f"avg_input_tokens={metrics.avg_input_tokens_per_decision:.1f}", flush=True)
        print(f"avg_output_tokens={metrics.avg_output_tokens_per_decision:.1f}", flush=True)
        print(f"avg_reasoning_tokens={metrics.avg_reasoning_tokens_per_decision:.1f}", flush=True)
        print(f"avg_latency_seconds={metrics.avg_latency_per_decision:.3f}", flush=True)
        print(f"trajectory_counts={json.dumps(metrics.trajectory_counts, separators=(',', ':'))}", flush=True)
        print(f"provider_requests={metrics.total_provider_requests}", flush=True)
        env_calls = sum(stat.call_count for stat in router.get_token_usages().values())
        print(f"environment_llm_calls={env_calls}", flush=True)
        print("rule_llm_calls=0", flush=True)
        print("reducer_llm_calls=0", flush=True)
        print("evaluation_llm_judge_calls=0", flush=True)
        if env_calls:
            raise AssertionError("environment made an LLM call")
    finally:
        if society is not None:
            await asyncio.wait_for(society.close(), timeout=45)
        await provider.aclose()


if __name__ == "__main__":
    asyncio.run(main())
