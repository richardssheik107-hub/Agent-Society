"""Day-level held-out split and deterministic empirical action scoring."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass

from social_sim.behavior_prior.index import BehaviorPriorIndex, load_nested_worker_corpora
from social_sim.behavior_prior.models import CORE7, SAMPLING_SEED
from social_sim.behavior_prior.query import PriorQuery


def _id_hash(ids: list[str]) -> str:
    return hashlib.sha256("\n".join(ids).encode("utf-8")).hexdigest()


def split_worker_diaries() -> tuple[dict[str, tuple[dict[str, object], ...]],
                                     tuple[dict[str, object], ...], dict[str, object]]:
    """Split unique workers by day ID, then take nested train-only prefixes."""
    existing, source = load_nested_worker_corpora()
    workers = {day["day_id"]: day for day in existing["BALL"]}
    ids = sorted(workers)
    random.Random(SAMPLING_SEED).shuffle(ids)
    train_ids, eval_ids = ids[:2572], ids[2572:]
    if len(train_ids) != 2572 or len(eval_ids) != 643 or set(train_ids) & set(eval_ids):
        raise ValueError("TRAIN_EVAL_DAY_LEAKAGE")
    sample_ids = sorted(train_ids)
    random.Random(SAMPLING_SEED).shuffle(sample_ids)
    corpora = {
        "B100": tuple(workers[day_id] for day_id in sample_ids[:100]),
        "B1000": tuple(workers[day_id] for day_id in sample_ids[:1000]),
        "BTRAIN_ALL": tuple(workers[day_id] for day_id in sample_ids),
    }
    train_set, eval_set = set(train_ids), set(eval_ids)
    if not (set(sample_ids[:100]) < set(sample_ids[:1000]) < train_set):
        raise ValueError("TRAIN_CORPUS_NOT_NESTED")
    if any(day["day_id"] in eval_set for corpus in corpora.values() for day in corpus):
        raise ValueError("EVAL_DAY_IN_RETRIEVAL")
    split = {
        "seed": SAMPLING_SEED, "method": "sorted_day_ids_then_random.Random(seed).shuffle",
        "train_fraction": 0.8, "train_count": len(train_ids), "eval_count": len(eval_ids),
        "train_day_id_hash": _id_hash(sorted(train_ids)),
        "eval_day_id_hash": _id_hash(sorted(eval_ids)),
        "train_sample_hashes": {name: _id_hash([day["day_id"] for day in corpus])
                                for name, corpus in corpora.items()},
        "source_sha256": source["source_sha256"],
        "source_all_adult_diaries": source["source_all_adult_diaries"],
        "eligible_employed_weekday_diaries": source["eligible_employed_weekday_diaries"],
        "overlap_count": 0,
    }
    split["split_hash"] = hashlib.sha256(json.dumps(
        {"seed": SAMPLING_SEED, "train": sorted(train_ids), "eval": sorted(eval_ids)},
        separators=(",", ":"), sort_keys=True,
    ).encode()).hexdigest()
    return corpora, tuple(workers[day_id] for day_id in eval_ids), split


@dataclass(frozen=True)
class HeldoutDistribution:
    fallback_level: str
    support_count: int
    other_mass: float
    counts: dict[str, int]

    def score(self, action: str) -> dict[str, object]:
        if action not in CORE7:
            raise ValueError("held-out action must be Core7")
        ranked = sorted((name for name in CORE7 if self.counts.get(name, 0) > 0),
                        key=lambda name: (-self.counts[name], name))
        return {
            "heldout_action_share": self.counts.get(action, 0) / self.support_count,
            "heldout_rank": ranked.index(action) + 1 if action in ranked else None,
            "heldout_top1_match": bool(ranked and action == ranked[0]),
            "heldout_top3_match": action in ranked[:3],
        }


class HeldoutScorer:
    """Never accepts a train index; builds fallback counts only from EVAL days."""

    def __init__(self, eval_days: tuple[dict[str, object], ...]) -> None:
        if len(eval_days) != 643 or len({day["day_id"] for day in eval_days}) != 643:
            raise ValueError("EVAL_POOL_SIZE_OR_DUPLICATE")
        self.index = BehaviorPriorIndex.build(eval_days)

    def distribution(self, query: PriorQuery) -> HeldoutDistribution:
        level, counts = self.index._source(query)
        support = sum(counts.values())
        if support <= 0:
            raise ValueError("EMPTY_EVAL_FALLBACK")
        return HeldoutDistribution(level, support, counts["OTHER"] / support,
                                   {name: counts[name] for name in (*CORE7, "OTHER")})
