"""Run all 32 Phase 8A cells with a policy-independent scripted client."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from social_sim.decision import ActionType
from social_sim.evaluation.ablation_metrics import aggregate_ablation_metrics
from social_sim.evaluation.ablation_report import write_ablation_report
from social_sim.evaluation.ablation_runner import (
    MAX_REAL_EPISODES,
    POLICY_NAMES,
    REPETITIONS_PER_CELL,
    AblationExperimentRunner,
    build_experiment_config,
    build_interleaved_schedule,
)
from social_sim.evaluation.ablation_scenarios import SCENARIO_VARIANTS
from social_sim.evaluation.models import world_snapshot
from social_sim.evaluation.runner import ScriptedDecisionClient, lunch_initial_world
from social_sim.evaluation.validation import validate_trajectory


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    (ActionType.MOVE, "restaurant"),
    (ActionType.BUY, "meal"),
    (ActionType.EAT, "meal"),
)


async def main() -> None:
    schedule = build_interleaved_schedule()
    config = build_experiment_config(
        provider_alias="scripted", decision_client_type="ScriptedDecisionClient",
        schedule=schedule,
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = ROOT / "run" / "evaluation" / "context_ablation" / f"offline_{stamp}"
    output.mkdir(parents=True)
    with (output / "experiment_config.json").open("x", encoding="utf-8") as target:
        json.dump(config, target, ensure_ascii=False, indent=2)
        target.write("\n")
    client = ScriptedDecisionClient(SCRIPT)
    results = await AblationExperimentRunner(
        client, output_dir=output,
        experiment_config_hash=str(config["experiment_config_hash"]),
        decision_policy_name="scripted", model_name="scripted",
    ).run(schedule)
    if len(results) != MAX_REAL_EPISODES or not all(item.success for item in results):
        raise AssertionError("offline ablation did not complete 32/32 cells")
    if client.call_count != 96 or sum(item.total_provider_requests for item in results):
        raise AssertionError("offline ablation made an unexpected decision/request count")
    if not all(validate_trajectory(item) for item in results):
        raise AssertionError("trajectory validation failed")
    baseline = world_snapshot(lunch_initial_world())
    equal = all(
        item.model_start_state == baseline
        and item.steps[0].state_before == baseline for item in results
    )
    budgets = all(
        step.context_chars < 2000 and step.prompt_chars < 3000
        for item in results for step in item.steps
    )
    if not equal or not budgets:
        raise AssertionError("model-start state or context budget invariant failed")
    scenarios = tuple(item.value for item in SCENARIO_VARIANTS)
    summary = aggregate_ablation_metrics(results, policies=POLICY_NAMES, scenarios=scenarios)
    write_ablation_report(
        output, summary, results, policies=POLICY_NAMES, scenarios=scenarios,
        repetitions_per_cell=REPETITIONS_PER_CELL, provider_alias="scripted",
        experiment_config_hash=str(config["experiment_config_hash"]),
    )
    print("CONTEXT_ABLATION_OFFLINE_OK")
    print(f"POLICIES={len(POLICY_NAMES)}")
    print(f"SCENARIOS={len(scenarios)}")
    print(f"EPISODES={len(results)}")
    print(f"SUCCESS={sum(item.success for item in results)}")
    print("MODEL_START_STATE_EQUAL=YES")
    print("CONTEXT_BUDGET_PASS=YES")
    print(f"ARTIFACT_DIR={output}")


if __name__ == "__main__":
    asyncio.run(main())
