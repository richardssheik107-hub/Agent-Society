"""A2-Fast no-network retrieval, R0-equivalence, and context budget gate."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from social_sim.behavior_prior import BehaviorPriorIndex, load_nested_worker_corpora
from social_sim.behavior_prior.validation import query_coverage, sanity_table
from social_sim.daily.calibrated import CalibratedSegmentBenchmark
from social_sim.daily.profiles import load_experiment_profiles
from social_sim.decision.client import FakeDecisionClient


async def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output = root / "run/evaluation/behavior_prior_corpus" / f"offline_{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}"
    output.mkdir(parents=True)
    groups, corpus_info = load_nested_worker_corpora()
    assert {name: len(days) for name, days in groups.items()} == {"B100": 100, "B1000": 1000, "BALL": 3215}
    indices = {name: BehaviorPriorIndex.build(days) for name, days in groups.items()}
    assert indices["B100"].index_hash == BehaviorPriorIndex.build(groups["B100"]).index_hash
    coverage = {name: query_coverage(index) for name, index in indices.items()}
    assert all(data["empty_rate"] == 0 for data in coverage.values())
    with (output / "query_coverage.json").open("x", encoding="utf-8") as file:
        json.dump({"min_support_count": 10, "corpora": coverage,
                   "sanity_table": {name: sanity_table(index) for name, index in indices.items()}},
                  file, ensure_ascii=False, indent=2)
    with (output / "corpus_manifest.json").open("x", encoding="utf-8") as file:
        json.dump(corpus_info, file, ensure_ascii=False, indent=2)
    profile = load_experiment_profiles()[2]
    conditions = (("C0", None, 0), ("C1", indices["B100"], 1),
                  ("C2", indices["B1000"], 1), ("C3", indices["BALL"], 1),
                  ("C4", indices["BALL"], 3))
    contexts = {}
    for number, (name, index, limit) in enumerate(conditions, 1):
        result = await CalibratedSegmentBenchmark(
            FakeDecisionClient('{"action":"LEISURE","target":null}'),
            output / "episodes", prior_index=index, prior_limit=limit,
        ).run(number, "MORNING", profile)
        assert result.day_completed and result.provider_request_count == 0
        assert all(len(record["activities"]) <= limit for record in result.prior_audit)
        assert all(record["hint_chars"] <= 120 for record in result.prior_audit)
        assert result.trajectory.max_context_chars < 2000 and result.trajectory.max_prompt_chars < 3000
        contexts[name] = result.trajectory.steps[0].context
        print(f"{name}=PASS priors={len(result.prior_audit)} max_context={result.trajectory.max_context_chars}")
    assert "h" not in json.loads(contexts["C0"])
    reference = await CalibratedSegmentBenchmark(
        FakeDecisionClient('{"action":"LEISURE","target":null}'),
        output / "episodes",
    ).run(6, "MORNING", profile)
    assert contexts["C0"] == reference.trajectory.steps[0].context
    assert hashlib.sha256(contexts["C0"].encode()).hexdigest() == hashlib.sha256(reference.trajectory.steps[0].context.encode()).hexdigest()
    for name in ("C1", "C2", "C3", "C4"):
        changed = json.loads(contexts[name])
        assert {key: value for key, value in changed.items() if key != "h"} == json.loads(contexts["C0"])
    print("NESTED_CORPUS=PASS RETRIEVAL_DETERMINISTIC=PASS R0_CONTEXT_EQUIVALENCE=PASS PROVIDER_CALLS=0")
    print(f"OFFLINE_ARTIFACT_DIR={output}")


if __name__ == "__main__":
    asyncio.run(main())
