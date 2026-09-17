"""Build descriptive NHAPS/AHTUS artifacts without changing simulator parameters."""

# ruff: noqa: E402 -- allow standalone invocation from the integration repository.
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import asdict
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scripts.download_nhaps_ahtus_1992_94 import DEFAULT_ROOT, inspect_zip, sha256
from scripts.inspect_nhaps_ahtus_schema import inspect
from social_sim.human_data.models import BehaviorCorpus, BehaviorDay, HumanActivityType, merge_adjacent_same_activity
from social_sim.human_data.nhaps_ahtus import load_sav
from social_sim.human_data.stats import distribution, summarize
from social_sim.human_data.validation import validate_diary

OUTPUT = ROOT / "run/human_data/nhaps_ahtus_1992_94"
MAPPING = ROOT / "config/nhaps_ahtus_activity_mapping.yaml"


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def weighted_percentile(pairs: list[tuple[int, float]], q: float) -> float | None:
    positive = sorted((v, w) for v, w in pairs if w > 0 and math.isfinite(w))
    if not positive:
        return None
    threshold = sum(w for _, w in positive) * q
    cumulative = 0.0
    for value, weight in positive:
        cumulative += weight
        if cumulative >= threshold:
            return float(value)
    return float(positive[-1][0])


def weighted_distribution(pairs: list[tuple[int, float]]) -> dict[str, float | int | None]:
    positive = [(value, weight) for value, weight in pairs if weight > 0 and math.isfinite(weight)]
    total = sum(weight for _, weight in positive)
    return {"count_positive_weight": len(positive), "weight_sum": round(total, 3), "mean": round(sum(v * w for v, w in positive) / total, 2) if total else None,
            "median": weighted_percentile(positive, .5), "p25": weighted_percentile(positive, .25), "p75": weighted_percentile(positive, .75), "p90": weighted_percentile(positive, .9)}


