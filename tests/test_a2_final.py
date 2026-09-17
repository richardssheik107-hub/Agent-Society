"""Offline, request-free A2-Final split, scorer, panel, and selection gates."""

from __future__ import annotations

import asyncio
import json

from social_sim.a2_final.corpus import HeldoutScorer, split_worker_diaries
from social_sim.a2_final.micro import SCENARIOS, micro_arms, micro_episode_row, micro_schedule, summarize_micro
from social_sim.a2_final.panel import CONDITIONS, STATES, FixedStateDecisionBenchmark, panel_schedule
from social_sim.a2_final.selection import select_engineering_baseline
from social_sim.a2_final.synthesis import synthesize_final_answer
from social_sim.behavior_prior.index import BehaviorPriorIndex
from social_sim.behavior_prior.query import PriorQuery
from social_sim.daily.profiles import load_experiment_profiles
from social_sim.daily.runner import DailyEpisodeRunner
from social_sim.daily.validation import validate_daily_trajectory
from social_sim.decision.client import FakeDecisionClient


def _offline_benchmark():
    corpora, eval_days, split = split_worker_diaries()
    indices = {name: BehaviorPriorIndex.build(days) for name, days in corpora.items()}
    client = FakeDecisionClient('{"action":"LEISURE","target":null}')
    return (FixedStateDecisionBenchmark(client, load_experiment_profiles()[2],
                                        indices, HeldoutScorer(eval_days)), client, split, corpora, eval_days)


def test_split_is_day_level_nested_and_reproducible() -> None:
    _, _, first, corpora, eval_days = _offline_benchmark()
    _, _, second, _, _ = _offline_benchmark()
    assert first == second
    assert (first["train_count"], first["eval_count"], first["overlap_count"]) == (2572, 643, 0)
    ids = {name: {day["day_id"] for day in days} for name, days in corpora.items()}
    assert ids["B100"] < ids["B1000"] < ids["BTRAIN_ALL"]
    assert not ids["BTRAIN_ALL"] & {day["day_id"] for day in eval_days}


def test_heldout_scorer_uses_eval_only_and_is_deterministic() -> None:
    _, _, _, _, eval_days = _offline_benchmark()
    scorer = HeldoutScorer(eval_days)
    first = scorer.distribution(PriorQuery.at(STATES[5].world().time, "MOVE"))
    second = scorer.distribution(PriorQuery.at(STATES[5].world().time, "MOVE"))
    assert first == second
    assert first.support_count > 0 and first.fallback_level in ("L0", "L1", "L2", "L3")
    scored = first.score("CHORES")
    assert 0 <= scored["heldout_action_share"] <= 1
    assert scored["heldout_top3_match"] == (scored["heldout_rank"] is not None and scored["heldout_rank"] <= 3)


def test_fixed_panel_schedule_and_context_scope() -> None:
    benchmark, client, _, _, _ = _offline_benchmark()
    schedule = panel_schedule()
    assert len(schedule) == len({case["case_id"] for case in schedule}) == 80
    assert all(sum(case["state_id"] == state.state_id and case["repetition"] == repetition
                   for case in schedule) == 5 for state in STATES for repetition in (1, 2))
    for state in STATES:
        control = json.loads(benchmark.preview(state, CONDITIONS[0])["context"])
        assert "h" not in control
        for condition in CONDITIONS[1:]:
            treatment = json.loads(benchmark.preview(state, condition)["context"])
            hints = treatment.pop("h")
            assert treatment == control
            assert len(hints) == 1
            assert len(benchmark.preview(state, condition)["prior"].activities) <= condition.prior_k
        assert state.event_log().all()[-1].action.value == state.previous_activity if state.previous_activity else not state.event_log().all()
    result = asyncio.run(benchmark.run(schedule[0]))
    assert result["provider_status"] == "SUCCESS" and result["action"] == "LEISURE"
    assert result["provider_request_count"] == 0 and client.call_count == 1


def _synthetic_rows(*, c4_share: float = 0.26, successes: int = 80) -> list[dict[str, object]]:
    rows = []
    for number, case in enumerate(panel_schedule()):
        condition = case["condition"]
        share = {"C0": 0.10, "C1": 0.20, "C2": 0.25, "C3": 0.25, "C4": c4_share}[condition]
        rows.append({**case, "provider_status": "SUCCESS" if number < successes else "TIMEOUT",
                     "heldout_action_share": share, "rule_executable": True,
                     "heldout_top3_match": False, "context_chars": 560 if condition == "C4" else 540,
                     "input_tokens": 260 if condition == "C4" else 250})
    return rows


