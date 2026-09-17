"""Offline B1.2 shadow-ontology calibration from the verified B1.1 NHAPS pilot."""

# ruff: noqa: E402 -- standalone CLI in the integration repository.
from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import asdict
import json
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from social_sim.calibration.coverage import measure, merged_shadow
from social_sim.calibration.duration import as_rows, comparisons, decision_frequency_counterfactual, duration_stats
from social_sim.calibration.ontology import (
    BehaviorDomainCandidate, CORE5, DOMAIN_ORDER, SOURCE_BY_CODE, SOURCE_CATEGORIES,
    TARGET_MINUTE_COVERAGE, select_minimal_ontology,
)
from social_sim.calibration.profiles import recommendation
from social_sim.calibration.validation import file_sha256, validate_coverage, validate_profile, validate_unchanged
from social_sim.human_data.models import BehaviorCorpus, BehaviorDay
from social_sim.human_data.nhaps_ahtus import load_sav
from social_sim.human_data.stats import percentile
from social_sim.human_data.validation import validate_diary


DEFAULT_INPUT = ROOT / "run/human_data/nhaps_ahtus_1992_94"
DEFAULT_OUTPUT = ROOT / "run/calibration/neutral_day_v1"
DEFAULT_PROFILE = ROOT / "config/experimental/neutral_day_calibrated_v1.yaml"
DATA_ROOT = ROOT / "data/external/ahtus/nhaps_1992_94"
MAPPING = ROOT / "config/nhaps_ahtus_activity_mapping.yaml"
INPUT_NAMES = ("SOURCE.json", "dataset_manifest.json", "mapping_audit.csv", "mapping_coverage.json", "behavior_days.jsonl", "activity_episode_duration.csv", "daily_activity_duration.csv", "start_time_histogram.csv", "transition_counts.csv", "transition_probs.csv", "nested_sample_ids.json", "schema_episode.json", "schema_background.json", "schema_summary.json")
PRODUCTION_FILES = (ROOT / "src/social_sim/daily/time.py", ROOT / "src/social_sim/daily/runner.py", ROOT / "src/social_sim/decision/models.py", *(ROOT / f"src/social_sim/rules/{name}.py" for name in ("base", "engine", "activity", "eating", "movement", "purchasing")))
ONTOLOGY_VERSION = "shadow-nhaps-main-v1"
CALIBRATION_VERSION = "neutral-day-calibrated-v1"


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def verified_inputs(source_dir: Path) -> tuple[dict[str, object], dict[str, str]]:
    source = read_json(source_dir / "SOURCE.json")
    previous = read_json(source_dir / "dataset_manifest.json")
    if previous["source_archive_sha256"] != source["archive_sha256"] or previous["dataset"] != "NHAPS":
        raise ValueError("B1.1 dataset/ZIP provenance mismatch")
    checksums = {name: file_sha256(source_dir / name) for name in INPUT_NAMES}
    for name in INPUT_NAMES:
        if name != "dataset_manifest.json" and previous["artifacts"][name]["sha256"] != checksums[name]:
            raise ValueError(f"B1.1 artifact checksum mismatch: {name}")
    return source, checksums


def load_verified_diaries(source_dir: Path, data_root: Path, source: dict[str, object]):
    archive = data_root / "raw" / source["archive_filename"]
    if file_sha256(archive) != source["archive_sha256"]:
        raise ValueError("original source ZIP checksum mismatch")
    work = data_root / "processed/work"
    schemas = [read_json(source_dir / f"schema_{kind}.json") for kind in ("background", "summary", "episode")]
    files = []
    for schema in schemas:
        if schema["source_archive_sha256"] != source["archive_sha256"]:
            raise ValueError("SAV schema provenance mismatch")
        path = work / Path(schema["source_member"]).name
        if file_sha256(path) != schema["extracted_sha256"]:
            raise ValueError(f"processed SAV checksum mismatch: {path.name}")
        files.append(path)
    loaded, mapping = load_sav(*files, MAPPING)
    valid = tuple(d for d in loaded.diaries if validate_diary(d).valid and not d.metadata["summary_mismatch"])
    old = read_json(source_dir / "dataset_manifest.json")
    if len(valid) != old["valid_diaries"] or loaded.raw_episode_rows != old["raw_rows"]["episode"]:
        raise ValueError("regenerated diary identity/count differs from B1.1")
    corpus_ids = {json.loads(line)["day_id"] for line in (source_dir / "behavior_days.jsonl").open(encoding="utf-8")}
    if corpus_ids != {d.day_id for d in valid}:
        raise ValueError("B1.1 canonical corpus and raw diaries disagree")
    return valid, mapping


