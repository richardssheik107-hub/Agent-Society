"""R0 identity and the sole R1/R3 compact-context delta."""

from __future__ import annotations

import json

import pytest

from social_sim.behavior_prior import BehaviorPriorIndex, format_prior, load_nested_worker_corpora
from social_sim.behavior_prior.query import PriorQuery
from social_sim.daily.calibrated import CalibratedSegmentBenchmark
from social_sim.daily.profiles import load_experiment_profiles
from social_sim.decision.client import FakeDecisionClient


@pytest.mark.asyncio
async def test_r0_equals_a20_g2_and_prior_is_only_delta(tmp_path):
    groups, _ = load_nested_worker_corpora()
    index = BehaviorPriorIndex.build(groups["B100"])
    profile = load_experiment_profiles()[2]
    contexts = []
    for number, (prior, limit) in enumerate(((None, 0), (None, 0), (index, 1), (index, 3)), 1):
        result = await CalibratedSegmentBenchmark(
            FakeDecisionClient('{"action":"LEISURE","target":null}'),
            tmp_path, prior_index=prior, prior_limit=limit,
        ).run(number, "MORNING", profile)
        assert result.day_completed
        contexts.append(result.trajectory.steps[0].context)
        assert bool(result.prior_audit) == bool(limit)
        if limit:
            assert all(1 <= len(record["activities"]) <= limit for record in result.prior_audit)
            assert all(record["support_count"] > 0 and record["feasible_prior_count"] <= len(record["activities"])
                       for record in result.prior_audit)
    assert contexts[0] == contexts[1]
    baseline = json.loads(contexts[0])
    assert "h" not in baseline
    for prior_context in contexts[2:]:
        context = json.loads(prior_context)
        assert len(context["h"]) == 1
        assert {key: value for key, value in context.items() if key != "h"} == baseline


def test_formatter_short_neutral_and_no_probabilities():
    groups, _ = load_nested_worker_corpora()
    index = BehaviorPriorIndex.build(groups["BALL"])
    for limit in (1, 3):
        result = index.query(PriorQuery(37, "MOVE"), limit=limit)
        hint = format_prior(result)
        assert len(hint) <= 120
        assert hint.startswith("prior: common around now")
        assert "%" not in hint and "Do " not in hint
        assert all(activity in hint for activity in result.activities)
