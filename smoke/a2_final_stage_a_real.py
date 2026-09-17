"""One-time, 80-request A2-Final independent decision panel."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "third_party/AgentSociety/.env")

from behavior_prior_corpus_real_pilot import audit_secrets  # noqa: E402
from social_sim.a2_final.corpus import HeldoutScorer, split_worker_diaries  # noqa: E402
from social_sim.a2_final.panel import (  # noqa: E402
    CONDITIONS, STATES, FixedStateDecisionBenchmark, panel_schedule,
)
from social_sim.a2_final.selection import select_engineering_baseline  # noqa: E402
from social_sim.behavior_prior.index import BehaviorPriorIndex  # noqa: E402
from social_sim.behavior_prior.validation import query_coverage  # noqa: E402
from social_sim.daily.calibrated import config_hash  # noqa: E402
from social_sim.daily.profiles import SOURCE as PROFILE_SOURCE, load_experiment_profiles  # noqa: E402
from social_sim.decision import FakeDecisionClient, OpenAICompatibleDecisionClient  # noqa: E402
from social_sim.decision.config import CODING_PLAN, DecisionProviderConfig  # noqa: E402
from social_sim.evaluation.models import world_snapshot  # noqa: E402


OUTPUT_ROOT = ROOT / "run/evaluation/a2_final"
START_MARKER = OUTPUT_ROOT / "a2_final_started.json"
BASELINE = "9b5e6e33f0ea9046e596a649562a1737e98c8491"
PROTECTED = (ROOT / "src/social_sim/daily/time.py", PROFILE_SOURCE)
PROTECTED_HASHES = {
    "src/social_sim/daily/time.py": "9ac6b13ade1eeb3c9e7345950ed4891453eaf01aadd9f5fe72d959bc36fcf320",
    "config/experimental/neutral_day_calibrated_v1.yaml": "58f293122bc48b274e1c4cfee3d8b198877bb3508fbd1b72c5bdc61e620ba14f",
}


def protected_hashes() -> dict[str, str]:
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in PROTECTED}


def write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=False, indent=2, allow_nan=False)
        file.write("\n")


def csv_row(row: dict[str, object]) -> dict[str, object]:
    return {key: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            if isinstance(value, (list, dict)) else value for key, value in row.items()}


async def main() -> None:
    if START_MARKER.exists():
        raise RuntimeError("A2_FINAL_ALREADY_STARTED_DO_NOT_RERUN")
    provider_config = DecisionProviderConfig.from_env()
    if provider_config.model != "ark-code-latest" or provider_config.base_url_category != CODING_PLAN:
        raise RuntimeError("A2_FINAL_PROVIDER_CONFIG_MISMATCH")
    before = protected_hashes()
    if before != PROTECTED_HASHES:
        raise RuntimeError("FROZEN_PRODUCTION_OR_PROFILE_HASH_MISMATCH")
    corpora, eval_days, split = split_worker_diaries()
    indices = {name: BehaviorPriorIndex.build(days) for name, days in corpora.items()}
    if any(day["day_id"] in {item["day_id"] for item in eval_days}
           for corpus in corpora.values() for day in corpus):
        raise RuntimeError("EVAL_RETRIEVAL_LEAKAGE")
    scorer = HeldoutScorer(eval_days)
    profile = load_experiment_profiles()[2]
    schedule = panel_schedule()
    offline = FixedStateDecisionBenchmark(FakeDecisionClient('{"action":"LEISURE","target":null}'),
                                          profile, indices, scorer)
    for state in STATES:
        r0 = offline.preview(state, CONDITIONS[0])
        if '"h":' in r0["context"]:
            raise RuntimeError("R0_PRIOR_LEAK")
        for condition in CONDITIONS[1:]:
            probe = offline.preview(state, condition)
            if len(probe["prior"].activities) > condition.prior_k:
                raise RuntimeError("PRIOR_LIST_LIMIT")
    fake_row = await offline.run(schedule[0])
    if fake_row["provider_status"] != "SUCCESS" or fake_row["provider_request_count"] != 0:
        raise RuntimeError("OFFLINE_CONTEXT_PRECHECK_FAILED")
    fields = tuple(fake_row)
    config = {
        "experiment_type": "a2_final_independent_fixed_state_panel", "git_baseline_commit": BASELINE,
        "profile": profile.name, "profile_hash": profile.profile_hash,
        "split_hash": split["split_hash"], "source_sha256": split["source_sha256"],
        "train_index_hashes": {name: index.index_hash for name, index in indices.items()},
        "eval_index_hash": scorer.index.index_hash,
        "states": [{"state_id": state.state_id, "title": state.title,
                    "world": world_snapshot(state.world()), "previous_activity": state.previous_activity}
                   for state in STATES],
        "conditions": [{"name": condition.name, "corpus": condition.corpus or "B0",
                        "prior_k": condition.prior_k} for condition in CONDITIONS],
        "schedule": schedule, "requests": 80, "repetitions": 2,
        "retrieval_min_support_count": 10, "eval_min_support_count": 10,
        "provider_alias": provider_config.model, "request_fields": ["model", "messages"],
        "request_timeout_seconds": 60, "transport_retries": 0,
        "pre_registered_thresholds": select_engineering_baseline(
            [{"case_id": f"placeholder-{index}", "provider_status": "PROVIDER_ERROR",
              "condition": schedule[index]["condition"], "state_id": schedule[index]["state_id"],
              "repetition": schedule[index]["repetition"]} for index in range(80)],
            {name: 0.0 for name in indices},
        )["thresholds"],
        "production_protected_before": before,
    }
    config["experiment_config_hash"] = config_hash(config)
    output = OUTPUT_ROOT / f"real_{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}"
    stage = output / "stage_a"
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    stage.mkdir()
    write_json(stage / "experiment_config.json", config)
    write_json(stage / "train_eval_split.json", split)
    write_json(stage / "corpus_manifest.json", {
        "train_sizes": {name: len(days) for name, days in corpora.items()},
        "eval_size": len(eval_days), "source_sha256": split["source_sha256"],
        "train_sample_hashes": split["train_sample_hashes"],
        "train_index_hashes": config["train_index_hashes"], "eval_index_hash": scorer.index.index_hash,
        "eval_used_for_retrieval": False, "contains_raw_diary": False,
    })
    coverage = {name: query_coverage(index) for name, index in indices.items()}
    write_json(stage / "retrieval_metrics.json", {"train": coverage, "eval": query_coverage(scorer.index)})
    write_json(stage / "schedule.json", schedule)
    with (stage / "decision_rows.csv").open("x", encoding="utf-8", newline="") as file:
        csv.DictWriter(file, fieldnames=fields).writeheader()
    (stage / "decision_rows.jsonl").open("x", encoding="utf-8").close()
    (stage / "request_starts.jsonl").open("x", encoding="utf-8").close()
    audit_secrets(output, provider_config.api_key)
    write_json(START_MARKER, {"experiment_id": output.name, "config_hash": config["experiment_config_hash"],
                              "started_at": datetime.now(timezone.utc).isoformat()})
    provider = OpenAICompatibleDecisionClient(
        base_url=provider_config.api_base, api_key=provider_config.api_key,
        model=provider_config.model, timeout_seconds=60, minimal_request=True,
    )
    rows = []
    try:
        benchmark = FixedStateDecisionBenchmark(provider, profile, indices, scorer)
        for number, case in enumerate(schedule, 1):
            with (stage / "request_starts.jsonl").open("a", encoding="utf-8") as file:
                file.write(json.dumps({"case_id": case["case_id"], "started_at":
                                       datetime.now(timezone.utc).isoformat()}) + "\n")
            print(f"START STAGE_A={number}/80 {case['state_id']} {case['condition']}", flush=True)
            row = await benchmark.run(case)
            if tuple(row) != fields or row["provider_request_count"] != 1:
                raise RuntimeError("PANEL_ROW_OR_REQUEST_INVARIANT")
            with (stage / "decision_rows.jsonl").open("a", encoding="utf-8") as file:
                file.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
            with (stage / "decision_rows.csv").open("a", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=fields)
                writer.writerow(csv_row(row))
            rows.append(row)
            if protected_hashes() != before:
                raise RuntimeError("PROTECTED_CONFIG_MODIFIED")
            if number % 10 == 0:
                audit_secrets(output, provider_config.api_key)
            print(f"DONE STAGE_A={number}/80 {row['provider_status']} action={row['action'] or 'NONE'}", flush=True)
        selection = select_engineering_baseline(
            rows, {name: metrics["exact_hit_rate"] for name, metrics in coverage.items()}
        )
        write_json(stage / "paired_comparisons.json", selection["comparisons"])
        write_json(stage / "engineering_selection.json", selection)
        counts = Counter(row["provider_status"] for row in rows)
        backend = Counter(row["actual_backend"] for row in rows if row["actual_backend"])
        with (stage / "summary.md").open("x", encoding="utf-8") as file:
            file.write("# A2-Final fixed-state decision panel\n\n"
                       f"Requests: 80; success={counts['SUCCESS']}, timeout={counts['TIMEOUT']}, "
                       f"invalid={counts['INVALID_MODEL_OUTPUT']}, provider_error={counts['PROVIDER_ERROR']}.\n\n"
                       f"Actual backend (successful envelopes): {dict(backend)}.\n\n"
                       f"Train: 2572 diaries; eval: 643 disjoint diaries.\n"
                       f"Exact-hit rates: { {name: round(item['exact_hit_rate'], 4) for name, item in coverage.items()} }.\n"
                       f"Minimum corpus at R1: {selection['minimum_corpus_at_R1']}.\n"
                       f"Minimum prior at full train: {selection['minimum_prior_at_full_train']}.\n"
                       f"Selected Stage B arm: {selection['selected_corpus']} + {selection['selected_prior']} "
                       f"({selection['selection_basis']}).\n\n"
                       "All behavioral comparisons use matched successful state×repetition pairs. "
                       "A held-out diary distribution is not a single correct action.\n")
        audit_secrets(output, provider_config.api_key)
        print(f"STAGE_A_COMPLETE success={counts['SUCCESS']} timeout={counts['TIMEOUT']} "
              f"invalid={counts['INVALID_MODEL_OUTPUT']} output={output}", flush=True)
    finally:
        await provider.aclose()


if __name__ == "__main__":
    asyncio.run(main())
