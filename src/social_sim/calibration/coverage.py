"""Coverage and sequence statistics of the shadow ontology."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from social_sim.human_data.models import HumanDayDiary

from .ontology import classify


@dataclass(frozen=True)
class ShadowEpisode:
    activity: str
    start_minute: int
    end_minute: int
    raw_codes: tuple[int, ...]

    @property
    def duration_minutes(self) -> int:
        return self.end_minute - self.start_minute


def raw_shadow(diary: HumanDayDiary, domains: tuple[str, ...]) -> tuple[ShadowEpisode, ...]:
    return tuple(ShadowEpisode(classify(int(ep.raw_activity_code), ep.canonical_activity.value, domains), ep.start_minute, ep.end_minute, (int(ep.raw_activity_code),)) for ep in diary.episodes)


def merged_shadow(diary: HumanDayDiary, domains: tuple[str, ...]) -> tuple[ShadowEpisode, ...]:
    merged: list[ShadowEpisode] = []
    for ep in raw_shadow(diary, domains):
        if merged and merged[-1].activity == ep.activity and merged[-1].end_minute == ep.start_minute:
            prev = merged[-1]
            merged[-1] = ShadowEpisode(prev.activity, prev.start_minute, ep.end_minute, prev.raw_codes + ep.raw_codes)
        else:
            merged.append(ep)
    return tuple(merged)


def measure(diaries: tuple[HumanDayDiary, ...], domains: tuple[str, ...]) -> dict[str, object]:
    raw_total = raw_covered = minutes_total = minutes_covered = transitions_total = transitions_covered = 0
    transitions: Counter[tuple[str, str]] = Counter()
    remaining: Counter[int] = Counter()
    for diary in diaries:
        raw = raw_shadow(diary, domains)
        raw_total += len(raw)
        minutes_total += diary.total_minutes
        for ep in raw:
            if ep.activity == "OTHER":
                remaining[ep.raw_codes[0]] += ep.duration_minutes
            else:
                raw_covered += 1
                minutes_covered += ep.duration_minutes
        merged = merged_shadow(diary, domains)
        for first, second in zip(merged, merged[1:]):
            transitions_total += 1
            transitions[(first.activity, second.activity)] += 1
            if first.activity != "OTHER" and second.activity != "OTHER":
                transitions_covered += 1
    return {
        "episodes": raw_total, "covered_episodes": raw_covered,
        "episode_coverage": raw_covered / raw_total if raw_total else 0.0,
        "minutes": minutes_total, "covered_minutes": minutes_covered,
        "minute_coverage": minutes_covered / minutes_total if minutes_total else 0.0,
        "OTHER_remaining_minutes": minutes_total - minutes_covered,
        "transitions": transitions_total, "covered_transitions": transitions_covered,
        "transition_coverage": transitions_covered / transitions_total if transitions_total else 0.0,
        "transition_counts": transitions, "remaining_codes": remaining,
    }
