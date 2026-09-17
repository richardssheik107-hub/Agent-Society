"""One-time interleaved 24-cell A2.0 real-provider segmented pilot."""

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

from social_sim.daily.calibrated import (  # noqa: E402
    CalibratedSegmentBenchmark, aggregate, config_hash, episode_metrics,
    interleaved_schedule, segment_world,
)
from social_sim.daily.profiles import SOURCE, load_experiment_profiles  # noqa: E402
from social_sim.daily.validation import validate_daily_trajectory  # noqa: E402
from social_sim.decision import OpenAICompatibleDecisionClient  # noqa: E402
from social_sim.decision.config import CODING_PLAN, DecisionProviderConfig  # noqa: E402
from social_sim.evaluation.models import world_snapshot  # noqa: E402


OUTPUT_ROOT = ROOT / "run/evaluation/calibrated_neutral_day"
START_MARKER = OUTPUT_ROOT / "real_pilot_started.json"
BASELINE = "9139744cc67d8d0279821ef9750990af5642dc87"
TIMEOUT_SECONDS = 60


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


def summarize(output: Path, rows: list[dict[str, object]], profiles: tuple,
              configuration: dict[str, object], *, abort: str | None) -> None:
    per_profile = {p.name: aggregate([row for row in rows if row["profile"] == p.name]) for p in profiles}
    per_cell = {f"{p.name}__{segment}": aggregate([
        row for row in rows if row["profile"] == p.name and row["segment"] == segment
    ]) for p in profiles for segment in ("MORNING", "WORK", "MIDDAY", "EVENING")}
    write_json(output / "profile_metrics.json", per_profile)
    write_json(output / "profile_segment_metrics.json", per_cell)
    with (output / "summary.csv").open("x", encoding="utf-8", newline="") as file:
        fields = ["profile", "segment", "episode_id", "repeat", "segment_completion", "termination_reason",
                  "decision_count", "provider_request_count", "decision_burst_count", "idle_ratio",
                  "unique_activity_types", "personal_care_proposals", "chores_proposals"]
        writer = csv.DictWriter(file, fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    model_counts = Counter()
    for row in rows:
        model_counts.update(row["provider_models"])
    def comparison(left: str, right: str, field: str) -> str:
        a, b = per_profile[left][f"avg_{field}"], per_profile[right][f"avg_{field}"]
        return "NA (incomplete cells)" if a is None or b is None else f"{b - a:+.3f} ({a:.3f} → {b:.3f})"
    lines = [
        "# A2.0 Segmented Real Pilot", "",
        f"Executed {len(rows)}/24 independent segments; abort={abort or 'none'}.",
        "Only completed segments enter behavioral averages; incomplete cells remain NA. ",
        "Cross-profile overall means and deltas are descriptive/unpaired and selection-biased when completion rates differ.", "",
        "| Profile | Complete | Truncated | Provider failures | Avg decisions | Avg bursts | Avg idle ratio | Avg unique activities |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, summary in per_profile.items():
        values = [summary[f"avg_{k}"] for k in ("decision_count", "decision_burst_count", "idle_ratio", "unique_activity_types")]
        lines.append(f"| {name} | {summary['complete_segments']} | {summary['truncated_segments']} | {summary['provider_failures']} | "
                     + " | ".join("NA" if v is None else f"{v:.3f}" for v in values) + " |")
    lines += ["", "## Duration effect: G0 vs G1 (descriptive, unpaired)", "",
              f"Decision count Δ: {comparison('G0_ORIGINAL', 'G1_DURATION', 'decision_count')}",
              f"Decision burst Δ: {comparison('G0_ORIGINAL', 'G1_DURATION', 'decision_burst_count')}",
              f"Provider requests Δ: {comparison('G0_ORIGINAL', 'G1_DURATION', 'provider_request_count')}",
              "", "## Ontology effect: G1 vs G2 (descriptive, unpaired)", "",
              f"Idle ratio Δ: {comparison('G1_DURATION', 'G2_CORE7', 'idle_ratio')}",
              f"Activity diversity Δ: {comparison('G1_DURATION', 'G2_CORE7', 'unique_activity_types')}",
              "", "## Provider failures and context cost", "",
              f"Actual provider models: {json.dumps(dict(model_counts), sort_keys=True)}", "",
              "Profile×segment results and context/token/latency data are in profile_segment_metrics.json.",
              "G2 did not select either new action in this pilot; an ontology effect on idle cannot be inferred.",
              "No causal winner or human-likeness inference is supported by two repetitions.", "",
    ]
    with (output / "summary.md").open("x", encoding="utf-8") as file:
        file.write("\n".join(lines))
    source_data = __import__("yaml").safe_load(SOURCE.read_text(encoding="utf-8"))
    write_json(output / "dataset_manifest.json", {
        "experiment_type": "calibrated_neutral_day_baseline", "git_baseline_commit": BASELINE,
        "experiment_config_hash": configuration["experiment_config_hash"],
        "profile_hashes": {p.name: p.profile_hash for p in profiles},
        "source_calibration_profile": "config/experimental/neutral_day_calibrated_v1.yaml",
        "source_profile_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "nhaps_source_archive_sha256": source_data["source"]["archive_sha256"],
        "corpus_size": 0, "behavior_support": "B0_NONE", "provider_alias": "ark-code-latest",
        "actual_provider_models": dict(model_counts), "contains_hidden_reasoning": False,
        "contains_raw_prompt": False, "episodes_executed": len(rows), "pilot_abort": abort,
    })


async def main() -> None:
    if START_MARKER.exists():
        raise RuntimeError("RESEARCH_A2_REAL_PILOT_ALREADY_STARTED")
    config = DecisionProviderConfig.from_env()
    if config.model != "ark-code-latest" or config.base_url_category != CODING_PLAN:
        raise RuntimeError("A2_PROVIDER_CONFIG_MISMATCH")
    profiles = load_experiment_profiles()
    by_name = {profile.name: profile for profile in profiles}
    schedule = interleaved_schedule(profiles)
    output = OUTPUT_ROOT / f"real_{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}"
    configuration = {
        "experiment_type": "calibrated_neutral_day_baseline", "git_baseline_commit": BASELINE,
        "profile_hashes": {p.name: p.profile_hash for p in profiles},
        "schedule": schedule, "start_states": {segment: world_snapshot(segment_world(segment))
                                             for segment in ("MORNING", "WORK", "MIDDAY", "EVENING")},
        "tick_minutes": 15, "segment_minutes": 180, "max_decisions_per_segment": 8,
        "repeats": 2, "corpus_size": 0, "behavior_support": "B0_NONE",
        "provider_alias": config.model, "request_fields": ["model", "messages"],
        "request_timeout_seconds": TIMEOUT_SECONDS, "transport_retries": 0,
    }
    configuration["experiment_config_hash"] = config_hash(configuration)
    provider = OpenAICompatibleDecisionClient(
        base_url=config.api_base, api_key=config.api_key, model=config.model,
        timeout_seconds=TIMEOUT_SECONDS, minimal_request=True,
    )
    rows: list[dict[str, object]] = []
    consecutive_infrastructure_failures = 0
    abort: str | None = None
    try:
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        output.mkdir()
        (output / "episodes").mkdir()
        write_json(output / "experiment_config.json", configuration)
        write_json(output / "profile_snapshots.json", {p.name: {**p.snapshot(), "profile_hash": p.profile_hash} for p in profiles})
        write_json(output / "schedule.json", schedule)
        audit_secrets(output, config.api_key)
        write_json(START_MARKER, {"experiment_id": output.name, "started_at": datetime.now(timezone.utc).isoformat()})
        benchmark = CalibratedSegmentBenchmark(provider, output / "episodes", config.model)
        for item in schedule:
            try:
                result = await benchmark.run(item["episode"], item["segment"], by_name[item["profile"]])
                validate_daily_trajectory(result)
                if result.decision_count > 8 or result.provider_request_count > result.decision_count:
                    raise RuntimeError("ARCHITECTURE_VIOLATION")
                if any(step.prompt is not None for step in result.trajectory.steps):
                    raise RuntimeError("RAW_PROMPT_RETAINED")
                row = episode_metrics(result, segment=item["segment"], repeat=item["repeat"])
                row["experiment_config_hash"] = configuration["experiment_config_hash"]
                rows.append(row)
                with (output / "trajectories.jsonl").open("a", encoding="utf-8") as file:
                    file.write(json.dumps({"behavior_profile_name": result.behavior_profile_name,
                                           "behavior_profile_hash": result.behavior_profile_hash,
                                           "experiment_config_hash": configuration["experiment_config_hash"],
                                           "trajectory": result.trajectory.to_dict()}, ensure_ascii=False) + "\n")
                audit_secrets(output, config.api_key)
                reason = result.termination_reason.value
                if reason == "ARCHITECTURE_ERROR":
                    abort = "ARCHITECTURE_VIOLATION"
                elif reason in ("TIMEOUT", "PROVIDER_ERROR"):
                    consecutive_infrastructure_failures += 1
                    if consecutive_infrastructure_failures >= 3:
                        abort = "THREE_CONSECUTIVE_INFRASTRUCTURE_FAILURES"
                else:
                    consecutive_infrastructure_failures = 0
                print(f"CELL={item['episode']}/24 {item['profile']} {item['segment']} "
                      f"{reason} ticks={len(result.ticks)} requests={result.provider_request_count}", flush=True)
                if abort:
                    break
            except Exception:
                abort = "ARCHITECTURE_OR_SECRET_VIOLATION"
                raise
        summarize(output, rows, profiles, configuration, abort=abort)
        audit_secrets(output, config.api_key)
        print(f"PILOT_EPISODES={len(rows)} ABORT={abort or 'none'} OUTPUT={output}", flush=True)
    finally:
        await provider.aclose()


if __name__ == "__main__":
    asyncio.run(main())
