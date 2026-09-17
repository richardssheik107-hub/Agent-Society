"""ATUS 2025 single-year CSV/ZIP loader. Time axis starts at 04:00 diary day."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from io import TextIOWrapper
from pathlib import Path
from zipfile import ZipFile

from .mapping import ActivityMapping
from .models import HumanActivityEpisode, HumanDayDiary


REQUIRED_ACTIVITY = {"TUCASEID", "TUACTIVITY_N", "TUACTDUR24", "TUSTARTTIM", "TUSTOPTIME", "TUTIER1CODE", "TUTIER2CODE", "TUTIER3CODE", "TEWHERE"}
REQUIRED_RESPONDENT = {"TUCASEID", "TELFS", "TUDIARYDATE", "TUDIARYDAY"}
REQUIRED_ROSTER = {"TUCASEID", "TULINENO", "TEAGE"}
REQUIRED_WHO = {"TUCASEID", "TUACTIVITY_N", "TUWHO_CODE"}


def _reader(path: Path):
    if path.suffix.lower() == ".zip":
        archive = ZipFile(path)
        candidates = [name for name in archive.namelist() if name.lower().endswith((".dat", ".csv")) and not name.startswith("__MACOSX")]
        if len(candidates) != 1:
            archive.close()
            raise ValueError(f"expected one CSV-like member in {path}: {candidates}")
        stream = TextIOWrapper(archive.open(candidates[0]), encoding="utf-8-sig", newline="")
        return archive, stream, csv.DictReader(stream)
    stream = path.open(encoding="utf-8-sig", newline="")
    return None, stream, csv.DictReader(stream)


def _rows(path: Path, required: set[str]):
    archive, stream, reader = _reader(path)
    try:
        fields = set(reader.fieldnames or [])
        missing = required - fields
        if missing:
            raise ValueError(f"{path.name}: missing columns {sorted(missing)}; actual {sorted(fields)}")
        yield from reader
    finally:
        stream.close()
        if archive:
            archive.close()


def inspect_schema(path: Path) -> list[str]:
    archive, stream, reader = _reader(path)
    try:
        return reader.fieldnames or []
    finally:
        stream.close()
        if archive:
            archive.close()


def _clock_minutes(value: str) -> int:
    parts = value.split(":")
    if len(parts) != 3:
        raise ValueError(f"invalid ATUS time {value!r}")
    hour, minute, second = map(int, parts)
    if hour == 24 and minute == 0 and second == 0:
        return 0
    if not (0 <= hour < 24 and 0 <= minute < 60 and second == 0):
        raise ValueError(f"invalid ATUS time {value!r}")
    return hour * 60 + minute


def _matches_clock(elapsed: int, clock: str) -> bool:
    return (240 + elapsed) % 1440 == _clock_minutes(clock)


@dataclass(frozen=True)
class AtusLoadResult:
    diaries: tuple[HumanDayDiary, ...]
    activity_rows: int
    respondent_rows: int
    roster_rows: int
    unique_activity_cases: int
    minor_cases: int
    unmatched_activity_cases: int
    parse_errors: tuple[tuple[str, str], ...]


def load_atus_activity(activity_path: Path, respondent_path: Path, roster_path: Path, mapping: ActivityMapping) -> AtusLoadResult:
    respondents = {row["TUCASEID"]: row for row in _rows(respondent_path, REQUIRED_RESPONDENT)}
    roster_rows = 0
    ages: dict[str, int] = {}
    for row in _rows(roster_path, REQUIRED_ROSTER):
        roster_rows += 1
        if row["TULINENO"].strip() == "1":
            ages[row["TUCASEID"]] = int(row["TEAGE"])
    grouped: dict[str, list[dict[str, str]]] = {}
    activity_rows = 0
    for row in _rows(activity_path, REQUIRED_ACTIVITY):
        activity_rows += 1
        grouped.setdefault(row["TUCASEID"], []).append(row)
    diaries: list[HumanDayDiary] = []
    unmatched = 0
    minors = 0
    parse_errors: list[tuple[str, str]] = []
    for caseid, rows in grouped.items():
        respondent = respondents.get(caseid)
        age = ages.get(caseid)
        if respondent is None or age is None:
            unmatched += 1
            continue
        if age < 18:
            minors += 1
            continue
        day_id = f"atus2025:{caseid}:{respondent['TUDIARYDATE']}"
        episodes: list[HumanActivityEpisode] = []
        elapsed = 0
        clock_errors = 0
        ordered_rows = sorted(rows, key=lambda item: int(item["TUACTIVITY_N"]))
        try:
            for row_number, row in enumerate(ordered_rows):
                duration = int(row["TUACTDUR24"])
                code = "".join(row[key].strip().zfill(2) for key in ("TUTIER1CODE", "TUTIER2CODE", "TUTIER3CODE"))
                canonical, label = mapping.classify(code)
                # TUACTDUR24 truncates the final activity at 04:00; its raw stop clock can be later.
                if not _matches_clock(elapsed, row["TUSTARTTIM"]) or (row_number < len(ordered_rows) - 1 and not _matches_clock(elapsed + duration, row["TUSTOPTIME"])):
                    clock_errors += 1
                episodes.append(HumanActivityEpisode(person_id=caseid, day_id=day_id, episode_index=int(row["TUACTIVITY_N"]), start_minute=elapsed, end_minute=elapsed + duration, duration_minutes=duration, raw_activity_code=code, raw_activity_label=label, canonical_activity=canonical, location_raw=row["TEWHERE"].strip() or None, source_dataset="ATUS_2025"))
                elapsed += duration
        except (ValueError, KeyError) as error:
            parse_errors.append((day_id, f"parse_error:{type(error).__name__}:{error}"))
            continue
        weekday_code = int(respondent["TUDIARYDAY"])
        diaries.append(HumanDayDiary(person_id=caseid, day_id=day_id, episodes=tuple(episodes), total_minutes=elapsed, metadata={"age": age, "employment_status": respondent["TELFS"], "diary_date": respondent["TUDIARYDATE"], "weekday_code": weekday_code, "weekday": weekday_code in (2, 3, 4, 5, 6), "clock_mismatch_count": clock_errors}))
    return AtusLoadResult(tuple(diaries), activity_rows, len(respondents), roster_rows, len(grouped), minors, unmatched, tuple(parse_errors))
