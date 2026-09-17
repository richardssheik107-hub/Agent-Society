"""Descriptive, unweighted time-use summaries; no policy calibration side effects."""

from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean

from .models import HumanActivityType, HumanDayDiary, merge_adjacent_same_activity


CORE5 = tuple(kind for kind in HumanActivityType if kind != HumanActivityType.OTHER)


def percentile(values: list[int], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low = int(position)
    return round(ordered[low] + (ordered[min(low + 1, len(ordered) - 1)] - ordered[low]) * (position - low), 2)


def distribution(values: list[int], episode: bool = False) -> dict[str, float | int | None]:
    result: dict[str, float | int | None] = {"count": len(values), "mean": round(mean(values), 2) if values else None, "median": percentile(values, .5), "p25": percentile(values, .25), "p75": percentile(values, .75)}
    if episode:
        result.update(p90=percentile(values, .9), p95=percentile(values, .95))
    return result


def summarize(diaries: tuple[HumanDayDiary, ...]) -> dict[str, object]:
    duration: dict[str, list[int]] = defaultdict(list)
    daily: dict[str, list[int]] = defaultdict(list)
    starts: Counter[tuple[str, int]] = Counter()
    transitions: Counter[tuple[str, str]] = Counter()
    other: Counter[str] = Counter()
    other_labels: dict[str, str] = {}
    raw_counts: list[int] = []
    merged_counts: list[int] = []
    unique_counts: list[int] = []
    core_count = core_minutes = total_count = total_minutes = 0
    for diary in diaries:
        merged = merge_adjacent_same_activity(diary.episodes)
        raw_counts.append(len(diary.episodes))
        merged_counts.append(len(merged))
        unique_counts.append(len({ep.canonical_activity for ep in merged}))
        totals = Counter()
        for ep in diary.episodes:
            total_count += 1
            total_minutes += ep.duration_minutes
            totals[ep.canonical_activity.value] += ep.duration_minutes
            if ep.canonical_activity != HumanActivityType.OTHER:
                core_count += 1
                core_minutes += ep.duration_minutes
            else:
                other[ep.raw_activity_code] += ep.duration_minutes
                other_labels[ep.raw_activity_code] = ep.raw_activity_label
        for ep in merged:
            kind = ep.canonical_activity.value
            duration[kind].append(ep.duration_minutes)
            if ep.canonical_activity in CORE5:
                # ATUS starts at 04:00; NHAPS/AHTUS starts at midnight.
                clock_offset = int(diary.metadata.get("diary_start_clock_minute", 240))
                starts[(kind, ((clock_offset + ep.start_minute) % 1440) // 30)] += 1
        for left, right in zip(merged, merged[1:]):
            transitions[(left.canonical_activity.value, right.canonical_activity.value)] += 1
        for kind in HumanActivityType:
            daily[kind.value].append(totals[kind.value])
    return {
        "episode_duration": {kind.value: distribution(duration[kind.value], episode=True) for kind in HumanActivityType},
        "daily_duration": {kind.value: distribution(daily[kind.value]) for kind in HumanActivityType},
        "start_bins": starts,
        "transitions": transitions,
        "activity_counts": {"raw": distribution(raw_counts), "canonical_merged": distribution(merged_counts), "unique_canonical": distribution(unique_counts)},
        "coverage": {"total_episodes": total_count, "mapped_to_core_count": core_count, "mapped_to_core_ratio": round(core_count / total_count, 6) if total_count else None, "OTHER_count": total_count - core_count, "OTHER_ratio": round((total_count - core_count) / total_count, 6) if total_count else None, "total_minutes": total_minutes, "mapped_to_core_minutes": core_minutes, "mapped_to_core_minute_ratio": round(core_minutes / total_minutes, 6) if total_minutes else None, "OTHER_minutes": total_minutes - core_minutes},
        "other_top20": [{"code": code, "label": other_labels[code], "minutes": minutes} for code, minutes in other.most_common(20)],
        "raw_episode_count": total_count,
        "canonical_merged_episode_count": sum(merged_counts),
    }
