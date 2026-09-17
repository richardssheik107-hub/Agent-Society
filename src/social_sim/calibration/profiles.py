"""Experimental profile recommendation without runtime side effects."""

from __future__ import annotations

from .ontology import TARGET_MINUTE_COVERAGE


def recommendation(all_coverage: float, weekday_coverage: float, remaining_major_gap: bool, interpretable_durations: bool) -> str:
    if all_coverage < TARGET_MINUTE_COVERAGE or weekday_coverage < TARGET_MINUTE_COVERAGE or remaining_major_gap or not interpretable_durations:
        return "NOT_READY"
    return "RECOMMENDED_FOR_NEXT_EXPERIMENT"
