"""Passive trajectory capture and JSON/JSONL persistence."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path

from .models import EpisodeResult, StepTrajectory, TerminationReason
from .validation import validate_trajectory


class TrajectoryRecorder:
    """Collect one episode without touching decisions, rules, or world state."""

    def __init__(
        self,
        episode_id: str,
        output_dir: str | Path = "run/evaluation",
        *,
        record_prompt: bool = False,
    ) -> None:
        if not isinstance(episode_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", episode_id):
            raise ValueError("episode_id must use letters, digits, underscore, or hyphen")
        if not isinstance(record_prompt, bool):
            raise TypeError("record_prompt must be a bool")
        self.episode_id = episode_id
        self.output_dir = Path(output_dir)
        self.record_prompt = record_prompt
        self._steps: list[StepTrajectory] = []
        self._result: EpisodeResult | None = None
        self._written = False

    @property
    def steps(self) -> tuple[StepTrajectory, ...]:
        return tuple(self._steps)

    @property
    def result(self) -> EpisodeResult | None:
        return self._result

    def append_step(self, step: StepTrajectory) -> None:
        if self._result is not None:
            raise RuntimeError("episode is already finished")
        if not isinstance(step, StepTrajectory):
            raise TypeError("step must be a StepTrajectory")
        if step.episode_id != self.episode_id:
            raise ValueError("step episode_id does not match recorder")
        if step.step_index != len(self._steps) + 1:
            raise ValueError("step_index must be continuous and start at 1")
        # Prompt retention is an explicit opt-in; never serialize it by accident.
        if not self.record_prompt and step.prompt is not None:
            step = replace(step, prompt=None)
        self._steps.append(step)

    def finish_episode(
        self,
        *,
        success: bool,
        termination_reason: TerminationReason,
        final_state: dict[str, object],
        decision_count: int | None = None,
        invalid_outputs: int = 0,
        provider_errors: int = 0,
        total_provider_requests: int | None = None,
        scenario_name: str = "lunch",
        context_policy_name: str = "baseline_compact",
        decision_policy_name: str = "unknown",
        model_name: str | None = None,
        seed: int | None = None,
    ) -> EpisodeResult:
        if self._result is not None:
            raise RuntimeError("episode is already finished")
        steps = tuple(self._steps)
        observed_decisions = sum(step.decision_call_count for step in steps)
        observed_requests = sum(step.provider_request_count for step in steps)
        if decision_count is None:
            decision_count = observed_decisions
        if total_provider_requests is None:
            total_provider_requests = observed_requests
        if decision_count < observed_decisions:
            raise ValueError("decision_count cannot be less than recorded decisions")
        if total_provider_requests < observed_requests:
            raise ValueError("total_provider_requests cannot be less than recorded requests")
        if success != (termination_reason == TerminationReason.GOAL_REACHED):
            raise ValueError("success and termination_reason disagree")
        result = EpisodeResult(
            episode_id=self.episode_id,
            success=success,
            termination_reason=termination_reason,
            decision_count=decision_count,
            accepted_actions=sum(step.rule_allowed for step in steps),
            rejected_actions=sum(not step.rule_allowed for step in steps),
            invalid_outputs=invalid_outputs,
            provider_errors=provider_errors,
            total_provider_requests=total_provider_requests,
            final_state=final_state,
            events=tuple(step.event for step in steps),
            steps=steps,
            total_input_tokens=sum(step.input_tokens or 0 for step in steps),
            total_output_tokens=sum(step.output_tokens or 0 for step in steps),
            total_reasoning_tokens=sum(step.reasoning_tokens or 0 for step in steps),
            total_latency_seconds=sum(step.decision_latency_seconds for step in steps),
            max_context_chars=max((step.context_chars for step in steps), default=0),
            max_prompt_chars=max((step.prompt_chars for step in steps), default=0),
            scenario_name=scenario_name,
            context_policy_name=context_policy_name,
            decision_policy_name=decision_policy_name,
            model_name=model_name,
            seed=seed,
        )
        validate_trajectory(result)
        self._result = result
        return result

    def write_episode(self, result: EpisodeResult | None = None) -> Path:
        """Write one episode JSON and append its steps to trajectories.jsonl once."""
        if self._written:
            raise RuntimeError("episode has already been written")
        if self._result is None:
            raise RuntimeError("finish_episode must be called before write_episode")
        if result is not None and result is not self._result:
            raise ValueError("result must be this recorder's finished episode")
        result = self._result
        suffix = re.search(r"(\d{6})$", self.episode_id)
        filename = f"episode_{suffix.group(1) if suffix else self.episode_id}.json"
        episodes_dir = self.output_dir / "episodes"
        episodes_dir.mkdir(parents=True, exist_ok=True)
        episode_path = episodes_dir / filename
        episode_json = json.dumps(result.to_dict(), ensure_ascii=False, indent=2, allow_nan=False)
        step_lines = "".join(
            json.dumps(step.to_dict(), ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n"
            for step in result.steps
        )
        with episode_path.open("x", encoding="utf-8") as episode_file:
            episode_file.write(episode_json + "\n")
        if step_lines:
            with (self.output_dir / "trajectories.jsonl").open("a", encoding="utf-8") as jsonl_file:
                jsonl_file.write(step_lines)
        self._written = True
        return episode_path
