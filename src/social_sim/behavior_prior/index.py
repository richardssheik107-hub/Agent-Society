"""Reproducible unweighted counts of observed Core7 episode onsets."""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from .models import BUCKET_COUNT, CORE7, MIN_SUPPORT_COUNT, SAMPLING_SEED, TICK_BUCKET_MINUTES
from .query import PriorQuery, PriorResult


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "run/calibration/neutral_day_v1/behavior_days_core7_candidate.jsonl"
SOURCE_MANIFEST = ROOT / "run/calibration/neutral_day_v1/calibration_manifest.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_nested_worker_corpora(source: Path = SOURCE) -> tuple[dict[str, tuple[dict[str, object], ...]], dict[str, object]]:
    """Apply B1.1's sorted-ID + Random(2025).shuffle sampling to the worker subset."""
    manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    source_hash = _sha256(source)
    if source_hash != manifest["output_artifacts"][source.name]:
        raise ValueError("Core7 candidate source checksum mismatch")
    days = [json.loads(line) for line in source.open(encoding="utf-8")]
    if len(days) != 7341 or len({day["day_id"] for day in days}) != len(days):
        raise ValueError("Core7 source is not the frozen 7,341 unique diaries")
    workers = {day["day_id"]: day for day in days if day["metadata"]["employment_status"] in (1, 2)
               and day["metadata"]["weekday"] is True}
    if len(workers) != 3215:
        raise ValueError("employed-weekday corpus size changed")
    ids = sorted(workers)
    random.Random(SAMPLING_SEED).shuffle(ids)
    corpora = {name: tuple(workers[day_id] for day_id in ids[:size]) for name, size in (
        ("B100", 100), ("B1000", 1000), ("BALL", len(ids)),
    )}
    if not set(d["day_id"] for d in corpora["B100"]) < set(d["day_id"] for d in corpora["B1000"]) < set(workers):
        raise ValueError("nested corpus inclusion failed")
    info = {
        "source_path": str(source.relative_to(ROOT)), "source_sha256": source_hash,
        "source_all_adult_diaries": len(days), "eligible_employed_weekday_diaries": len(workers),
        "seed": SAMPLING_SEED,
        "sample_sizes": {name: len(corpus) for name, corpus in corpora.items()},
        "sample_id_hashes": {name: hashlib.sha256("\n".join(d["day_id"] for d in corpus).encode()).hexdigest()
                             for name, corpus in corpora.items()},
        "sampling_method": "sorted_id_then_random.Random(seed).shuffle_then_prefix",
    }
    return corpora, info


@dataclass
class BehaviorPriorIndex:
    corpus_size: int
    exact: dict[tuple[int, str | None], Counter[str]]
    by_bucket: dict[int, Counter[str]]
    global_counts: Counter[str]
    index_hash: str
    min_support_count: int = MIN_SUPPORT_COUNT

    @classmethod
    def build(cls, days: tuple[dict[str, object], ...], *, min_support_count: int = MIN_SUPPORT_COUNT) -> BehaviorPriorIndex:
        if not days or min_support_count not in (10, 20):
            raise ValueError("index requires days and support threshold 10 or 20")
        exact: dict[tuple[int, str | None], Counter[str]] = defaultdict(Counter)
        by_bucket: dict[int, Counter[str]] = defaultdict(Counter)
        global_counts: Counter[str] = Counter()
        seen: set[str] = set()
        for day in days:
            day_id = day["day_id"]
            if day_id in seen:
                raise ValueError("duplicate diary")
            seen.add(day_id)
            previous = None
            clock_offset = day["metadata"]["diary_start_clock_minute"]
            for episode in day["episodes"]:
                activity = episode["activity"]
                if activity not in (*CORE7, "OTHER"):
                    raise ValueError("non-Core7 activity in source")
                bucket = ((episode["start_minute"] + clock_offset) % 1440) // TICK_BUCKET_MINUTES
                exact[bucket, previous][activity] += 1
                by_bucket[bucket][activity] += 1
                global_counts[activity] += 1
                previous = activity if activity in CORE7 else None
        payload = {
            "ids": sorted(seen), "min_support_count": min_support_count,
            "counts": [(bucket, previous, sorted(counter.items()))
                       for (bucket, previous), counter in sorted(exact.items(), key=lambda pair: (pair[0][0], pair[0][1] or ""))],
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return cls(len(days), dict(exact), dict(by_bucket), global_counts, digest, min_support_count)

    def _source(self, query: PriorQuery) -> tuple[str, Counter[str]]:
        adjacent = Counter()
        for bucket in ((query.bucket - 1) % BUCKET_COUNT, query.bucket, (query.bucket + 1) % BUCKET_COUNT):
            adjacent.update(self.by_bucket.get(bucket, Counter()))
        options = (
            ("L0", self.exact.get((query.bucket, query.previous_activity), Counter())),
            ("L1", self.by_bucket.get(query.bucket, Counter())),
            ("L2", adjacent),
        )
        for level, counts in options:
            if sum(counts.values()) >= self.min_support_count and any(counts[action] for action in CORE7):
                return level, counts
        return "L3", self.global_counts

    def query(self, query: PriorQuery, *, limit: int) -> PriorResult:
        if limit not in (1, 3):
            raise ValueError("only R1 or R3 is allowed")
        level, counts = self._source(query)
        support = sum(counts.values())
        ranked = sorted(((action, counts[action]) for action in CORE7 if counts[action]),
                        key=lambda pair: (-pair[1], pair[0]))
        if not ranked:
            raise ValueError("no executable Core7 prior even after global fallback")
        return PriorResult(
            tuple(action for action, _ in ranked[:limit]), level, support,
            counts["OTHER"] / support if support else 0.0,
            query.bucket, query.previous_activity,
        )