def test_engineering_selection_is_pre_registered_and_safe_for_untested_cross_factor() -> None:
    exact = {"B100": 0.12, "B1000": 0.71, "BTRAIN_ALL": 0.86}
    chosen = select_engineering_baseline(_synthetic_rows(), exact)
    assert chosen["minimum_corpus_at_R1"] == "B1000"
    assert chosen["minimum_prior_at_full_train"] == "R1"
    assert (chosen["selected_corpus"], chosen["selected_prior"]) == ("B1000", "R1")
    r3 = select_engineering_baseline(_synthetic_rows(c4_share=0.30), exact)
    assert r3["minimum_prior_at_full_train"] == "R3"
    assert (r3["selected_corpus"], r3["selected_prior"]) == ("BTRAIN_ALL", "R3")
    weak = select_engineering_baseline(_synthetic_rows(successes=60), exact)
    assert not weak["reference_provider_stable_enough"]
    assert weak["minimum_corpus_at_R1"] == weak["minimum_prior_at_full_train"] == "UNRESOLVED"
    assert weak["selection_basis"] == "CONSERVATIVE_FALLBACK_NOT_MINIMUM"


def test_micro_schedule_and_validation_rules() -> None:
    arms = micro_arms("B1000", "R1")
    schedule = micro_schedule(arms)
    assert len(schedule) == 24
    assert all(sum(row["scenario"] == scenario.name and row["repetition"] == repetition
                   for row in schedule) == 3 for scenario in SCENARIOS for repetition in (1, 2))
    rows = [{"episode_number": item["episode"], "scenario": item["scenario"],
             "repetition": item["repetition"], "condition": item["arm"],
             "segment_completion": True, "termination_reason": "DAY_END",
             "idle_ratio": 0.0, "rejection_rate": 0.0, "decision_count": 1,
             "repeated_invalid_count": 0, "active_minutes": 90, "unique_activity_types": 1,
             "personal_care_proposals": 0, "personal_care_accepted": 0,
             "chores_proposals": 0, "chores_accepted": 0} for item in schedule]
    assert summarize_micro(rows, arms)["minimum_validation"] == "PASS"
    candidate = next(row for row in rows if row["condition"] == "CANDIDATE")
    candidate["idle_ratio"] = 0.2
    assert summarize_micro(rows, arms)["minimum_validation"] == "DEGRADED"
    full_arms = micro_arms("BTRAIN_ALL", "R1")
    assert len(micro_schedule(full_arms)) == 16


def test_micro_runner_is_bounded_and_partial_metrics_are_separate() -> None:
    client = FakeDecisionClient('{"action":"LEISURE","target":null}')
    for number, scenario in enumerate(SCENARIOS, 1):
        result = asyncio.run(DailyEpisodeRunner(
            client, write_artifacts=False, initial_world=scenario.world(),
            behavior_profile=load_experiment_profiles()[2], window_minutes=90,
            max_decisions_per_day=4, allow_deterministic_output_recovery=True,
        ).run_episode(number))
        assert validate_daily_trajectory(result)
        assert result.decision_count <= 4 and result.observed_minutes <= 90
        row = micro_episode_row(result, micro_schedule(micro_arms("BTRAIN_ALL", "R1"))[number - 1])
        assert row["episode_number"] == number
        if not result.day_completed:
            assert row["idle_ratio"] is None and row["partial_observed_minutes"] == result.observed_minutes


def test_final_synthesis_requires_actual_evidence_and_never_calls_judge() -> None:
    rows = _synthetic_rows()
    for row in rows:
        row["actual_backend"] = "synthetic"
    exact = {"B100": 0.12, "B1000": 0.71, "BTRAIN_ALL": 0.86}
    selection = select_engineering_baseline(rows, exact)
    retrieval = {"train": {name: {"exact_hit_rate": rate} for name, rate in exact.items()}}
    micro = {"episodes": 24, "architecture_failures": 0, "minimum_validation": "PASS"}
    split = {"train_count": 2572, "eval_count": 643}
    answer = synthesize_final_answer(selection, rows, micro, split, retrieval, "fixed-hash")
    assert answer["status"] == "RESEARCH QUESTIONS CLOSED — ENGINEERING BASELINE"
    assert (answer["minimum_corpus"], answer["minimum_corpus_diaries"], answer["minimum_prior"]) == (
        "B1000", 1000, "R1")
    assert answer["llm_call_boundary"]["judge"] == 0
    weak_rows = _synthetic_rows(successes=60)
    for row in weak_rows:
        row["actual_backend"] = None
    weak = select_engineering_baseline(weak_rows, exact)
    weak_answer = synthesize_final_answer(weak, weak_rows, micro, split, retrieval, "fixed-hash")
    assert weak_answer["status"] == "RESEARCH QUESTION 1 PARTIALLY UNRESOLVED"
    assert weak_answer["minimum_corpus_diaries"] is None
