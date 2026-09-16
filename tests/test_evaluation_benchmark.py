"""End-to-end offline benchmark acceptance without provider requests."""

import asyncio
import json

from social_sim.decision import ActionType
from social_sim.evaluation.metrics import MetricsAggregator
from social_sim.evaluation.report import write_benchmark_report
from social_sim.evaluation.runner import EpisodeRunner, LunchBenchmarkScenario, ScriptedDecisionClient
from social_sim.evaluation.validation import validate_trajectory


def test_twenty_scripted_lunch_episodes_and_dataset(tmp_path) -> None:
    script = (
        (ActionType.MOVE, "restaurant"),
        (ActionType.BUY, "meal"),
        (ActionType.EAT, "meal"),
    )
    episodes = asyncio.run(EpisodeRunner(
        LunchBenchmarkScenario(), ScriptedDecisionClient(script),
        output_dir=tmp_path, decision_policy_name="scripted", model_name="scripted",
    ).run_benchmark(20))
    assert all(validate_trajectory(episode) for episode in episodes)
    metrics = MetricsAggregator().aggregate(episodes)
    assert metrics.episodes_total == metrics.episodes_success == 20
    assert metrics.completion_rate == 1.0
    assert metrics.avg_decisions == 3.0
    assert metrics.rejection_rate == 0.0
    assert metrics.trajectory_counts == {"MOVE>BUY>EAT": 20}
    assert metrics.action_counts == {"MOVE": 20, "BUY": 20, "EAT": 20}
    assert metrics.total_provider_requests == 0
    write_benchmark_report(
        tmp_path, metrics, episodes, scenario_name="lunch",
        decision_client_type="ScriptedDecisionClient", model_name="scripted",
    )
    manifest = json.loads((tmp_path / "dataset_manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "0.1"
    assert manifest["episode_count"] == 20
    assert manifest["step_count"] == 60
    assert manifest["contains_raw_prompt"] is False
    assert manifest["contains_hidden_reasoning"] is False
    assert len((tmp_path / "trajectories.jsonl").read_text(encoding="utf-8").splitlines()) == 60
    assert len(list((tmp_path / "episodes").glob("episode_*.json"))) == 20


def test_three_rejection_episodes_have_one_reason_each(tmp_path) -> None:
    script = (
        (ActionType.BUY, "meal"),
        (ActionType.MOVE, "restaurant"),
        (ActionType.BUY, "meal"),
        (ActionType.EAT, "meal"),
    )
    episodes = asyncio.run(EpisodeRunner(
        LunchBenchmarkScenario(), ScriptedDecisionClient(script),
        output_dir=tmp_path, decision_policy_name="scripted_rejection",
    ).run_benchmark(3))
    metrics = MetricsAggregator().aggregate(episodes)
    assert all(validate_trajectory(episode) and episode.success for episode in episodes)
    assert metrics.episodes_total == metrics.episodes_success == 3
    assert metrics.avg_decisions == 4.0
    assert metrics.rejected_actions_total == 3
    assert metrics.rejection_rate == 3 / 12
    assert metrics.rejection_reason_counts == {"NOT_AT_SELLER": 3}
    assert metrics.trajectory_counts == {"BUY!NOT_AT_SELLER>MOVE>BUY>EAT": 3}
