"""Network-free tests for fresh, sequential evaluation episodes."""

import asyncio
import json

import httpx

from social_sim.decision import ActionType, DecisionClientError
from social_sim.decision.client import DecisionReply
from social_sim.evaluation.models import TerminationReason
from social_sim.evaluation.runner import (
    EpisodeRunner,
    LunchBenchmarkScenario,
    ScriptedDecisionClient,
)


LUNCH_SCRIPT = (
    (ActionType.MOVE, "restaurant"),
    (ActionType.BUY, "meal"),
    (ActionType.EAT, "meal"),
)


def run(runner: EpisodeRunner, count: int):
    return asyncio.run(runner.run_benchmark(count))


def test_episode_runner_records_real_steps_and_resets_world(tmp_path) -> None:
    client = ScriptedDecisionClient(LUNCH_SCRIPT)
    results = run(
        EpisodeRunner(
            LunchBenchmarkScenario(), client, output_dir=tmp_path,
            decision_policy_name="scripted", model_name="scripted",
        ),
        2,
    )
    assert [result.episode_id for result in results] == ["lunch-000001", "lunch-000002"]
    assert all(result.success for result in results)
    assert all(result.termination_reason is TerminationReason.GOAL_REACHED for result in results)
    assert [result.decision_count for result in results] == [3, 3]
    assert client.call_count == 6
    assert results[0].final_state["venues"]["restaurant"]["meal"]["stock"] == 9
    assert results[1].steps[0].state_before["venues"]["restaurant"]["meal"]["stock"] == 10
    assert [step.step_index for step in results[0].steps] == [1, 2, 3]
    assert [step.proposal["action"] for step in results[0].steps] == ["MOVE", "BUY", "EAT"]
    assert [step.event["event_type"] for step in results[0].steps] == ["MOVED", "PURCHASED", "ATE"]
    assert results[0].steps[1].state_before == results[0].steps[0].state_after
    assert results[0].steps[2].state_before == results[0].steps[1].state_after
    assert results[0].steps[1].observation["location"] == "restaurant"
    assert results[0].steps[2].observation["inventory"]["meal"] == 1
    assert all(step.context_chars == len(step.context) for result in results for step in result.steps)
    assert all(step.context_chars < 2000 and step.prompt_chars < 3000 for result in results for step in result.steps)
    assert all(step.provider_request_count == 0 for result in results for step in result.steps)
    assert all(step.prompt is None for result in results for step in result.steps)
    assert (tmp_path / "episodes" / "episode_000001.json").exists()
    assert (tmp_path / "episodes" / "episode_000002.json").exists()
    assert len((tmp_path / "trajectories.jsonl").read_text(encoding="utf-8").splitlines()) == 6


def test_rejected_buy_is_recorded_without_world_mutation(tmp_path) -> None:
    client = ScriptedDecisionClient(((ActionType.BUY, "meal"),) + LUNCH_SCRIPT)
    result = run(EpisodeRunner(LunchBenchmarkScenario(), client, output_dir=tmp_path), 1)[0]
    assert result.success
    assert result.decision_count == 4
    assert result.rejected_actions == 1
    rejected = result.steps[0]
    assert rejected.rule_reason_code == "NOT_AT_SELLER"
    assert rejected.event["event_type"] == "ACTION_REJECTED"
    assert rejected.effects == ()
    assert rejected.state_before == rejected.state_after
    assert "ACTION_REJECTED:NOT_AT_SELLER" in result.steps[1].context


def test_invalid_output_ends_episode_without_retry_or_rule_event(tmp_path) -> None:
    class InvalidClient:
        call_count = 0

        async def complete(self, system_prompt, user_prompt):
            self.call_count += 1
            return DecisionReply("not JSON")

    client = InvalidClient()
    result = run(EpisodeRunner(LunchBenchmarkScenario(), client, output_dir=tmp_path), 1)[0]
    assert result.termination_reason is TerminationReason.INVALID_MODEL_OUTPUT
    assert result.invalid_outputs == 1
    assert result.decision_count == client.call_count == 1
    assert result.steps == result.events == ()
    assert result.final_state["people"]["1"]["location"] == "home"


def test_provider_error_isolated_and_third_episode_continues(tmp_path) -> None:
    class FlakyClient:
        def __init__(self):
            self.episode = 0
            self.index = 0
            self.call_count = 0
            self.provider_request_count = 0

        def start_episode(self):
            self.episode += 1
            self.index = 0

        async def complete(self, system_prompt, user_prompt):
            self.call_count += 1
            self.provider_request_count += 1
            if self.episode == 2:
                raise DecisionClientError("simulated HTTP failure")
            action, target = LUNCH_SCRIPT[self.index]
            self.index += 1
            return DecisionReply(
                json.dumps({"action": action.value, "target": target}),
                provider_request_count=1,
            )

    client = FlakyClient()
    results = run(EpisodeRunner(LunchBenchmarkScenario(), client, output_dir=tmp_path), 3)
    assert [result.success for result in results] == [True, False, True]
    assert results[1].termination_reason is TerminationReason.PROVIDER_ERROR
    assert results[1].provider_errors == 1
    assert results[1].decision_count == results[1].total_provider_requests == 1
    assert results[1].steps == ()
    assert results[2].steps[0].state_before["venues"]["restaurant"]["meal"]["stock"] == 10
    assert client.call_count == client.provider_request_count == 7


def test_record_prompt_is_explicit_opt_in(tmp_path) -> None:
    result = run(
        EpisodeRunner(
            LunchBenchmarkScenario(), ScriptedDecisionClient(LUNCH_SCRIPT),
            output_dir=tmp_path, record_prompt=True,
        ),
        1,
    )[0]
    assert all(step.prompt is not None and "Context:" in step.prompt for step in result.steps)
    assert "prompt" in result.steps[0].to_dict()


def test_timeout_is_terminal_for_one_episode_but_not_the_benchmark(tmp_path) -> None:
    class TimeoutOnceClient:
        def __init__(self):
            self.episode = 0
            self.index = 0
            self.provider_request_count = 0

        def start_episode(self):
            self.episode += 1
            self.index = 0

        async def complete(self, system_prompt, user_prompt):
            self.provider_request_count += 1
            if self.episode == 1:
                raise httpx.ReadTimeout("simulated timeout")
            action, target = LUNCH_SCRIPT[self.index]
            self.index += 1
            return DecisionReply(
                json.dumps({"action": action.value, "target": target}),
                provider_request_count=1,
            )

    results = run(EpisodeRunner(
        LunchBenchmarkScenario(), TimeoutOnceClient(), output_dir=tmp_path,
    ), 2)
    assert results[0].termination_reason is TerminationReason.TIMEOUT
    assert results[0].decision_count == results[0].total_provider_requests == 1
    assert results[0].steps == ()
    assert results[1].success and results[1].decision_count == 3


def test_max_decisions_has_five_rejected_steps(tmp_path) -> None:
    client = ScriptedDecisionClient(((ActionType.BUY, "meal"),) * 5)
    result = run(EpisodeRunner(LunchBenchmarkScenario(), client, output_dir=tmp_path), 1)[0]
    assert result.termination_reason is TerminationReason.MAX_DECISIONS
    assert result.decision_count == result.rejected_actions == 5
    assert result.accepted_actions == 0
    assert all(step.state_before == step.state_after for step in result.steps)