def build(data_root: Path = DEFAULT_ROOT, output: Path = OUTPUT, mapping_path: Path = MAPPING, seed: int = 2025) -> dict[str, object]:
    source = json.loads((data_root / "SOURCE.json").read_text(encoding="utf-8"))
    archive = data_root / "raw" / source["archive_filename"]
    if sha256(archive) != source["archive_sha256"]:
        raise ValueError("immutable source archive checksum mismatch")
    members = inspect_zip(archive)
    inspect(data_root, output)  # verifies extracted members and refreshes metadata artifacts.
    work = data_root / "processed/work"
    loaded, mapping = load_sav(*(work / Path(members[key]).name for key in ("USA92_94quest.sav", "USA1993hfsum.sav", "USA1993hfep.sav")), mapping_path)
    checked = [(diary, validate_diary(diary)) for diary in loaded.diaries]
    valid = tuple(d for d, result in checked if result.valid and not d.metadata["summary_mismatch"])
    excluded = [{"day_id": d.day_id, "reason": ";".join(result.reasons) if not result.valid else "summary_mismatch", "total_minutes": d.total_minutes} for d, result in checked if not result.valid or d.metadata["summary_mismatch"]]
    excluded.extend({"day_id": day, "reason": reason, "total_minutes": ""} for day, reason in loaded.parse_errors)
    write_csv(data_root / "processed/excluded_diaries.csv", ["day_id", "reason", "total_minutes"], excluded)
    subsets = {"all_adults": valid, "employed_adults": tuple(d for d in valid if d.metadata["employment_status"] in (1, 2)),
               "employed_weekday": tuple(d for d in valid if d.metadata["employment_status"] in (1, 2) and d.metadata["weekday"])}
    stats = {name: summarize(days) for name, days in subsets.items()}
    summary = {"dataset": "NHAPS_AHTUS_1992_94", "raw_diarists": loaded.raw_diarists, "background_rows": loaded.raw_background_rows,
               "summary_rows": loaded.raw_summary_rows, "episode_rows": loaded.raw_episode_rows, "adult_diaries": len(loaded.diaries) + len(loaded.parse_errors),
               "minor_cases": loaded.minor_cases, "missing_age_cases": loaded.missing_age_cases,
               "unmatched_background": loaded.unmatched_background, "unmatched_summary": loaded.unmatched_summary,
               "valid_diaries": len(valid), "invalid_adult_diaries": len(excluded), "summary_mismatches": len(loaded.summary_mismatches),
               "subsets": {name: len(days) for name, days in subsets.items()}, "total_minutes": distribution([d.total_minutes for d in valid]),
               "quality_flags": dict(Counter(f"lowqual={d.metadata['lowqual']},baddem={d.metadata['baddem']}" for d in valid)),
               "weight_positive_diaries": sum(d.metadata["recwght"] > 0 for d in valid),
               "note": "Strict full 1440-minute diaries; descriptive, not final population calibration."}
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "SOURCE.json", source)
    write_json(output / "dataset_summary.json", summary)
    write_json(output / "mapping_coverage.json", {name: s["coverage"] for name, s in stats.items()})
    audit: dict[int, Counter[str]] = defaultdict(Counter)
    location: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for diary in valid:
        for ep in diary.episodes:
            audit[int(ep.raw_activity_code)]["episodes"] += 1
            audit[int(ep.raw_activity_code)]["minutes"] += ep.duration_minutes
            location[(ep.canonical_activity.value, ep.location_raw or "unknown")]["episodes"] += 1
            location[(ep.canonical_activity.value, ep.location_raw or "unknown")]["minutes"] += ep.duration_minutes
    audit_rows = []
    for code in sorted(audit):
        rule = mapping.rules.get(code)
        audit_rows.append({"source_code": code, "source_label": mapping.actual_labels.get(code, "unknown"), "episode_count": audit[code]["episodes"],
                           "total_minutes": audit[code]["minutes"], "canonical_mapping": rule["canonical_activity"] if rule else "OTHER",
                           "confidence": rule["confidence"] if rule else "unmapped_conservative"})
    write_csv(output / "mapping_audit.csv", list(audit_rows[0]), audit_rows)
    other_top = sorted((r for r in audit_rows if r["canonical_mapping"] == "OTHER"), key=lambda r: -r["total_minutes"])[:30]
    write_csv(output / "top_other_categories.csv", list(audit_rows[0]), other_top)
    location_labels = {int(float(k)): v for k, v in json.loads((output / "schema_episode.json").read_text(encoding="utf-8"))["value_labels"]["eloc"].items()}
    loc_rows = [{"activity": k, "source_location_code": loc, "source_location_label": location_labels.get(int(loc), "unknown"),
                 "episode_count": counts["episodes"], "minutes": counts["minutes"]} for (k, loc), counts in sorted(location.items())]
    write_csv(output / "activity_location.csv", list(loc_rows[0]), loc_rows)
    duration_rows = []
    daily_rows = []
    start_rows = []
    transition_rows = []
    prob_rows = []
    weighted_rows = []
    weighted_episode_rows = []
    for name, days in subsets.items():
        s = stats[name]
        for kind in HumanActivityType:
            activity = kind.value
            duration_rows.append({"subset": name, "activity": activity, **s["episode_duration"][activity]})
            daily = s["daily_duration"][activity]
            daily_rows.append({"subset": name, "activity": activity, **daily, "p90": distribution([sum(ep.duration_minutes for ep in d.episodes if ep.canonical_activity == kind) for d in days], episode=True)["p90"]})
            weighted_rows.append({"subset": name, "activity": activity, **weighted_distribution([(sum(ep.duration_minutes for ep in d.episodes if ep.canonical_activity == kind), float(d.metadata["recwght"])) for d in days])})
            merged_weighted = [(ep.duration_minutes, float(d.metadata["recwght"])) for d in days for ep in merge_adjacent_same_activity(d.episodes) if ep.canonical_activity == kind]
            weighted_episode_rows.append({"subset": name, "activity": activity, **weighted_distribution(merged_weighted),
                                          "p95": weighted_percentile(merged_weighted, .95)})
            if kind != HumanActivityType.OTHER:
                for bin_index in range(48):
                    start_rows.append({"subset": name, "activity": activity, "bin_start_minute": bin_index * 30, "count": s["start_bins"][(activity, bin_index)]})
        outgoing = Counter()
        for (left, _), count in s["transitions"].items():
            outgoing[left] += count
        for left in HumanActivityType:
            for right in HumanActivityType:
                count = s["transitions"][(left.value, right.value)]
                transition_rows.append({"subset": name, "from_activity": left.value, "to_activity": right.value, "count": count})
                prob_rows.append({"subset": name, "from_activity": left.value, "to_activity": right.value, "probability": round(count / outgoing[left.value], 6) if outgoing[left.value] else 0})
    write_csv(output / "activity_episode_duration.csv", list(duration_rows[0]), duration_rows)
    write_csv(output / "daily_activity_duration.csv", list(daily_rows[0]), daily_rows)
    write_csv(output / "weighted_daily_activity_duration.csv", list(weighted_rows[0]), weighted_rows)
    write_csv(output / "weighted_activity_episode_duration.csv", list(weighted_episode_rows[0]), weighted_episode_rows)
    write_csv(output / "start_time_histogram.csv", list(start_rows[0]), start_rows)
    write_csv(output / "transition_counts.csv", list(transition_rows[0]), transition_rows)
    write_csv(output / "transition_probs.csv", list(prob_rows[0]), prob_rows)
    write_json(output / "activity_count_stats.json", {name: s["activity_counts"] for name, s in stats.items()})
    write_json(output / "weighted_coverage.json", {name: {"core5_minute_share": round(sum(float(d.metadata["recwght"]) * sum(ep.duration_minutes for ep in d.episodes if ep.canonical_activity != HumanActivityType.OTHER) for d in days) / sum(float(d.metadata["recwght"]) * d.total_minutes for d in days if float(d.metadata["recwght"]) > 0), 6), "weight": "recwght; positive-weight only; diary-level weighting"} for name, days in subsets.items()})
    candidates = {"status": "CANDIDATE_ONLY_NOT_PRODUCTION", "source": "NHAPS/AHTUS 1992–94 employed weekday descriptive", "no_simulator_mutation": True,
                  "activities": {kind.value: {"empirical_merged_episode": stats["employed_weekday"]["episode_duration"][kind.value],
                                               "empirical_daily": next(row for row in daily_rows if row["subset"] == "employed_weekday" and row["activity"] == kind.value)} for kind in HumanActivityType}}
    write_json(output / "calibration_candidates.json", candidates)
    days = [BehaviorDay(day_id=d.day_id, canonical_episodes=merge_adjacent_same_activity(d.episodes), metadata=d.metadata) for d in valid]
    corpus = BehaviorCorpus(days)
    with (output / "behavior_days.jsonl").open("w", encoding="utf-8") as stream:
        for day in days:
            stream.write(json.dumps({"day_id": day.day_id, "canonical_sequence": ">".join(ep.canonical_activity.value for ep in day.canonical_episodes),
                                     "canonical_merged_episodes": len(day.canonical_episodes), "unique_canonical_types": len({ep.canonical_activity for ep in day.canonical_episodes}),
                                     "transition_count": max(len(day.canonical_episodes) - 1, 0),
                                     "canonical_episodes": [{**asdict(ep), "canonical_activity": ep.canonical_activity.value} for ep in day.canonical_episodes],
                                     "metadata": day.metadata}, ensure_ascii=False) + "\n")
    ordered = [day.day_id for day in corpus.sample_days(len(corpus), seed)]
    write_json(output / "nested_sample_ids.json", {"seed": seed, "samples": {"B100": ordered[:100] if len(corpus) >= 100 else None,
                                                         "B1000": ordered[:1000] if len(corpus) >= 1000 else None, "BALL": ordered}})
    top_transitions = sorted(((left, right, count) for (left, right), count in stats["all_adults"]["transitions"].items() if left != right), key=lambda row: -row[2])[:30]
    write_csv(output / "top_transitions.csv", ["rank", "from_activity", "to_activity", "count"],
              [{"rank": i, "from_activity": left, "to_activity": right, "count": count} for i, (left, right, count) in enumerate(top_transitions, 1)])
    note = ["# NHAPS/AHTUS 1992–94 pilot", "", f"Archive SHA256: `{source['archive_sha256']}`. Raw diarists {loaded.raw_diarists}; valid adult diaries {len(valid)}; excluded adult diaries {len(excluded)}; age missing {loaded.missing_age_cases}.",
            f"Core5 episode coverage: {stats['all_adults']['coverage']['mapped_to_core_ratio']:.3%}; minute coverage: {stats['all_adults']['coverage']['mapped_to_core_minute_ratio']:.3%}.",
            "", "## Top OTHER by minutes", *[f"- {row['source_code']} {row['source_label']}: {row['total_minutes']:,} min" for row in other_top[:10]],
            "", "## Top 30 canonical transitions", *[f"- {i}. {left} → {right}: {count:,}" for i, (left, right, count) in enumerate(top_transitions, 1)],
            "", "Descriptive only: 1990s U.S. diary data; no policy or simulator parameter has been changed. LEISURE includes sports/media/social; MOVE means empirical travel, not an executable MOVE. Zero-weight low-quality diaries remain in the unweighted corpus but are excluded from weighted descriptions."]
    (output / "summary.md").write_text("\n".join(note) + "\n", encoding="utf-8")
    import pyreadstat
    manifest = {"dataset": "NHAPS", "source_family": "AHTUS", "survey_years": "1992-94", "source_provider": "Centre for Time Use Research",
                "source_archive_sha256": source["archive_sha256"], "reader": f"pyreadstat {pyreadstat.__version__}", "mapping_version": mapping.version,
                "raw_rows": {"background": loaded.raw_background_rows, "summary": loaded.raw_summary_rows, "episode": loaded.raw_episode_rows},
                "valid_diaries": len(valid), "invalid_adult_diaries": len(excluded), "contains_hidden_reasoning": False, "LLM_calls": 0,
                "privacy": "Anonymized survey identifiers only; local ignored artifacts; no reidentification.",
                "artifacts": {p.name: {"sha256": sha256(p), "size_bytes": p.stat().st_size, "source_archive_sha256": source["archive_sha256"]} for p in sorted(output.iterdir()) if p.is_file() and p.name != "dataset_manifest.json"}}
    write_json(output / "dataset_manifest.json", manifest)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--mapping", type=Path, default=MAPPING)
    parser.add_argument("--seed", type=int, default=2025)
    args = parser.parse_args()
    print(json.dumps(build(args.data_root, args.output, args.mapping, args.seed), indent=2))