def _prior_candidates(days, domains, coverage):
    starts: dict[str, Counter[int]] = {activity: Counter() for activity in (*CORE5, *DOMAIN_ORDER)}
    start_minutes: dict[str, list[int]] = {activity: [] for activity in starts}
    transitions = coverage["transition_counts"]
    for diary in days:
        for episode in merged_shadow(diary, domains):
            if episode.activity in starts:
                starts[episode.activity][episode.start_minute // 30] += 1
                start_minutes[episode.activity].append(episode.start_minute)
    time_priors = {}
    for activity, bins in starts.items():
        top = sorted(bins.items(), key=lambda item: (-item[1], item[0]))[:3]
        circular_sleep = activity == "SLEEP"
        time_priors[activity] = {"top_3_30_minute_bins": [{"clock_start_minute": index * 30, "count": count} for index, count in top],
                                 "median_start_minute": None if circular_sleep else percentile(start_minutes[activity], .5),
                                 "start_iqr": None if circular_sleep else [percentile(start_minutes[activity], .25), percentile(start_minutes[activity], .75)],
                                 "reason": "SLEEP crosses midnight; no linear quantiles." if circular_sleep else "Linear clock quantiles are descriptive; inspect multimodal peaks too."}
    outgoing = Counter()
    for (left, _), count in transitions.items():
        outgoing[left] += count
    transition_priors = {}
    for activity in (*CORE5, *DOMAIN_ORDER, "OTHER"):
        top = sorted(((right, count) for (left, right), count in transitions.items() if left == activity), key=lambda pair: (-pair[1], pair[0]))[:3]
        transition_priors[activity] = [{"next_activity": right, "count": count, "probability": round(count / outgoing[activity], 6)} for right, count in top]
    return time_priors, transition_priors


def _serialize_coverage(value: dict[str, object]) -> dict[str, object]:
    return {key: round(val, 9) if isinstance(val, float) else val for key, val in value.items() if key not in ("transition_counts", "remaining_codes")}


def build(source_dir: Path = DEFAULT_INPUT, output: Path = DEFAULT_OUTPUT, profile_path: Path = DEFAULT_PROFILE, data_root: Path = DATA_ROOT) -> dict[str, object]:
    if profile_path.resolve() != DEFAULT_PROFILE.resolve() and profile_path.parent.name != "experimental":
        raise ValueError("profile must be placed under an experimental/ directory")
    protected = {path: file_sha256(path) for path in PRODUCTION_FILES}
    from social_sim.decision.models import ActionType
    actions_before = tuple(action.value for action in ActionType)
    source, checksums = verified_inputs(source_dir)
    diaries, mapping = load_verified_diaries(source_dir, data_root, source)
    subsets = {"all_adults": diaries, "employed_adults": tuple(d for d in diaries if d.metadata["employment_status"] in (1, 2)),
               "employed_weekday_adults": tuple(d for d in diaries if d.metadata["employment_status"] in (1, 2) and d.metadata["weekday"])}
    choices = ((), ("PERSONAL_CARE",), ("CHORES",), DOMAIN_ORDER)
    measured = {subgroup: {choice: measure(days, choice) for choice in choices} for subgroup, days in subsets.items()}
    source_coverage = read_json(source_dir / "mapping_coverage.json")
    for subgroup, mapped_name in (("all_adults", "all_adults"), ("employed_adults", "employed_adults"), ("employed_weekday_adults", "employed_weekday")):
        validate_coverage(measured[subgroup][()], measured[subgroup][DOMAIN_ORDER], source_coverage[mapped_name])
    audit = {int(row["source_code"]): row for row in csv.DictReader((source_dir / "mapping_audit.csv").open(encoding="utf-8", newline=""))}
    if set(SOURCE_BY_CODE) & {code for code, row in audit.items() if row["canonical_mapping"] != "OTHER"}:
        raise ValueError("new domain overlaps Core5 mapping")
    mapped_rows = []
    for source_category in SOURCE_CATEGORIES:
        row = audit[source_category.code]
        if row["source_label"] != source_category.label:
            raise ValueError(f"source category label drift: {source_category.code}")
        mapped_rows.append({"raw_code": source_category.code, "raw_label": source_category.label, "total_minutes": row["total_minutes"],
                            "episode_count": row["episode_count"], "candidate_domain": source_category.domain,
                            "confidence": source_category.confidence, "rationale": source_category.rationale})
    rows = []
    for subgroup, variants in measured.items():
        for domains, value in variants.items():
            rows.append({"subgroup": subgroup, "ontology_name": "Core5" if not domains else "Core7" if len(domains) == 2 else f"Core5+{domains[0]}",
                         "category_count": 5 + len(domains), "episode_coverage": round(value["episode_coverage"], 9),
                         "minute_coverage": round(value["minute_coverage"], 9), "transition_coverage": round(value["transition_coverage"], 9),
                         "OTHER_remaining_minutes": value["OTHER_remaining_minutes"]})
    core7 = measured["all_adults"][DOMAIN_ORDER]
    other_rows = [{"raw_code": code, "raw_label": mapping.actual_labels.get(code, "Unknown"), "total_minutes": minutes,
                   "share_of_valid_adult_minutes": round(minutes / core7["minutes"], 9)} for code, minutes in core7["remaining_codes"].most_common(20)]
    weekday_stats = duration_stats(subsets["employed_weekday_adults"], DOMAIN_ORDER)
    comparison = comparisons(weekday_stats)
    indexed = {row.activity: row for row in comparison}
    counterfactual = decision_frequency_counterfactual(indexed)
    time_priors, transition_priors = _prior_candidates(subsets["employed_weekday_adults"], DOMAIN_ORDER, measured["employed_weekday_adults"][DOMAIN_ORDER])
    # A major gap is defined prospectively as any explicit, *unmapped* source
    # activity domain occupying >=5% of all valid adult minutes. Inspect the
    # remaining categories and report the largest domain without adding it.
    residual_domains = {"SHOPPING": tuple(range(26, 33)), "CARE_GIVING": tuple(range(33, 41)),
                        "EDUCATION": tuple(range(16, 20)), "VOLUNTEERING_RELIGION": tuple(range(41, 50))}
    residual = {name: sum(core7["remaining_codes"][code] for code in codes) / core7["minutes"] for name, codes in residual_domains.items()}
    largest = max(residual, key=residual.get)
    gap = f"MAJOR_GAP:{largest}" if residual[largest] >= .05 else "NO_MAJOR_GAP"
    selected_all = select_minimal_ontology({choice: measured["all_adults"][choice]["minute_coverage"] for choice in choices})
    selected_worker = select_minimal_ontology({choice: measured["employed_weekday_adults"][choice]["minute_coverage"] for choice in choices})
    status = recommendation(core7["minute_coverage"], measured["employed_weekday_adults"][DOMAIN_ORDER]["minute_coverage"], gap != "NO_MAJOR_GAP", all(row.recommended_candidate is not None for row in comparison))
    candidates = []
    for domain in DOMAIN_ORDER:
        gain = measured["all_adults"][(domain,)]
        candidates.append(asdict(BehaviorDomainCandidate(domain, tuple(s.code for s in SOURCE_CATEGORIES if s.domain == domain),
                        gain["minute_coverage"] - measured["all_adults"][()]["minute_coverage"],
                        gain["episode_coverage"] - measured["all_adults"][()]["episode_coverage"],
                        gain["minute_coverage"], gain["episode_coverage"], "high_and_medium_exact_code",
                        "Explicit source categories, no inference from labels or ActionType modification", status == "RECOMMENDED_FOR_NEXT_EXPERIMENT")))
    profile = {"profile_name": CALIBRATION_VERSION, "version": 1,
               "source": {"dataset": "NHAPS_AHTUS_1992_94", "survey_years": "1992-1994", "archive_sha256": source["archive_sha256"], "subgroup": "employed_weekday_adults"},
               "ontology": {"version": ONTOLOGY_VERSION, "status": "EXPERIMENTAL", "activities": [*CORE5, *DOMAIN_ORDER], "selected_minimal_all_adults": list(selected_all) if selected_all is not None else None,
                            "selected_minimal_employed_weekday": list(selected_worker) if selected_worker is not None else None},
               "coverage": {name: _serialize_coverage(values[DOMAIN_ORDER]) for name, values in measured.items()},
               "duration_candidates": {row.activity: row.recommended_candidate for row in comparison},
               "duration_semantics": {"SLEEP": "session placeholder pending overnight redesign", "EAT": "future occupancy only", "MOVE": "future travel occupancy only", "others": "experimental merged-episode median"},
               "time_prior_status": "DESCRIPTIVE_ONLY_NOT_IN_PROMPT", "transition_prior_status": "DESCRIPTIVE_ONLY_NOT_IN_PROMPT", "recommendation": status,
               "target_minute_coverage": TARGET_MINUTE_COVERAGE, "production_config_modified": False, "LLM_calls": 0}
    validate_profile(profile, source["archive_sha256"], status)
    # Preflight output destinations before *any* write; B1.1 stays untouched.
    output_resolved = output.resolve()
    if source_dir.resolve() == output_resolved or profile_path.resolve() in PRODUCTION_FILES:
        raise ValueError("output would overwrite input or production configuration")
    if output_resolved.is_relative_to(ROOT) and not output_resolved.is_relative_to((ROOT / "run/calibration").resolve()):
        raise ValueError("repository-local calibration output must stay under run/calibration/")
    if profile_path.resolve().is_relative_to(ROOT) and not profile_path.resolve().is_relative_to((ROOT / "config/experimental").resolve()):
        raise ValueError("repository-local profile must stay under config/experimental/")
    output.mkdir(parents=True, exist_ok=True)
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    write_csv(output / "ontology_coverage.csv", list(rows[0]), rows)
    write_csv(output / "ontology_mapping_audit.csv", list(mapped_rows[0]), mapped_rows)
    write_csv(output / "remaining_other_categories.csv", list(other_rows[0]), other_rows)
    write_csv(output / "duration_comparison.csv", list(as_rows(comparison)[0]), as_rows(comparison))
    write_json(output / "duration_candidates.json", {"source_subgroup": "employed_weekday_adults", "shadow_core7": weekday_stats, "comparisons": as_rows(comparison)})
    write_json(output / "time_prior_candidates.json", {"subgroup": "employed_weekday_adults", "ontology": "Core7", "clock": "midnight-to-midnight", "priors": time_priors})
    write_json(output / "transition_prior_candidates.json", {"subgroup": "employed_weekday_adults", "ontology": "Core7", "merge": "recomputed from raw episode sequence", "priors": transition_priors})
    write_json(output / "counterfactual_decision_frequency.json", counterfactual)
    write_json(output / "domain_candidates.json", candidates)
    write_json(output / "remaining_domain_shares.json", {"domain_shares": residual, "major_gap_rule": "single explicit residual domain >=5% of all adult minutes", "result": gap})
    old_samples = read_json(source_dir / "nested_sample_ids.json")
    seed = int(old_samples["seed"])
    corpus = BehaviorCorpus([BehaviorDay(d.day_id, (), d.metadata) for d in diaries])
    ids = [day.day_id for day in corpus.sample_days(len(corpus), seed)]
    if ids != old_samples["samples"]["BALL"]:
        raise ValueError("candidate corpus sample order differs from B1.1")
    write_json(output / "nested_sample_ids.json", {"seed": seed, "samples": {"B100": ids[:100], "B1000": ids[:1000], "BALL": ids}})
    with (output / "behavior_days_core7_candidate.jsonl").open("w", encoding="utf-8") as stream:
        for diary in diaries:
            sequence = merged_shadow(diary, DOMAIN_ORDER)
            stream.write(json.dumps({"day_id": diary.day_id, "ontology_status": "EXPERIMENTAL", "source_archive_sha256": source["archive_sha256"],
                                     "canonical_sequence": ">".join(ep.activity for ep in sequence), "episodes": [asdict(ep) | {"duration_minutes": ep.duration_minutes} for ep in sequence],
                                     "metadata": diary.metadata}, ensure_ascii=False) + "\n")
    profile_header = "# EXPERIMENTAL CALIBRATION PROFILE\n# NOT PRODUCTION DEFAULT\n# NHAPS/AHTUS 1992–94 US ADULT PILOT\n"
    profile_path.write_text(profile_header + yaml.safe_dump(profile, sort_keys=False, allow_unicode=True), encoding="utf-8")
    gain = (core7["minute_coverage"] - measured["all_adults"][()]["minute_coverage"]) * 100
    text = ["# Neutral-Day calibration v1 (experimental)", "", f"Source ZIP SHA256: `{source['archive_sha256']}`.",
            f"All adult Core5 → Core7 minute coverage: {measured['all_adults'][()]['minute_coverage']:.2%} → {core7['minute_coverage']:.2%} (+{gain:.2f} percentage points); target {TARGET_MINUTE_COVERAGE:.0%}.",
            f"Employed-weekday Core7 minute coverage: {measured['employed_weekday_adults'][DOMAIN_ORDER]['minute_coverage']:.2%}.",
            f"Selected minimal all-adult additions: {selected_all}; employed-weekday additions: {selected_worker}.",
            f"Residual domain check: {gap}; profile {status}.",
            f"Synthetic 18h replay: {counterfactual['current_profile_estimated_decisions_per_day']} → {counterfactual['calibrated_profile_estimated_decisions_per_day']} estimated decisions, reduction {counterfactual['estimated_decision_reduction']}.",
            "", "Idle warning: missing common actions can create artificial idle even with a capable model.",
            "Duration warning: short sessions mechanically increase DecisionTrigger frequency; this replay is not a model-quality or API-call estimate.",
            "No production rules, ActionType, default durations, LLM, retrieval, or B1.1 artifacts were changed."]
    (output / "summary.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    validate_unchanged(protected)
    if tuple(action.value for action in ActionType) != actions_before or "PERSONAL_CARE" in actions_before or "CHORES" in actions_before:
        raise ValueError("production ActionType changed")
    manifest = {"source_archive_sha256": source["archive_sha256"], "source_dataset": "NHAPS_AHTUS_1992_94", "subgroup": "employed_weekday_adults",
                "source_artifact_checksums": checksums, "calibration_version": CALIBRATION_VERSION, "ontology_version": ONTOLOGY_VERSION,
                "ontology_status": "EXPERIMENTAL", "target_coverage": TARGET_MINUTE_COVERAGE, "recommendation": status,
                "production_config_modified": False, "LLM_calls": 0,
                "candidate_profile": {"path": str(profile_path.relative_to(ROOT)) if profile_path.is_relative_to(ROOT) else str(profile_path), "sha256": file_sha256(profile_path)},
                "output_artifacts": {path.name: file_sha256(path) for path in sorted(output.iterdir()) if path.is_file() and path.name != "calibration_manifest.json"}}
    write_json(output / "calibration_manifest.json", manifest)
    return {"source_archive_sha256": source["archive_sha256"], "coverage": {name: {("Core5" if not domains else "Core7" if len(domains) == 2 else f"Core5+{domains[0]}"): _serialize_coverage(value) for domains, value in values.items()} for name, values in measured.items()},
            "selected_minimal_all_adults": selected_all, "selected_minimal_employed_weekday": selected_worker, "gap": gap, "recommendation": status,
            "durations": as_rows(comparison), "counterfactual": counterfactual, "remaining_top20": other_rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--data-root", type=Path, default=DATA_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        source, _ = verified_inputs(args.input)
        print(json.dumps({"dry_run": True, "source_dataset": source["dataset"], "source_archive_sha256": source["archive_sha256"],
                          "subgroup": "employed_weekday_adults", "candidate_domains": list(DOMAIN_ORDER),
                          "target_minute_coverage": TARGET_MINUTE_COVERAGE, "output": str(args.output), "profile": str(args.profile)}, indent=2))
        return
    result = build(args.input, args.output, args.profile, args.data_root)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
