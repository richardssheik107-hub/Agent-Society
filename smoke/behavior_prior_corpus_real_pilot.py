"""One-time 5×4 A2-Fast provider pilot; no cell replacement or model retrieval."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "third_party/AgentSociety/.env"
load_dotenv(ENV_FILE)

from social_sim.behavior_prior.benchmark import (  # noqa: E402
    CONDITIONS, aggregate_condition, condition_episode_metrics, matched_comparisons, schedule,
)
from social_sim.behavior_prior.index import BehaviorPriorIndex, load_nested_worker_corpora  # noqa: E402
from social_sim.behavior_prior.validation import query_coverage, sanity_table  # noqa: E402
from social_sim.daily.calibrated import CalibratedSegmentBenchmark, SEGMENTS, config_hash, segment_world  # noqa: E402
from social_sim.daily.profiles import SOURCE as CALIBRATION_PROFILE, load_experiment_profiles  # noqa: E402
from social_sim.daily.validation import validate_daily_trajectory  # noqa: E402
from social_sim.decision import OpenAICompatibleDecisionClient  # noqa: E402
from social_sim.decision.client import FakeDecisionClient  # noqa: E402
from social_sim.decision.config import CODING_PLAN, DecisionProviderConfig  # noqa: E402
from social_sim.evaluation.models import world_snapshot  # noqa: E402


OUTPUT_ROOT = ROOT / "run/evaluation/behavior_prior_corpus"
START_MARKER = OUTPUT_ROOT / "real_pilot_started.json"
TIMEOUT_SECONDS = 60
BASELINE = "9139744cc67d8d0279821ef9750990af5642dc87"
PROTECTED = (ROOT / "src/social_sim/daily/time.py", CALIBRATION_PROFILE)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=False, indent=2, allow_nan=False)
        file.write("\n")


def audit_secrets(directory: Path, key: str) -> None:
    credentials = [key] + [value for name, value in dotenv_values(ENV_FILE).items()
                           if value and len(value) >= 12 and any(
                               term in name.upper() for term in ("KEY", "SECRET", "TOKEN", "PASSWORD")
                           )]
    forbidden = re.compile(r"(?i)authorization|bearer\s|reasoning_content|<think|api[_-]?key")
    for file in directory.rglob("*"):
        if file.is_file():
            content = file.read_text(encoding="utf-8", errors="ignore")
            if forbidden.search(content) or any(secret in content for secret in credentials):
                raise RuntimeError("SECRET_LEAK_DETECTED")


def summarize(output: Path, rows: list[dict[str, object]], config: dict[str, object],
              corpus_info: dict[str, object], indices: dict[str, BehaviorPriorIndex],
              protected_before: dict[str, str], abort: str | None) -> None:
    by_condition = {c.name: aggregate_condition([row for row in rows if row["condition"] == c.name])
                    for c in CONDITIONS}
    by_cell = {f"{c.name}__{segment}": aggregate_condition([
        row for row in rows if row["condition"] == c.name and row["segment"] == segment
    ]) for c in CONDITIONS for segment in SEGMENTS}
    matched = matched_comparisons(rows)
    write_json(output / "condition_metrics.json", by_condition)
    write_json(output / "condition_segment_metrics.json", by_cell)
    write_json(output / "matched_comparisons.json", matched)
    fields = (
        "episode_id", "condition", "corpus", "prior_limit", "segment", "segment_completion",
        "termination_reason", "provider_failure", "decision_count", "provider_request_count",
        "decision_burst_count", "same_state_decision_count", "repeated_invalid_count",
        "idle_minutes", "idle_ratio", "unique_activity_types", "active_minutes", "rejection_rate",
        "personal_care_prior_mentions", "personal_care_proposals", "personal_care_accepted", "personal_care_minutes",
        "chores_prior_mentions", "chores_proposals", "chores_accepted", "chores_minutes",
        "prior_query_count", "prior_follow_rate", "prior_feasible_count", "avg_added_context_chars",
        "avg_context_chars", "avg_prompt_chars", "input_tokens", "output_tokens", "reasoning_tokens", "latency_seconds",
    )
    with (output / "summary.csv").open("x", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    models = Counter()
    for row in rows:
        models.update(row["provider_models"])
    completed = sum(row["segment_completion"] for row in rows)
    provider_timeouts = sum(row["termination_reason"] == "TIMEOUT" for row in rows)
    max_decisions = sum(row["termination_reason"] == "MAX_DECISIONS" for row in rows)
    invalid_outputs = sum(row["termination_reason"] == "INVALID_MODEL_OUTPUT" for row in rows)
    lines = [
        "# A2-Fast Behavior Prior + Corpus Size Pilot", "",
        f"Executed {len(rows)}/20 cells; complete={completed}, provider_timeout={provider_timeouts}, "
        f"max_decisions={max_decisions}, invalid_model_output={invalid_outputs}, abort={abort or 'none'}.",
        "Only matched complete same-segment cells support direct behavioral comparison. "
        "Unpaired overall means are descriptive and vulnerable to completion selection.", "",
        "| Condition | Corpus | Priors | Complete / 4 | Timeout | Decision cap | Avg idle ratio* | Avg decisions* |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for condition in CONDITIONS:
        metrics = by_condition[condition.name]
        idle = metrics["avg_idle_ratio"]
        decisions = metrics["avg_decision_count"]
        lines.append(f"| {condition.name} | {condition.corpus or 'B0'} | {condition.prior_limit} | "
                     f"{metrics['complete_segments']} | {metrics['provider_timeouts']} | "
                     f"{metrics['max_decisions_terminations']} | "
                     f"{'NA' if idle is None else f'{idle:.3f}'} | "
                     f"{'NA' if decisions is None else f'{decisions:.2f}'} |")
    lines += ["", "`*` Complete segments only. See condition_segment_metrics.json for each cell.", "",
              "## Matched complete comparisons", ""]
    for label, key in (("Prior C0 vs C3", "prior_effect_C0_C3"),
                       ("Corpus B100 vs B1000", "corpus_size_C1_C2"),
                       ("Corpus B1000 vs BALL", "corpus_size_C2_C3"),
                       ("Retrieval R1 vs R3", "retrieval_size_C3_C4")):
        comparison = matched[key]
        lines.append(f"- {label}: segments={','.join(comparison['matched_complete_segments']) or 'none'}; "
                     f"mean paired idle-ratio Δ={comparison['deltas_right_minus_left']['idle_ratio']}; "
                     f"mean paired decision Δ={comparison['deltas_right_minus_left']['decision_count']}.")
    lines += ["", f"Actual backend models (successful steps): {json.dumps(dict(models), sort_keys=True)}.",
              "A prior mention or model follow is descriptive, not proof of correctness.",
              "No significance or human-likeness claim is made from one repetition per cell.", ""]
    with (output / "summary.md").open("x", encoding="utf-8") as file:
        file.write("\n".join(lines))
    write_json(output / "corpus_manifest.json", {
        **corpus_info, "conditions": {c.name: {"corpus": c.corpus or "B0", "prior_limit": c.prior_limit}
                                       for c in CONDITIONS},
        "contains_raw_diary": False, "nested_sampling_verified": True,
    })
    write_json(output / "retrieval_index_manifest.json", {
        "method": "deterministic_aggregate_episode_onset_counts", "min_support_count": 10,
        "bucket_minutes": 30, "fallback_order": ["L0", "L1", "L2", "L3"],
        "index_hashes": {name: index.index_hash for name, index in indices.items()},
        "index_corpus_sizes": {name: index.corpus_size for name, index in indices.items()},
        "retrieval_llm_calls": 0,
    })
    write_json(output / "dataset_manifest.json", {
        "experiment_type": "behavior_prior_corpus_joint_pilot", "git_baseline_commit": BASELINE,
        "experiment_config_hash": config["experiment_config_hash"],
        "episodes_executed": len(rows), "complete_segments": completed,
        "provider_timeouts": provider_timeouts, "max_decisions_terminations": max_decisions,
        "architecture_failures": sum(row["termination_reason"] == "ARCHITECTURE_ERROR" for row in rows),
        "source_all_adult_diaries": corpus_info["source_all_adult_diaries"],
        "eligible_employed_weekday_diaries": corpus_info["eligible_employed_weekday_diaries"],
        "source_core7_sha256": corpus_info["source_sha256"],
        "calibration_profile_sha256": sha256(CALIBRATION_PROFILE),
        "production_protected_before": protected_before,
        "production_protected_after": {str(path.relative_to(ROOT)): sha256(path) for path in PROTECTED},
        "provider_alias": "ark-code-latest", "actual_provider_models": dict(models),
        "contains_hidden_reasoning": False, "contains_raw_prompt": False,
        "contains_credentials": False, "pilot_abort": abort,
    })


async def main() -> None:
    if START_MARKER.exists():
        raise RuntimeError("RESEARCH_A2_FAST_REAL_PILOT_ALREADY_STARTED")
    provider_config = DecisionProviderConfig.from_env()
    if provider_config.model != "ark-code-latest" or provider_config.base_url_category != CODING_PLAN:
        raise RuntimeError("A2_FAST_PROVIDER_CONFIG_MISMATCH")
    protected_before = {str(path.relative_to(ROOT)): sha256(path) for path in PROTECTED}
    corpora, corpus_info = load_nested_worker_corpora()
    indices = {name: BehaviorPriorIndex.build(days) for name, days in corpora.items()}
    if indices["B100"].index_hash != BehaviorPriorIndex.build(corpora["B100"]).index_hash:
        raise RuntimeError("RETRIEVAL_NONDETERMINISTIC")
    profile = load_experiment_profiles()[2]
    run_schedule = schedule()
    config = {
        "experiment_type": "behavior_prior_corpus_joint_pilot", "git_baseline_commit": BASELINE,
        "simulator_profile": profile.name, "simulator_profile_hash": profile.profile_hash,
        "schedule": run_schedule, "segment_start_states": {s: world_snapshot(segment_world(s)) for s in SEGMENTS},
        "conditions": [{"name": c.name, "corpus": c.corpus or "B0", "prior_limit": c.prior_limit}
                       for c in CONDITIONS],
        "corpus_sample_hashes": corpus_info["sample_id_hashes"],
        "retrieval_index_hashes": {name: index.index_hash for name, index in indices.items()},
        "min_support_count": 10, "tick_minutes": 15, "segment_minutes": 180,
        "max_decisions_per_segment": 8, "repetitions": 1,
        "provider_alias": provider_config.model, "request_fields": ["model", "messages"],
        "request_timeout_seconds": TIMEOUT_SECONDS, "transport_retries": 0,
    }
    config["experiment_config_hash"] = config_hash(config)
    # Reconfirm C0 has exactly the same first compact context as A2.0 G2.
    first = await CalibratedSegmentBenchmark(
        FakeDecisionClient('{"action":"LEISURE","target":null}'), OUTPUT_ROOT / "preflight",
        write_artifacts=False,
    ).run(1, "MORNING", profile)
    second = await CalibratedSegmentBenchmark(
        FakeDecisionClient('{"action":"LEISURE","target":null}'), OUTPUT_ROOT / "preflight",
        write_artifacts=False,
    ).run(2, "MORNING", profile)
    if first.trajectory.steps[0].context != second.trajectory.steps[0].context:
        raise RuntimeError("R0_CONTEXT_MISMATCH")
    output = OUTPUT_ROOT / f"real_{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}"
    provider = OpenAICompatibleDecisionClient(
        base_url=provider_config.api_base, api_key=provider_config.api_key,
        model=provider_config.model, timeout_seconds=TIMEOUT_SECONDS, minimal_request=True,
    )
    rows: list[dict[str, object]] = []
    abort: str | None = None
    try:
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        output.mkdir()
        (output / "episodes").mkdir()
        write_json(output / "experiment_config.json", config)
        write_json(output / "schedule.json", run_schedule)
        write_json(output / "query_coverage.json", {
            "query_grid": "48 half-hour buckets x (None + Core7 previous activity)",
            "min_support_count": 10,
            "threshold_sparsity_comparison_B100": {
                "10": query_coverage(indices["B100"]),
                "20": query_coverage(BehaviorPriorIndex.build(corpora["B100"], min_support_count=20)),
            },
            "corpora": {name: query_coverage(index) for name, index in indices.items()},
            "sanity_table": {name: sanity_table(index) for name, index in indices.items()},
        })
        audit_secrets(output, provider_config.api_key)
        write_json(START_MARKER, {"experiment_id": output.name, "started_at": datetime.now(timezone.utc).isoformat()})
        conditions = {c.name: c for c in CONDITIONS}
        consecutive_infrastructure_failures = 0
        for item in run_schedule:
            condition = conditions[item["condition"]]
            benchmark = CalibratedSegmentBenchmark(
                provider, output / "episodes", provider_config.model,
                prior_index=indices.get(condition.corpus), prior_limit=condition.prior_limit,
            )
            try:
                result = await benchmark.run(item["episode"], item["segment"], profile)
                validate_daily_trajectory(result)
                if result.decision_count > 8 or result.provider_request_count > result.decision_count:
                    raise RuntimeError("ARCHITECTURE_VIOLATION")
                if any(step.provider_request_count != 1 or step.prompt is not None
                       for step in result.trajectory.steps):
                    raise RuntimeError("REQUEST_OR_PROMPT_INVARIANT_VIOLATION")
                if condition.prior_limit == 0 and result.prior_audit:
                    raise RuntimeError("R0_PRIOR_LEAK")
                if condition.prior_limit and any(len(record["activities"]) > condition.prior_limit
                                                 for record in result.prior_audit):
                    raise RuntimeError("PRIOR_LIMIT_VIOLATION")
                row = condition_episode_metrics(result, segment=item["segment"], condition=condition)
                row["experiment_config_hash"] = config["experiment_config_hash"]
                rows.append(row)
                with (output / "trajectories.jsonl").open("a", encoding="utf-8") as file:
                    file.write(json.dumps({
                        "condition": condition.name, "corpus": condition.corpus or "B0",
                        "prior_limit": condition.prior_limit,
                        "behavior_profile_name": profile.name, "behavior_profile_hash": profile.profile_hash,
                        "experiment_config_hash": config["experiment_config_hash"],
                        "prior_audit": [dict(record) for record in result.prior_audit],
                        "trajectory": result.trajectory.to_dict(),
                    }, ensure_ascii=False) + "\n")
                audit_secrets(output, provider_config.api_key)
                if {str(path.relative_to(ROOT)): sha256(path) for path in PROTECTED} != protected_before:
                    abort = "PRODUCTION_CONFIG_MODIFIED"
                elif result.termination_reason.value == "ARCHITECTURE_ERROR":
                    abort = "ARCHITECTURE_VIOLATION"
                elif result.termination_reason.value in ("TIMEOUT", "PROVIDER_ERROR"):
                    consecutive_infrastructure_failures += 1
                else:
                    consecutive_infrastructure_failures = 0
                print(f"CELL={item['episode']}/20 {condition.name} {item['segment']} "
                      f"{result.termination_reason.value} ticks={len(result.ticks)} "
                      f"requests={result.provider_request_count}", flush=True)
                if abort:
                    break
                if consecutive_infrastructure_failures >= 3:
                    abort = "THREE_CONSECUTIVE_INFRASTRUCTURE_FAILURES"
                    break
            except Exception:
                abort = "ARCHITECTURE_OR_SECRET_VIOLATION"
                raise
        summarize(output, rows, config, corpus_info, indices, protected_before, abort)
        audit_secrets(output, provider_config.api_key)
        print(f"PILOT_EPISODES={len(rows)} ABORT={abort or 'none'} OUTPUT={output}", flush=True)
    finally:
        await provider.aclose()


if __name__ == "__main__":
    asyncio.run(main())
