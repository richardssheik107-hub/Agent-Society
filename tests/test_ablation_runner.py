"""Offline schedule, fairness, and request-budget tests for Phase 8A."""

import asyncio
import json
from collections import Counter

import pytest

from social_sim.context import C0StatePolicy
from social_sim.decision import ActionType, DecisionClientError
from social_sim.evaluation.ablation_runner import (
    MAX_REAL_EPISODES,
    AblationExperimentRunner,
    ProviderInstabilityError,
    build_experiment_config,
    build_interleaved_schedule,
)
from social_sim.evaluation.ablation_scenarios import ScenarioVariant, prepare_ablation_scenario
from social_sim.evaluation.runner import EpisodeRunner, LunchBenchmarkScenario, ScriptedDecisionClient
from social_sim.evaluation.validation import validate_trajectory


SCRIPT = (
    (ActionType.MOVE, "restaurant"),
    (ActionType.BUY, "meal"),
    (ActionType.EAT, "meal"),
)


def test_schedule_is_fixed_interleaved_and_balanced() -> None:
    schedule = build_interleaved_schedule()
    assert schedule == build_interleaved_schedule()
    assert len(schedule) == MAX_REAL_EPISODES == 32
    assert [entry.episode_index for entry in schedule] == list(range(1, 33))
    assert Counter((entry.context_policy_name, entry.scenario_variant) for entry in schedule) == {
        cell: 2 for cell in {
            (entry.context_policy_name, entry.scenario_variant) for entry in schedule
        }
    }
    assert len({(entry.context_policy_name, entry.scenario_variant) for entry in schedule}) == 16
    assert [entry.context_policy_name for entry in schedule[:4]] == [
        "C0_state", "C1_last", "C3_recent3", "CR_relevant"
    ]
    assert [entry.context_policy_name for entry in schedule[4:8]] == [
        "C1_last", "C3_recent3", "CR_relevant", "C0_state"
    ]
    assert [entry.context_policy_name for entry in schedule[16:20]] == [
        "CR_relevant", "C3_recent3", "C1_last", "C0_state"
    ]


def test_config_hash_is_stable_and_covers_schedule_without_secret() -> None:
    first = build_experiment_config(
        provider_alias="scripted", decision_client_type="ScriptedDecisionClient"
    )
    second = build_experiment_config(
        provider_alias="scripted", decision_client_type="ScriptedDecisionClient"
    )
    assert first == second
    assert len(first["experiment_config_hash"]) == 64
    assert len(first["schedule"]) == 32
    assert first["request_contract"]["body_fields"] == ["model", "messages"]
    assert "api_key" not in json.dumps(first).lower()


def test_all_32_scripted_cells_share_world_and_complete(tmp_path) -> None:
    config = build_experiment_config(
        provider_alias="scripted", decision_client_type="ScriptedDecisionClient"
    )
    client = ScriptedDecisionClient(SCRIPT)
    results = asyncio.run(AblationExperimentRunner(
        client, output_dir=tmp_path,
        experiment_config_hash=config["experiment_config_hash"],
        decision_policy_name="scripted", model_name="scripted",
    ).run(build_interleaved_schedule()))
    assert len(results) == 32
    assert all(result.success and result.decision_count == 3 for result in results)
    assert all(validate_trajectory(result) for result in results)
    assert client.call_count == 96
    assert sum(result.total_provider_requests for result in results) == 0
    assert len({json.dumps(result.model_start_state, sort_keys=True) for result in results}) == 1
    assert all(result.steps[0].state_before == result.model_start_state for result in results)
    assert all(result.experiment_config_hash == config["experiment_config_hash"] for result in results)
    assert all(result.first_decision_action == "MOVE" for result in results)
    assert all(result.first_decision_target == "restaurant" for result in results)
    assert all(result.first_decision_repeats_prelude_rejection is False
               for result in results if result.prelude_rejection_present)
    assert all(result.recovery_after_rejection is True
               for result in results if result.prelude_rejection_present)
    assert all(result.steps[0].context_chars < 2000 and result.steps[0].prompt_chars < 3000
               for result in results)
    s2 = [result for result in results if result.scenario_variant == "S2_BURIED_REJECTION"]
    assert len(s2) == 8
    assert all(result.prelude_action_count == 5 and result.prelude_rejection_count == 1
               for result in s2)
    for result in s2:
        initial_context = result.steps[0].context
        if result.context_policy_name in ("C1_last", "C3_recent3"):
            assert "NOT_AT_SELLER" not in initial_context
        elif result.context_policy_name == "CR_relevant":
            assert "NOT_AT_SELLER" in initial_context
    assert len(list((tmp_path / "episodes").glob("episode_*.json"))) == 32
    assert len((tmp_path / "trajectories.jsonl").read_text(encoding="utf-8").splitlines()) == 96


def test_same_rejected_action_repeat_counts_only_model_steps(tmp_path) -> None:
    script = (
        (ActionType.BUY, "meal"),
        (ActionType.BUY, "meal"),
        (ActionType.MOVE, "restaurant"),
        (ActionType.BUY, "meal"),
        (ActionType.EAT, "meal"),
    )
    result = asyncio.run(EpisodeRunner(
        LunchBenchmarkScenario(), ScriptedDecisionClient(script), output_dir=tmp_path,
        context_policy=C0StatePolicy(), context_policy_name="C0_state",
    ).run_episode(
        1, setup=prepare_ablation_scenario(ScenarioVariant.S1_LAST_REJECTION),
        experiment_config_hash="0" * 64,
    ))
    assert result.success
    assert result.prelude_rejection_count == 1
    assert result.rejected_actions == 2
    assert result.same_rejected_action_repeat_count == 1
    assert result.first_decision_repeats_prelude_rejection is True
    assert result.recovery_after_rejection is False
    assert result.decision_count == 5


def test_three_consecutive_provider_failures_abort_after_three_requests(tmp_path) -> None:
    class BrokenClient:
        provider_request_count = 0

        async def complete(self, system_prompt, user_prompt):
            self.provider_request_count += 1
            raise DecisionClientError("simulated infrastructure failure")

    client = BrokenClient()
    runner = AblationExperimentRunner(
        client, output_dir=tmp_path, experiment_config_hash="0" * 64,
        decision_policy_name="broken", model_name="broken",
    )
    with pytest.raises(ProviderInstabilityError) as error:
        asyncio.run(runner.run(build_interleaved_schedule()))
    assert error.value.episodes_completed == 3
    assert client.provider_request_count == 3
