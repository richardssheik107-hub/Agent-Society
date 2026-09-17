"""NHAPS 1992–94 harmonized AHTUS diary adapter; no simulator dependency."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import yaml

from .models import HumanActivityEpisode, HumanActivityType, HumanDayDiary


DATASET = "NHAPS_AHTUS_1992_94"
KEYS = ("survey", "wave", "hhid", "pid")
EPISODE_COLUMNS = (*KEYS, "epnum", "start", "end", "time", "main", "diaryday", "month", "year", "eloc", "mtrav", "recwght", "lowqual", "baddem")
BACKGROUND_COLUMNS = (*KEYS, "age", "empstat")
SUMMARY_COLUMNS = (*KEYS, "tottime", "numep", "tmiss", "recwght")


def _integer(value: object) -> int:
    if value is None or value != value or int(value) != value:
        raise ValueError(f"not a finite integer: {value!r}")
    return int(value)


def _key(row: dict[str, object]) -> tuple[int, int, int, int]:
    return tuple(_integer(row[column]) for column in KEYS)  # type: ignore[return-value]


class NhapsMapping:
    def __init__(self, path: Path, actual_labels: dict[int, str]) -> None:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.version = data["version"]
        self.rules: dict[int, dict[str, str]] = {}
        for rule in data["rules"]:
            code = int(rule["source_code"])
            if code in self.rules:
                raise ValueError(f"duplicate source_code {code}")
            if actual_labels.get(code) != rule["source_label"]:
                raise ValueError(f"metadata label mismatch for {code}: {actual_labels.get(code)!r}")
            if not rule.get("rationale") or rule.get("confidence") not in ("high", "medium"):
                raise ValueError(f"missing rationale/confidence for {code}")
            HumanActivityType(rule["canonical_activity"])
            self.rules[code] = rule
        self.actual_labels = actual_labels

    def classify(self, code: int) -> tuple[HumanActivityType, str]:
        rule = self.rules.get(code)
        return (HumanActivityType(rule["canonical_activity"]), self.actual_labels[code]) if rule else (HumanActivityType.OTHER, self.actual_labels.get(code, "Unmapped AHTUS activity"))


@dataclass(frozen=True)
class NhapsLoadResult:
    diaries: tuple[HumanDayDiary, ...]
    raw_background_rows: int
    raw_summary_rows: int
    raw_episode_rows: int
    raw_diarists: int
    minor_cases: int
    missing_age_cases: int
    unmatched_background: int
    unmatched_summary: int
    duplicate_keys: tuple[str, ...]
    parse_errors: tuple[tuple[str, str], ...]
    summary_mismatches: tuple[tuple[str, str], ...]


def load_rows(
    episodes: list[dict[str, object]],
    background: list[dict[str, object]],
    summaries: list[dict[str, object]],
    mapping: NhapsMapping,
) -> NhapsLoadResult:
    """Join official SURVEY/WAVE/HHID/PID; preserve invalid diaries for validation."""
    duplicate: list[str] = []

    def index(rows: list[dict[str, object]], name: str) -> dict[tuple[int, int, int, int], dict[str, object]]:
        found = {}
        for row in rows:
            key = _key(row)
            if key in found:
                duplicate.append(f"{name}:{key}")
            found[key] = row
        return found

    backgrounds = index(background, "background")
    summary_map = index(summaries, "summary")
    grouped: dict[tuple[int, int, int, int], list[dict[str, object]]] = defaultdict(list)
    for episode in episodes:
        grouped[_key(episode)].append(episode)
    if duplicate:
        raise ValueError(f"duplicate person/diary merge keys: {duplicate[:5]}")
    diaries: list[HumanDayDiary] = []
    errors: list[tuple[str, str]] = []
    mismatches: list[tuple[str, str]] = []
    minors = missing_age = unmatched_background = unmatched_summary = 0
    for key, rows in sorted(grouped.items()):
        identifier = ":".join(map(str, key))
        day_id = f"nhaps1992_94:{identifier}"
        bg = backgrounds.get(key)
        summary = summary_map.get(key)
        if bg is None:
            unmatched_background += 1
            continue
        if summary is None:
            unmatched_summary += 1
            continue
        try:
            age = _integer(bg["age"])
        except ValueError:
            missing_age += 1
            continue
        if age in (-8, 999):  # Official SPSS labels: missing/dirty or DK-refusal.
            missing_age += 1
            continue
        if age < 18:
            minors += 1
            continue
        try:
            ordered = sorted(rows, key=lambda row: _integer(row["epnum"]))
            built = []
            main_totals: Counter[int] = Counter()
            for row in ordered:
                code = _integer(row["main"])
                start, end, duration = (_integer(row[field]) for field in ("start", "end", "time"))
                canonical, label = mapping.classify(code)
                built.append(HumanActivityEpisode(identifier, day_id, _integer(row["epnum"]), start, end, duration, str(code), label, canonical, str(_integer(row["eloc"])), DATASET))
                main_totals[code] += duration
            issues = []
            total = sum(ep.duration_minutes for ep in built)
            if total != _integer(summary["tottime"]):
                issues.append(f"episode_total={total},summary_tottime={summary['tottime']}")
            if len(built) != _integer(summary["numep"]):
                issues.append("numep_mismatch")
            for code, minutes in main_totals.items():
                field = f"tmain{code}"
                if field in summary and minutes != _integer(summary[field]):
                    issues.append(f"{field}_mismatch")
            if issues:
                mismatches.append((day_id, ";".join(issues[:10])))
            weekday_code = _integer(rows[0]["diaryday"])
            weight = float(summary["recwght"])
            diaries.append(HumanDayDiary(identifier, day_id, tuple(built), total, {
                "age": age, "employment_status": _integer(bg["empstat"]),
                "weekday_code": weekday_code, "weekday": weekday_code in (2, 3, 4, 5, 6),
                "month": _integer(rows[0]["month"]), "year": _integer(rows[0]["year"]),
                "recwght": weight, "lowqual": _integer(rows[0]["lowqual"]),
                "baddem": _integer(rows[0]["baddem"]), "diary_start_clock_minute": 0,
                "summary_mismatch": bool(issues),
            }))
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            errors.append((day_id, f"parse_error:{type(error).__name__}:{error}"))
    return NhapsLoadResult(tuple(diaries), len(background), len(summaries), len(episodes), len(grouped), minors, missing_age, unmatched_background, unmatched_summary, tuple(duplicate), tuple(errors), tuple(mismatches))


def load_sav(background: Path, summary: Path, episode: Path, mapping_path: Path) -> tuple[NhapsLoadResult, NhapsMapping]:
    import pyreadstat  # Integration-only dependency, not required for unit tests.

    frames = []
    metadata = None
    for path, columns in ((background, BACKGROUND_COLUMNS), (summary, SUMMARY_COLUMNS), (episode, EPISODE_COLUMNS)):
        frame, meta = pyreadstat.read_sav(str(path), usecols=None if path == summary else list(columns), apply_value_formats=False)
        if not set(columns).issubset(frame.columns):
            raise ValueError(f"{path.name}: missing {set(columns) - set(frame.columns)}")
        frames.append(frame.to_dict("records"))
        if path == episode:
            metadata = meta
    assert metadata is not None
    labels = {int(float(code)): label for code, label in metadata.variable_value_labels["main"].items()}
    mapping = NhapsMapping(mapping_path, labels)
    return load_rows(frames[2], frames[0], frames[1], mapping), mapping
