"""Twenty fresh scripted lunch episodes; no network or LLM requests."""

from __future__ import annotations

import asyncio
from pathlib import Path

from social_sim.decision import ActionType
from social_sim.evaluation.metrics import MetricsAggregator
from social_sim.evaluation.report import write_benchmark_report
from social_sim.evaluation.runner import EpisodeRunner, LunchBenchmarkScenario, ScriptedDecisionClient
from social_sim.evaluation.validation import validate_trajectory


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "run" / "evaluation" / "offline"


async def main() -> None:
    client = ScriptedDecisionClient((
        (ActionType.MOVE, "restaurant"),
        (ActionType.BUY, "meal"),
        (ActionType.EAT, "meal"),
    ))
    episodes = await EpisodeRunner(
        LunchBenchmarkScenario(), client, output_dir=OUTPUT,
        decision_policy_name="scripted", model_name="scripted",
    ).run_benchmark(20)
    if not all(validate_trajectory(episode) for episode in episodes):
        raise AssertionError("trajectory validation failed")
    metrics = MetricsAggregator().aggregate(episodes)
    if not (
        metrics.episodes_total == 20
        and metrics.episodes_success == 20
        and metrics.completion_rate == 1.0
        and metrics.avg_decisions == 3.0
        and metrics.rejection_rate == 0.0
        and metrics.trajectory_counts == {"MOVE>BUY>EAT": 20}
        and metrics.total_provider_requests == 0
    ):
        raise AssertionError("offline benchmark did not meet the frozen baseline")
    write_benchmark_report(
        OUTPUT, metrics, episodes, scenario_name="lunch",
        decision_client_type="ScriptedDecisionClient", model_name="scripted",
    )
    print("OFFLINE_BENCHMARK_OK")
    print("EPISODES=20")
    print("SUCCESS=20")
    print("COMPLETION_RATE=1.0")
    print("AVG_DECISIONS=3.0")
    print("TOP_TRAJECTORY=MOVE>BUY>EAT")
    print("TRAJECTORY_VALIDATION=PASS")


if __name__ == "__main__":
    asyncio.run(main())
