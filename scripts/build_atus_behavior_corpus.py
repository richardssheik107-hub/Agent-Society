"""Reproducible, descriptive ATUS 2025 ETL; never updates simulator parameters."""

# ruff: noqa: E402 -- repository src/ must be importable when invoked as a standalone CLI.

from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from social_sim.human_data.atus import REQUIRED_WHO, inspect_schema, load_atus_activity
from social_sim.human_data.mapping import load_mapping
from social_sim.human_data.models import BehaviorCorpus, BehaviorDay, HumanActivityType, merge_adjacent_same_activity
from social_sim.human_data.stats import distribution, summarize
from social_sim.human_data.validation import validate_diary


DEFAULT_DATA = ROOT / "data/external/atus/2025"
DEFAULT_OUTPUT = ROOT / "run/human_data/atus_2025"


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _episode_dict(ep) -> dict[str, object]:
    value = asdict(ep)
    value["canonical_activity"] = ep.canonical_activity.value
    return value


def build(data_root: Path, output: Path, mapping_path: Path, seed: int = 2025) -> dict[str, object]:
    source = json.loads((data_root / "SOURCE.json").read_text(encoding="utf-8"))
    for record in source["files"]:
        path = data_root / "raw" / record["name"]
        if _sha256(path) != record["sha256"]:
            raise ValueError(f"raw SHA256 mismatch: {path}")
    files = {"activity": "atusact-2025.zip", "respondent": "atusresp-2025.zip", "roster": "atusrost-2025.zip", "who": "atuswho-2025.zip"}
    schemas = {key: inspect_schema(data_root / "raw" / name) for key, name in files.items()}
    if not REQUIRED_WHO.issubset(schemas["who"]):
        raise ValueError(f"Who schema lacks required columns: {schemas['who']}")
    mapping = load_mapping(mapping_path)
    loaded = load_atus_activity(*(data_root / "raw" / files[name] for name in ("activity", "respondent", "roster")), mapping)
    statuses = [(diary, validate_diary(diary)) for diary in loaded.diaries]
    valid = tuple(diary for diary, result in statuses if result.valid)
    excluded = [(diary, result) for diary, result in statuses if not result.valid]
    employed_weekday = tuple(d for d in valid if d.metadata["employment_status"] in ("1", "2") and d.metadata["weekday"])
    all_stats = summarize(valid)
    worker_stats = summarize(employed_weekday)
    output.mkdir(parents=True, exist_ok=True)
    processed = data_root / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    _write_json(processed / "schema_inspection.json", schemas)
    excluded_rows = [{"day_id": diary.day_id, "reason": ";".join(result.reasons), "total_minutes": diary.total_minutes} for diary, result in excluded]
    excluded_rows += [{"day_id": day_id, "reason": reason, "total_minutes": ""} for day_id, reason in loaded.parse_errors]
    _write_csv(processed / "excluded_diaries.csv", ["day_id", "reason", "total_minutes"], excluded_rows)
    summary = {"dataset": "ATUS", "year": 2025, "raw_activity_rows": loaded.activity_rows, "raw_respondent_rows": loaded.respondent_rows, "raw_roster_rows": loaded.roster_rows, "unique_activity_diary_ids": loaded.unique_activity_cases, "minor_diaries_filtered": loaded.minor_cases, "unmatched_activity_cases": loaded.unmatched_activity_cases, "adult_diaries": len(loaded.diaries) + len(loaded.parse_errors), "valid_adult_diaries": len(valid), "excluded_adult_diaries": len(excluded_rows), "employed_weekday_diaries": len(employed_weekday), "valid_total_minutes_distribution": distribution([d.total_minutes for d in valid]), "all_adults": {"raw_episodes": all_stats["raw_episode_count"], "canonical_merged_episodes": all_stats["canonical_merged_episode_count"], "coverage": all_stats["coverage"]}, "employed_weekday": {"raw_episodes": worker_stats["raw_episode_count"], "canonical_merged_episodes": worker_stats["canonical_merged_episode_count"], "coverage": worker_stats["coverage"]}, "sampling_note": "Unweighted descriptive pilot; not population estimates."}
    _write_json(output / "dataset_summary.json", summary)
    _write_json(output / "mapping_coverage.json", {"all_adults": all_stats["coverage"], "employed_weekday": worker_stats["coverage"], "mapping_version": mapping.version})
    duration_rows = []
    daily_rows = []
    start_rows = []
    transition_rows = []
    prob_rows = []
    for sample, stats in (("all_adults", all_stats), ("employed_weekday", worker_stats)):
        for kind in HumanActivityType:
            duration_rows.append({"sample": sample, "activity": kind.value, **stats["episode_duration"][kind.value]})
            daily_rows.append({"sample": sample, "activity": kind.value, **stats["daily_duration"][kind.value]})
        for kind in HumanActivityType:
            if kind == HumanActivityType.OTHER:
                continue
            for bin_index in range(48):
                start_rows.append({"sample": sample, "activity": kind.value, "bin_start_minute": bin_index * 30, "count": stats["start_bins"][(kind.value, bin_index)]})
        outgoing = Counter()
        for (origin, destination), count in stats["transitions"].items():
            outgoing[origin] += count
        for origin in HumanActivityType:
            for destination in HumanActivityType:
                count = stats["transitions"][(origin.value, destination.value)]
                transition_rows.append({"sample": sample, "from_activity": origin.value, "to_activity": destination.value, "count": count})
                prob_rows.append({"sample": sample, "from_activity": origin.value, "to_activity": destination.value, "probability": round(count / outgoing[origin.value], 6) if outgoing[origin.value] else 0})
    _write_csv(output / "activity_duration_stats.csv", ["sample", "activity", "count", "mean", "median", "p25", "p75", "p90", "p95"], duration_rows)
    _write_csv(output / "daily_duration_stats.csv", ["sample", "activity", "count", "mean", "median", "p25", "p75"], daily_rows)
    _write_csv(output / "start_time_histogram.csv", ["sample", "activity", "bin_start_minute", "count"], start_rows)
    _write_csv(output / "transition_counts.csv", ["sample", "from_activity", "to_activity", "count"], transition_rows)
    _write_csv(output / "transition_probs.csv", ["sample", "from_activity", "to_activity", "probability"], prob_rows)
    _write_json(output / "activity_count_stats.json", {"all_adults": all_stats["activity_counts"], "employed_weekday": worker_stats["activity_counts"]})
    _write_json(output / "top_other.json", {"all_adults": all_stats["other_top20"], "employed_weekday": worker_stats["other_top20"]})
    _write_json(output / "calibration_candidates.json", {"status": "CANDIDATE_ONLY_NOT_PRODUCTION", "source": "ATUS 2025 unweighted employed weekday" if employed_weekday else "ATUS 2025 unweighted all adults", "activities": {kind.value: {"episode_duration_median": worker_stats["episode_duration"][kind.value]["median"] if employed_weekday else all_stats["episode_duration"][kind.value]["median"], "episode_duration_iqr": [worker_stats["episode_duration"][kind.value]["p25"], worker_stats["episode_duration"][kind.value]["p75"]] if employed_weekday else [all_stats["episode_duration"][kind.value]["p25"], all_stats["episode_duration"][kind.value]["p75"]], "daily_minutes_median": worker_stats["daily_duration"][kind.value]["median"] if employed_weekday else all_stats["daily_duration"][kind.value]["median"]} for kind in HumanActivityType}})
    days = [BehaviorDay(day_id=d.day_id, canonical_episodes=merge_adjacent_same_activity(d.episodes), metadata=d.metadata) for d in valid]
    corpus = BehaviorCorpus(days)
    with (output / "behavior_days.jsonl").open("w", encoding="utf-8") as stream:
        for day in days:
            stream.write(json.dumps({"day_id": day.day_id, "canonical_episodes": [_episode_dict(ep) for ep in day.canonical_episodes], "metadata": day.metadata}, ensure_ascii=False) + "\n")
    nested = {f"B{size}": [day.day_id for day in corpus.sample_days(size, seed)] for size in (100, 1000, 10000) if len(corpus) >= size}
    _write_json(output / "nested_sample_ids.json", {"seed": seed, "samples": nested})
    manifest = {"dataset": "ATUS", "year": 2025, "source": source["source_page"], "download_checksums": {row["name"]: row["sha256"] for row in source["files"]}, "raw_activity_rows": loaded.activity_rows, "valid_diaries": len(valid), "excluded_diaries": len(excluded_rows), "mapping_version": mapping.version, "mapping_coverage": all_stats["coverage"], "contains_personal_identifiers": False, "privacy_assessment": "Public anonymized survey case IDs only; no names or re-identification attempted. Case IDs retained locally in ignored outputs.", "artifacts": {path.name: {"sha256": _sha256(path), "size_bytes": path.stat().st_size} for path in sorted(output.iterdir()) if path.is_file() and path.name != "dataset_manifest.json"}}
    _write_json(output / "dataset_manifest.json", manifest)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--mapping", type=Path, default=ROOT / "config/atus_activity_mapping.yaml")
    parser.add_argument("--seed", type=int, default=2025)
    args = parser.parse_args()
    print(json.dumps(build(args.data_root, args.output, args.mapping, args.seed), indent=2))


if __name__ == "__main__":
    main()
