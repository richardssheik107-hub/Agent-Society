"""Offline-only A2-Closure evidence scoring and recording regression."""

from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from social_sim.a2_closure.audit import classify_max_decisions, decide_runtime_change, summarize_audit
from social_sim.a2_final.micro import SCENARIOS
from social_sim.daily.profiles import load_experiment_profiles
from social_sim.daily.runner import DailyEpisodeRunner
from social_sim.daily.validation import validate_daily_trajectory
from social_sim.decision import FakeDecisionClient
from a2_final_stage_b_real import DAILY_TRAJECTORY_SCENARIO_NAME


def _world(minute: int, *, location: str = "home") -> dict:
    time = datetime(2026, 1, 1, 18, 30, tzinfo=timezone.utc) + timedelta(minutes=minute)
    return {"time": time.isoformat(), "people": {"1": {"location": location, "activity": None,
            "money": 100.0, "inventory": {}, "hunger": 0.4, "energy": 0.5}}}


def _synthetic_immediate_cell() -> tuple[dict, dict, dict]:
    steps = []
    actions = (("MOVE", "restaurant", True), ("BUY", "meal", True),
               ("EAT", "meal", True), ("LEISURE", None, False))
    for index, (action, target, allowed) in enumerate(actions):
        state = _world(index * 15, location="restaurant" if index else "home")
        steps.append({"simulation_time": state["time"], "trigger_reason": "NO_ACTIVE_ACTIVITY",
                      "state_before": state, "state_after": deepcopy(state),
                      "proposal": {"action": action, "target": target},
                      "rule_allowed": allowed,
                      "rule_reason_code": "ACCEPTED" if allowed else "NOT_AT_ACTIVITY_LOCATION",
                      "context": json.dumps({"h": []}), "active_activity": None})
    ticks = [{"active_activity": None, "end_time": _world((index + 1) * 15)["time"]}
             for index in range(4)]
    row = {"episode_number": 7, "scenario": "M4_EVENING", "condition": "CANDIDATE",
           "termination_reason": "MAX_DECISIONS", "decision_count": 4, "observed_minutes": 60}
    return row, {"termination_reason": "MAX_DECISIONS", "steps": steps}, {"ticks": ticks}


def test_root_cause_scores_immediate_churn_and_prior_followed_rejection() -> None:
    row, trajectory, daily = _synthetic_immediate_cell()
    trajectory["steps"][0]["context"] = json.dumps(
        {"h": ["prior: common around now after unknown -> MOVE"]})
    trajectory["steps"][3]["context"] = json.dumps(
        {"h": ["prior: common around now after EAT -> LEISURE"]})
    cell = classify_max_decisions(row, trajectory, daily)
    assert cell["primary_root_cause"] == "B_IMMEDIATE_ACTION_CHURN"
    assert cell["immediate_followup_count"] == 3
    assert cell["prior_followed_and_rejected"] == 1
    assert cell["prior_related_invalid_share_of_decisions"] == 0.25
    assert len(cell["compact_trace"]) == 4
    assert "reasoning" not in json.dumps(cell).lower()


def test_global_dominance_and_prior_signal_are_deterministic() -> None:
    row, trajectory, daily = _synthetic_immediate_cell()
    cell = classify_max_decisions(row, trajectory, daily)
    cells = []
    for index in range(1, 8):
        item = deepcopy(cell)
        item["cell_id"] = index
        if index <= 3:
            item["prior_followed_and_rejected"] = 1
            item["prior_related_invalid_share_of_decisions"] = 0.25
        cells.append(item)
    summary, prior = summarize_audit(cells)
    assert summary["global_dominant_cause"] == "B_IMMEDIATE_ACTION_CHURN"
    assert prior["prior_loop_signal"] == "YES"
    assert prior["qualifying_cells"] == [1, 2, 3]
    decision = decide_runtime_change(summary, prior)
    assert decision["decision"] == "BEHAVIORAL_CAUSE_UNRESOLVED"
    assert decision["runtime_behavior_change"] == "NONE"
    assert decision["real_continuity_rerun"] == "NOT_NEEDED"
    assert decide_runtime_change(
        {"global_dominant_cause": "NONE", "same_tick_duplicate_count": 0},
        {"prior_loop_signal": "NO"},
    )["decision"] == "NO_RUNTIME_CHANGE_NEEDED"


def test_daily_recording_scenario_name_regression_without_provider() -> None:
    assert DAILY_TRAJECTORY_SCENARIO_NAME == "neutral_day"
    async def run(name: str):
        return await DailyEpisodeRunner(
            FakeDecisionClient('{"action":"LEISURE","target":null}'),
            write_artifacts=False, initial_world=SCENARIOS[0].world(),
            behavior_profile=load_experiment_profiles()[2], window_minutes=90,
            max_decisions_per_day=4, scenario_name=name,
            allow_deterministic_output_recovery=True,
        ).run_episode(1)

    with pytest.raises(ValueError, match="success and termination_reason disagree|final state does not match last step"):
        asyncio.run(run("a2_final_micro"))
    result = asyncio.run(run(DAILY_TRAJECTORY_SCENARIO_NAME))
    assert validate_daily_trajectory(result)
    assert result.trajectory.scenario_name == "neutral_day"
