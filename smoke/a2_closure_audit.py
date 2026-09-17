"""One-time, offline-only read of the seven frozen A2-Final cap failures."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from social_sim.a2_closure.audit import classify_max_decisions, summarize_audit


ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "run/evaluation/a2_final/real_20260917T101056138346Z"
OUTPUT_ROOT = ROOT / "run/evaluation/a2_closure"
MARKER = OUTPUT_ROOT / "a2_closure_started.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=False, indent=2, allow_nan=False)
        file.write("\n")


def main() -> None:
    if MARKER.exists():
        raise RuntimeError("CLOSURE_AUDIT_ALREADY_STARTED")
    stage = HISTORY / "stage_b"
    rows = read_jsonl(stage / "episode_rows.jsonl")
    max_rows = [row for row in rows if row["termination_reason"] == "MAX_DECISIONS"]
    if len(max_rows) != 7:
        raise RuntimeError("HISTORICAL_MAX_DECISIONS_NOT_SEVEN")
    trajectories = {entry["episode"]: entry["trajectory"]
                    for entry in read_jsonl(stage / "trajectories.jsonl")}
    sources = [stage / "episode_rows.jsonl", stage / "trajectories.jsonl",
               stage / "episode_001_failure.json"]
    cells = []
    for row in max_rows:
        number = row["episode_number"]
        daily_path = stage / "episodes/daily_episodes" / f"episode_{number:06d}.json"
        sources.append(daily_path)
        cells.append(classify_max_decisions(row, trajectories[number], read_json(daily_path)))
    before = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in sources}
    summary, prior = summarize_audit(cells)
    after = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in sources}
    if before != after:
        raise RuntimeError("HISTORICAL_ARTIFACT_CHANGED_DURING_READ")
    failure = read_json(stage / "episode_001_failure.json")
    if failure["episode"] != 1 or failure["termination_reason"] != "ARCHITECTURE_ERROR":
        raise RuntimeError("HISTORICAL_ARCHITECTURE_RECORD_MISMATCH")
    output = OUTPUT_ROOT / f"audit_{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}"
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    write_json(output / "source_manifest.json", {
        "historical_experiment": HISTORY.name, "historical_source_sha256": before,
        "historical_artifacts_read_only": True, "audit_provider_requests": 0,
        "contains_raw_prompt": False, "contains_hidden_reasoning": False,
    })
    write_json(output / "max_decision_audit.json", cells)
    with (output / "max_decision_audit.csv").open("x", encoding="utf-8", newline="") as file:
        fields = ("cell_id", "scenario", "condition", "observed_minutes", "decision_count",
                  "accepted_count", "rejected_count", "activity_minutes", "prior_count",
                  "termination_point", "primary_root_cause", "secondary_causes",
                  "trigger_reason_distribution", "repeated_rejected_count", "rejection_reasons",
                  "immediate_followup_count", "same_state_redecision_count", "cycle_signature",
                  "prior_mentions", "prior_followed", "prior_followed_and_executable",
                  "prior_followed_and_rejected", "prior_not_followed", "compact_trace")
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for cell in cells:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict))
                             else value for key, value in cell.items()})
    with (output / "compact_traces.txt").open("x", encoding="utf-8") as file:
        for cell in cells:
            file.write(f"CELL {cell['cell_id']} {cell['scenario']} {cell['condition']} "
                       f"PRIMARY={cell['primary_root_cause']}\n")
            file.write("\n".join(cell.get("compact_trace", [])) + "\n\n")
    write_json(output / "root_cause_summary.json", summary)
    write_json(output / "prior_loop_audit.json", prior)
    write_json(output / "architecture_error_audit.json", {
        "historical_cell_id": 1, "exception_type": "ValueError",
        "exception_message": failure["error"],
        "failure_site": "DailyEpisodeRunner.run_episode -> TrajectoryRecorder.finish_episode -> validate_trajectory: generic final-state check",
        "root_cause": "The A2-Final Stage B harness passed scenario_name=a2_final_micro; the generic validator expects immediate-step final-state equality, but daily ticks legitimately advance state after a decision. The existing neutral_day validator handles tick drift.",
        "minimal_fix": "Stage B harness passes scenario_name=neutral_day; no world, rule, reducer, provider, or decision semantics change.",
        "affected_fields": ["episode_001 validated trajectory absent", "request count unknown",
                            "behavior metrics unknown"],
        "stage_a_affected": False, "other_stage_b_cells_affected": False,
        "historical_cell_remains_invalid": True, "historical_cell_rerun": False,
        "regression_test": "tests/test_a2_closure_audit.py::test_daily_recording_scenario_name_regression_without_provider",
    })
    write_json(MARKER, {"experiment_id": output.name, "created_at": datetime.now(timezone.utc).isoformat(),
                        "historical_source_sha256": before})
    print(f"A2_CLOSURE_AUDIT_COMPLETE cells=7 dominant={summary['global_dominant_cause']} "
          f"prior_loop={prior['prior_loop_signal']} output={output}", flush=True)


if __name__ == "__main__":
    main()
