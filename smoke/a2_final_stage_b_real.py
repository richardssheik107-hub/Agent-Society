"""One-time selected 90-minute continuity validation after the 80-row panel."""

from __future__ import annotations

import asyncio
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone

from dotenv import load_dotenv

from a2_final_stage_a_real import OUTPUT_ROOT, ROOT, START_MARKER, audit_secrets, protected_hashes

load_dotenv(ROOT / "third_party/AgentSociety/.env")

from social_sim.a2_final.corpus import split_worker_diaries  # noqa: E402
from social_sim.a2_final.micro import (  # noqa: E402
    SCENARIOS, micro_arms, micro_episode_row, micro_schedule, summarize_micro,
)
from social_sim.behavior_prior.index import BehaviorPriorIndex  # noqa: E402
from social_sim.daily.persona import NeutralPersona  # noqa: E402
from social_sim.daily.profiles import load_experiment_profiles  # noqa: E402
from social_sim.daily.runner import DailyEpisodeRunner  # noqa: E402
from social_sim.daily.validation import validate_daily_trajectory  # noqa: E402
from social_sim.decision import OpenAICompatibleDecisionClient  # noqa: E402
from social_sim.decision.config import CODING_PLAN, DecisionProviderConfig  # noqa: E402
from social_sim.evaluation.models import world_snapshot  # noqa: E402


DAILY_TRAJECTORY_SCENARIO_NAME = "neutral_day"


def write_json(path, value) -> None:
    with path.open("x", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=False, indent=2, allow_nan=False)
        file.write("\n")


