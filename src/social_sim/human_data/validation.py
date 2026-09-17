"""Explicit diary validation; rejected diaries never enter statistics."""

from __future__ import annotations

from dataclasses import dataclass

from .models import HumanDayDiary


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    reasons: tuple[str, ...]


def validate_diary(diary: HumanDayDiary, expected_minutes: int = 1440) -> ValidationResult:
    reasons: list[str] = []
    if not diary.episodes:
        reasons.append("empty_diary")
    if diary.total_minutes != sum(ep.duration_minutes for ep in diary.episodes):
        reasons.append("total_mismatch")
    if diary.total_minutes != expected_minutes:
        reasons.append("not_24_hours")
    if diary.metadata.get("clock_mismatch_count", 0):
        reasons.append("clock_mismatch")
    for index, ep in enumerate(diary.episodes):
        if ep.day_id != diary.day_id or ep.person_id != diary.person_id:
            reasons.append("identity_mismatch")
        if ep.episode_index != index + 1:
            reasons.append("episode_index")
        if index and ep.start_minute < diary.episodes[index - 1].end_minute:
            reasons.append("overlap")
        if index and ep.start_minute > diary.episodes[index - 1].end_minute:
            reasons.append("gap")
    if diary.episodes and (diary.episodes[0].start_minute != 0 or diary.episodes[-1].end_minute != expected_minutes):
        reasons.append("not_full_window")
    return ValidationResult(not reasons, tuple(dict.fromkeys(reasons)))
