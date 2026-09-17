"""Frozen-worker corpus, nested samples, and aggregate retrieval."""

from __future__ import annotations

import pytest

from social_sim.behavior_prior.index import BehaviorPriorIndex, load_nested_worker_corpora
from social_sim.behavior_prior.models import CORE7
from social_sim.behavior_prior.query import PriorQuery
from social_sim.behavior_prior.validation import query_coverage, sanity_table


@pytest.fixture(scope="module")
def corpora():
    return load_nested_worker_corpora()


def test_nested_worker_corpus_reproducible(corpora):
    groups, info = corpora
    assert info["source_all_adult_diaries"] == 7341
    assert info["sample_sizes"] == {"B100": 100, "B1000": 1000, "BALL": 3215}
    assert {d["day_id"] for d in groups["B100"]} < {d["day_id"] for d in groups["B1000"]} < {d["day_id"] for d in groups["BALL"]}
    assert all(d["metadata"]["weekday"] and d["metadata"]["employment_status"] in (1, 2)
               for d in groups["BALL"])
    assert load_nested_worker_corpora()[1]["sample_id_hashes"] == info["sample_id_hashes"]


def test_index_reproducible_and_never_returns_other(corpora):
    groups, _ = corpora
    first = BehaviorPriorIndex.build(groups["B100"])
    second = BehaviorPriorIndex.build(groups["B100"])
    assert first.index_hash == second.index_hash
    assert first.query(PriorQuery(36, "MOVE"), limit=3) == second.query(PriorQuery(36, "MOVE"), limit=3)
    for name, days in groups.items():
        index = BehaviorPriorIndex.build(days)
        result = index.query(PriorQuery(36, "MOVE"), limit=3)
        assert 1 <= len(result.activities) <= 3
        assert len(set(result.activities)) == len(result.activities)
        assert set(result.activities) <= set(CORE7)
        assert 0 <= result.excluded_other_mass <= 1
        assert result.support_count >= 10
        assert query_coverage(index)["empty_rate"] == 0
        assert len(sanity_table(index)) == 25
        if name == "B100":
            assert query_coverage(index)["fallback_L3"] > 0


def test_threshold_selection_uses_measured_sparsity(corpora):
    days = corpora[0]["B100"]
    low = query_coverage(BehaviorPriorIndex.build(days, min_support_count=10))
    high = query_coverage(BehaviorPriorIndex.build(days, min_support_count=20))
    assert low["exact_hit_rate"] > high["exact_hit_rate"]
    assert low["fallback_L3"] < high["fallback_L3"]
