"""Independent time-use ontology and deterministic corpus sampling."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
import random


class HumanActivityType(str, Enum):
    SLEEP = "SLEEP"
    WORK = "WORK"
    EAT = "EAT"
    LEISURE = "LEISURE"
    MOVE = "MOVE"
    OTHER = "OTHER"


@dataclass(frozen=True)
class HumanActivityEpisode:
    person_id: str
    day_id: str
    episode_index: int
    start_minute: int
    end_minute: int
    duration_minutes: int
    raw_activity_code: str
    raw_activity_label: str
    canonical_activity: HumanActivityType
    location_raw: str | None
    source_dataset: str

    def __post_init__(self) -> None:
        if self.duration_minutes <= 0 or self.end_minute <= self.start_minute:
            raise ValueError("episode duration must be positive")
        if self.end_minute - self.start_minute != self.duration_minutes:
            raise ValueError("episode clock span and duration disagree")
        if self.episode_index < 1 or self.start_minute < 0:
            raise ValueError("invalid episode index or start")


@dataclass(frozen=True)
class HumanDayDiary:
    person_id: str
    day_id: str
    episodes: tuple[HumanActivityEpisode, ...]
    total_minutes: int
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class BehaviorDay:
    day_id: str
    canonical_episodes: tuple[HumanActivityEpisode, ...]
    metadata: dict[str, object] = field(default_factory=dict)


class BehaviorCorpus:
    def __init__(self, days: list[BehaviorDay] | tuple[BehaviorDay, ...]) -> None:
        self._days = {day.day_id: day for day in days}
        if len(self._days) != len(days):
            raise ValueError("duplicate day_id")

    def __len__(self) -> int:
        return len(self._days)

    def get_day(self, day_id: str) -> BehaviorDay:
        return self._days[day_id]

    def sample_days(self, n: int, seed: int) -> tuple[BehaviorDay, ...]:
        if n < 0 or n > len(self):
            raise ValueError("sample size out of range; oversampling is forbidden")
        ids = sorted(self._days)
        random.Random(seed).shuffle(ids)
        return tuple(self._days[day_id] for day_id in ids[:n])


def merge_adjacent_same_activity(episodes: tuple[HumanActivityEpisode, ...]) -> tuple[HumanActivityEpisode, ...]:
    """Merge contiguous canonical episodes; retain raw episodes separately."""
    merged: list[HumanActivityEpisode] = []
    for episode in episodes:
        if merged and merged[-1].canonical_activity == episode.canonical_activity and merged[-1].end_minute == episode.start_minute:
            previous = merged[-1]
            merged[-1] = replace(previous, end_minute=episode.end_minute, duration_minutes=previous.duration_minutes + episode.duration_minutes, raw_activity_code="MULTIPLE", raw_activity_label="Merged canonical episodes")
        else:
            merged.append(episode)
    return tuple(merged)
