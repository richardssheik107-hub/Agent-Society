"""Passive recorder ordering, JSONL, and prompt defaults."""

from dataclasses import replace
import json

import pytest

from social_sim.evaluation.models import TerminationReason
from social_sim.evaluation.recorder import TrajectoryRecorder
from test_trajectory_models import _step


def test_recorder_writes_one_structured_step_and_episode(tmp_path) -> None:
    recorder = TrajectoryRecorder("lunch-000001", output_dir=tmp_path)
    step = replace(_step(), prompt="system plus user prompt")
    recorder.append_step(step)
    result = recorder.finish_episode(
        success=True,
        termination_reason=TerminationReason.GOAL_REACHED,
        final_state=step.state_after,
        scenario_name="lunch",
        decision_policy_name="scripted",
    )
    path = recorder.write_episode(result)
    episode = json.loads(path.read_text(encoding="utf-8"))
    lines = (tmp_path / "trajectories.jsonl").read_text(encoding="utf-8").splitlines()
    assert path.name == "episode_000001.json"
    assert episode["schema_version"] == "0.1"
    assert episode["decision_count"] == 1
    assert episode["accepted_actions"] == 1
    assert episode["events"][0]["event_type"] == "MOVED"
    assert episode["steps"][0]["state_before"]["people"]["1"]["location"] == "home"
    assert episode["steps"][0]["state_after"]["people"]["1"]["location"] == "restaurant"
    assert len(lines) == 1
    assert json.loads(lines[0])["step_index"] == 1
    assert "prompt" not in episode["steps"][0]
    assert "prompt" not in json.loads(lines[0])
    with pytest.raises(RuntimeError, match="already been written"):
        recorder.write_episode()


def test_recorder_rejects_duplicate_or_out_of_order_steps(tmp_path) -> None:
    recorder = TrajectoryRecorder("lunch-000001", output_dir=tmp_path)
    with pytest.raises(ValueError, match="continuous"):
        recorder.append_step(replace(_step(), step_index=2))
    recorder.append_step(_step())
    with pytest.raises(ValueError, match="continuous"):
        recorder.append_step(_step())
    with pytest.raises(ValueError, match="episode_id"):
        recorder.append_step(replace(_step(), episode_id="lunch-000002", step_index=2))


def test_record_prompt_requires_explicit_opt_in(tmp_path) -> None:
    recorder = TrajectoryRecorder("lunch-000001", output_dir=tmp_path, record_prompt=True)
    step = replace(_step(), prompt="system plus user prompt")
    recorder.append_step(step)
    result = recorder.finish_episode(
        success=True,
        termination_reason=TerminationReason.GOAL_REACHED,
        final_state=step.state_after,
    )
    assert result.steps[0].to_dict()["prompt"] == "system plus user prompt"


def test_recorder_does_not_replace_existing_episode_file(tmp_path) -> None:
    first = TrajectoryRecorder("lunch-000001", output_dir=tmp_path)
    first.append_step(_step())
    first.finish_episode(success=True, termination_reason=TerminationReason.GOAL_REACHED,
                         final_state=_step().state_after)
    first.write_episode()
    second = TrajectoryRecorder("lunch-000001", output_dir=tmp_path)
    second.append_step(_step())
    second.finish_episode(success=True, termination_reason=TerminationReason.GOAL_REACHED,
                          final_state=_step().state_after)
    with pytest.raises(FileExistsError):
        second.write_episode()
    assert len((tmp_path / "trajectories.jsonl").read_text(encoding="utf-8").splitlines()) == 1


def test_nonadjacent_rejection_repeat_is_recorded(tmp_path) -> None:
    recorder = TrajectoryRecorder("lunch-000001", output_dir=tmp_path)
    baseline = _step()
    home = baseline.state_before
    for index, action, reason in (
        (1, "BUY", "NOT_AT_SELLER"),
        (2, "EAT", "ITEM_NOT_OWNED"),
        (3, "BUY", "NOT_AT_SELLER"),
    ):
        recorder.append_step(replace(
            baseline,
            step_index=index,
            state_before=home,
            state_after=home,
            proposal={"action": action, "target": "meal"},
            intent={"actor_id": 1, "action": action, "target": "meal", "params": {"quantity": 1}},
            rule_allowed=False,
            rule_reason_code=reason,
            effects=(),
            event={
                "event_id": f"event-{index}", "event_type": "ACTION_REJECTED",
                "actor_id": 1, "action": action, "target": "meal", "success": False,
                "reason_code": reason,
            },
        ))
    result = recorder.finish_episode(
        success=False,
        termination_reason=TerminationReason.MAX_DECISIONS,
        final_state=home,
        scenario_variant="S1_LAST_REJECTION",
        model_start_state=home,
    )
    assert result.same_rejected_action_repeat_count == 1