async def main() -> None:
    resume_after_first_harness_failure = sys.argv[1:] == ["--continue-after-episode-1"]
    if sys.argv[1:] and not resume_after_first_harness_failure:
        raise ValueError("UNKNOWN_STAGE_B_ARGUMENT")
    marker = json.loads(START_MARKER.read_text(encoding="utf-8"))
    output = OUTPUT_ROOT / marker["experiment_id"]
    stage_a = output / "stage_a"
    selection = json.loads((stage_a / "engineering_selection.json").read_text(encoding="utf-8"))
    panel_rows = [json.loads(line) for line in (stage_a / "decision_rows.jsonl").read_text(encoding="utf-8").splitlines()]
    if len(panel_rows) != 80 or selection["panel_requests"] != 80:
        raise RuntimeError("STAGE_A_INCOMPLETE")
    already_started = (output / "stage_b_started.json").exists() or (output / "stage_b").exists()
    if already_started and not resume_after_first_harness_failure:
        raise RuntimeError("STAGE_B_ALREADY_STARTED_DO_NOT_RERUN")
    if resume_after_first_harness_failure and not already_started:
        raise RuntimeError("STAGE_B_NOT_STARTED")
    provider_config = DecisionProviderConfig.from_env()
    if provider_config.model != "ark-code-latest" or provider_config.base_url_category != CODING_PLAN:
        raise RuntimeError("A2_FINAL_PROVIDER_CONFIG_MISMATCH")
    before = protected_hashes()
    if before != json.loads((stage_a / "experiment_config.json").read_text(encoding="utf-8"))["production_protected_before"]:
        raise RuntimeError("PROTECTED_CONFIG_MODIFIED")
    corpora, _, split = split_worker_diaries()
    if split["split_hash"] != json.loads((stage_a / "train_eval_split.json").read_text(encoding="utf-8"))["split_hash"]:
        raise RuntimeError("STAGE_B_SPLIT_CHANGED")
    indices = {name: BehaviorPriorIndex.build(days) for name, days in corpora.items()}
    arms = micro_arms(selection["selected_corpus"], selection["selected_prior"])
    schedule = micro_schedule(arms)
    profile = load_experiment_profiles()[2]
    stage = output / "stage_b"
    experiment_config = {
        "stage_a_config_hash": marker["config_hash"], "split_hash": split["split_hash"],
        "profile": profile.name, "profile_hash": profile.profile_hash,
        "arms": {name: {"corpus": corpus or "B0", "prior_k": limit} for name, (corpus, limit) in arms.items()},
        "scenarios": [{"name": scenario.name, "initial_world": world_snapshot(scenario.world())}
                      for scenario in SCENARIOS],
        "window_minutes": 90, "tick_minutes": 15, "max_decisions": 4,
        "provider_alias": provider_config.model, "request_fields": ["model", "messages"],
        "request_timeout_seconds": 60, "transport_retries": 0,
        "selection_basis": selection["selection_basis"],
        "production_protected_before": before,
    }
    if resume_after_first_harness_failure:
        starts = [json.loads(line) for line in (stage / "episode_starts.jsonl").read_text(
            encoding="utf-8").splitlines()]
        if len(starts) != 1 or starts[0].get("episode") != 1 or not starts[0].get("started_at"):
            raise RuntimeError("STAGE_B_RESUME_STARTS_MISMATCH")
        if (json.loads((stage / "schedule.json").read_text(encoding="utf-8")) != schedule
                or json.loads((stage / "experiment_config.json").read_text(encoding="utf-8")) != experiment_config
                or (stage / "episode_rows.jsonl").stat().st_size
                or (stage / "trajectories.jsonl").stat().st_size
                or any((stage / "episodes").iterdir())
                or (stage / "episode_001_failure.json").exists()):
            raise RuntimeError("STAGE_B_RESUME_ARTIFACTS_NOT_PRISTINE")
        first = schedule[0]
        failure = {
            "episode": 1, "scenario": first["scenario"], "arm": first["arm"],
            "started_at": starts[0]["started_at"], "termination_reason": "ARCHITECTURE_ERROR",
            "error": "ValueError: episode final state does not match last step",
            "cause": "Harness used a non-neutral_day scenario_name, making the generic recorder validate daily tick drift as an immediate step transition.",
            "provider_request_count": None, "observed_minutes": None,
            "action_audit_available": False, "rerun": False,
        }
        write_json(stage / "episode_001_failure.json", failure)
        first_row = {
            "episode_number": 1, "scenario": first["scenario"], "repetition": first["repetition"],
            "condition": first["arm"], "corpus": first["corpus"], "prior_k": first["prior_k"],
            "segment_completion": False, "termination_reason": "ARCHITECTURE_ERROR",
            "personal_care_proposals": None, "personal_care_accepted": None,
            "chores_proposals": None, "chores_accepted": None,
            "provider_request_count": None, "decision_count": None,
            "observed_minutes": None, "partial_observed_minutes": None,
        }
        with (stage / "episode_rows.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps(first_row, ensure_ascii=False, allow_nan=False) + "\n")
        rows = [first_row]
        pending = schedule[1:]
    else:
        stage.mkdir()
        (stage / "episodes").mkdir()
        (stage / "episode_rows.jsonl").open("x", encoding="utf-8").close()
        (stage / "trajectories.jsonl").open("x", encoding="utf-8").close()
        (stage / "episode_starts.jsonl").open("x", encoding="utf-8").close()
        write_json(stage / "schedule.json", schedule)
        write_json(stage / "experiment_config.json", experiment_config)
        write_json(output / "stage_b_started.json", {"started_at": datetime.now(timezone.utc).isoformat(),
                                                      "episodes_budget": len(schedule)})
        rows = []
        pending = schedule
    provider = OpenAICompatibleDecisionClient(
        base_url=provider_config.api_base, api_key=provider_config.api_key,
        model=provider_config.model, timeout_seconds=60, minimal_request=True,
    )
    try:
        for item in pending:
            scenario = next(scenario for scenario in SCENARIOS if scenario.name == item["scenario"])
            prior_index = indices.get(arms[item["arm"]][0])
            with (stage / "episode_starts.jsonl").open("a", encoding="utf-8") as file:
                file.write(json.dumps({"episode": item["episode"], "started_at":
                                       datetime.now(timezone.utc).isoformat()}) + "\n")
            print(f"START STAGE_B={item['episode']}/{len(schedule)} {item['scenario']} {item['arm']}", flush=True)
            result = await DailyEpisodeRunner(
                provider, output_dir=stage / "episodes", model_name=provider_config.model,
                persona=NeutralPersona(goal="live through this period while handling your basic needs and obligations"),
                behavior_profile=profile, initial_world=scenario.world(), window_minutes=90,
                max_decisions_per_day=4, scenario_name=DAILY_TRAJECTORY_SCENARIO_NAME,
                allow_deterministic_output_recovery=True,
                prior_index=prior_index, prior_limit=item["prior_k"],
            ).run_episode(item["episode"])
            validate_daily_trajectory(result)
            if result.decision_count > 4 or result.provider_request_count > result.decision_count:
                raise RuntimeError("MICRO_DECISION_OR_REQUEST_CAP")
            if any(step.provider_request_count != 1 or step.prompt is not None for step in result.trajectory.steps):
                raise RuntimeError("MICRO_REQUEST_OR_PROMPT_INVARIANT")
            row = micro_episode_row(result, item)
            rows.append(row)
            with (stage / "episode_rows.jsonl").open("a", encoding="utf-8") as file:
                file.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
            with (stage / "trajectories.jsonl").open("a", encoding="utf-8") as file:
                file.write(json.dumps({"episode": item["episode"], "arm": item["arm"],
                                       "scenario": item["scenario"], "repetition": item["repetition"],
                                       "trajectory": result.trajectory.to_dict()},
                                      ensure_ascii=False, allow_nan=False) + "\n")
            audit_secrets(output, provider_config.api_key)
            if protected_hashes() != before:
                raise RuntimeError("PROTECTED_CONFIG_MODIFIED")
            print(f"DONE STAGE_B={item['episode']}/{len(schedule)} {result.termination_reason.value} "
                  f"requests={result.provider_request_count}", flush=True)
            if result.termination_reason.value == "ARCHITECTURE_ERROR":
                raise RuntimeError("MICRO_ARCHITECTURE_FAILURE")
        metrics = summarize_micro(rows, arms)
        write_json(stage / "condition_metrics.json", metrics["by_arm"])
        write_json(stage / "matched_comparisons.json", {
            "candidate_vs_control": metrics["candidate_vs_control"],
            "candidate_vs_full": metrics["candidate_vs_full"],
            "minimum_validation": metrics["minimum_validation"],
        })
        with (stage / "summary.csv").open("x", encoding="utf-8", newline="") as file:
            fields = ("episode_id", "episode_number", "scenario", "repetition", "condition", "corpus", "prior_k",
                      "segment_completion", "termination_reason", "observed_minutes", "partial_observed_minutes",
                      "decision_count", "provider_request_count", "decision_burst_count", "same_state_decision_count",
                      "idle_minutes", "idle_ratio", "partial_idle_minutes", "repeated_invalid_count",
                      "rejected_actions", "rejection_rate", "unique_activity_types", "active_minutes",
                      "unresolved_need_minutes", "obligation_neglect_minutes", "personal_care_proposals",
                      "personal_care_accepted", "personal_care_minutes", "chores_proposals", "chores_accepted",
                      "chores_minutes", "avg_context_chars", "input_tokens", "output_tokens",
                      "reasoning_tokens", "latency_seconds")
            writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        counts = Counter(row["termination_reason"] for row in rows)
        with (stage / "summary.md").open("x", encoding="utf-8") as file:
            file.write("# A2-Final 90-minute micro-rollout\n\n"
                       f"Episodes: {len(rows)}; complete={metrics['complete']}; "
                       f"timeout={counts['TIMEOUT']}; max_decisions={counts['MAX_DECISIONS']}; "
                       f"invalid_model_output={counts['INVALID_MODEL_OUTPUT']}; "
                       f"architecture_error={counts['ARCHITECTURE_ERROR']}.\n\n"
                       f"Candidate: {selection['selected_corpus']} + {selection['selected_prior']} "
                       f"({selection['selection_basis']}).\n"
                       f"Minimum validation: {metrics['minimum_validation']}.\n\n"
                       "Only matched complete episodes support full-window behavioral comparisons. "
                       "Truncated episodes retain provider and partial-window audits.\n")
        audit_secrets(output, provider_config.api_key)
        print(f"STAGE_B_COMPLETE episodes={len(rows)} complete={metrics['complete']} "
              f"validation={metrics['minimum_validation']}", flush=True)
    finally:
        await provider.aclose()


if __name__ == "__main__":
    asyncio.run(main())
