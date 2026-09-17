"""Deterministic A2-Final answer assembly; never calls a model judge."""

from __future__ import annotations

from collections import Counter


CONTEXT_STRUCTURE = (
    "compact current state + current needs/obligation + last relevant event "
    "+ bounded empirical behavior prior"
)


def synthesize_final_answer(
    selection: dict[str, object], panel_rows: list[dict[str, object]],
    micro: dict[str, object], split: dict[str, object],
    retrieval: dict[str, object], baseline_commit: str,
) -> dict[str, object]:
    """Assemble only pre-registered engineering conclusions from frozen artifacts."""
    if len(panel_rows) != 80 or micro["episodes"] not in (16, 24):
        raise ValueError("A2_FINAL_INCOMPLETE_INPUT")
    if selection["panel_requests"] != 80 or selection["success"] != sum(
        row["provider_status"] == "SUCCESS" for row in panel_rows
    ):
        raise ValueError("A2_FINAL_PANEL_COUNT_MISMATCH")
    counts = Counter(row["provider_status"] for row in panel_rows)
    backends = Counter(row["actual_backend"] for row in panel_rows if row["actual_backend"])
    minimum_corpus = selection["minimum_corpus_at_R1"]
    minimum_prior = selection["minimum_prior_at_full_train"]
    # R3 was tested only at full train, so a smaller R1 corpus cannot be
    # advertised as a validated smaller-corpus/R3 joint configuration.
    if minimum_prior == "R3" and minimum_corpus != "UNRESOLVED":
        minimum_corpus = "BTRAIN_ALL"
    sizes = {"B100": 100, "B1000": 1000, "BTRAIN_ALL": split["train_count"]}
    minimum_diaries = sizes.get(minimum_corpus)
    stable = selection["success_rate"] >= 0.90
    continuity = micro["minimum_validation"] in ("PASS", "SAME_AS_FULL")
    closed = (stable and minimum_corpus != "UNRESOLVED" and minimum_prior != "UNRESOLVED"
              and micro["architecture_failures"] == 0 and continuity)
    status = ("RESEARCH QUESTIONS CLOSED — ENGINEERING BASELINE" if closed
              else "RESEARCH QUESTION 1 PARTIALLY UNRESOLVED")
    return {
        "schema_version": 1,
        "git_baseline_commit": baseline_commit,
        "status": status,
        "minimum_corpus": minimum_corpus,
        "minimum_corpus_diaries": minimum_diaries,
        "minimum_corpus_at_R1": selection["minimum_corpus_at_R1"],
        "minimum_prior": minimum_prior,
        "minimum_prior_activity_names": {"R1": 1, "R3": 3}.get(minimum_prior),
        "minimum_context_structure": CONTEXT_STRUCTURE,
        "minimum_context_structure_status": "CROSS_PHASE_CANDIDATE_NOT_JOINTLY_ABLATED",
        "tested_runtime_event_policy": "C3_recent3",
        "selected_reference_profile": {
            "corpus": selection["selected_corpus"], "prior": selection["selected_prior"],
            "selection_basis": selection["selection_basis"],
            "tested_runtime_event_policy": "C3_recent3",
            "context_structure_candidate_is_exact_joint_ablation": False,
        },
        "question_1_answer": {
            "idle_causes": [
                "Core5 action-space incompleteness: PERSONAL_CARE and CHORES were absent (B1.2).",
                "WORK duration 90 minutes versus empirical median about 270 minutes caused needless re-decisions (B1.2/A2.0).",
                "Rejected proposals and same-state repeated decisions produced non-progress loops (A1/A1.1/8A).",
                "Missing local time/transition behavior cues can leave the model without a useful next-activity prior (A2-Fast/A2-Final).",
                "Provider timeout/truncation prevents completing observations and is not agent inactivity (A1.1/A2-Fast/A2-Final).",
            ],
            "minimum_corpus": minimum_corpus,
            "minimum_corpus_diaries": minimum_diaries,
            "minimum_prior": minimum_prior,
            "minimum_context_structure": CONTEXT_STRUCTURE,
            "minimum_context_structure_status": "CROSS_PHASE_CANDIDATE_NOT_JOINTLY_ABLATED",
            "scope": "Current small-context simulator engineering candidate, not a population or theoretical minimum.",
        },
        "question_2_answer": {
            "hard_deterministic_rules": ["money", "inventory", "stock", "location validity",
                                         "seller presence", "state consistency", "activity conflict",
                                         "world consequences"],
            "empirical_calibration": ["activity ontology", "comparable duration",
                                      "time-of-day distribution", "transition prior",
                                      "behavior corpus", "population-level activity support"],
            "model_role": "Choose the next action from compact state and bounded prior; deterministic rules govern consequences.",
            "open_data_calibration_worthwhile": "YES",
            "evidence": {"core5_all_adult_minute_coverage": 0.8217,
                         "core7_all_adult_minute_coverage": 0.9300,
                         "core7_employed_weekday_minute_coverage": 0.9461,
                         "old_work_minutes": 90, "empirical_work_median_minutes_approx": 270,
                         "retrieval_exact_hit_rates": {name: data["exact_hit_rate"]
                                                       for name, data in retrieval["train"].items()}},
            "boundary": "Historical diary distributions inform calibration, never force a schedule or override rules.",
        },
        "stage_a": {"requests": 80, "success": counts["SUCCESS"], "timeout": counts["TIMEOUT"],
                    "invalid_output": counts["INVALID_MODEL_OUTPUT"],
                    "provider_error": counts["PROVIDER_ERROR"], "actual_backends": dict(backends),
                    "success_rate": selection["success_rate"], "train_diaries": split["train_count"],
                    "eval_diaries": split["eval_count"],
                    "exact_hit_rates": {name: data["exact_hit_rate"] for name, data in retrieval["train"].items()},
                    "prior_effect": selection["comparisons"]["prior_C0_C3"],
                    "prior_size": selection["comparisons"]["prior_size_C3_C4"]},
        "stage_b": micro,
        "provider_limitations": ("REFERENCE_PROVIDER_NOT_STABLE_ENOUGH" if not stable else
                                 "Independent panel met the 90% engineering comparison gate; "
                                 "micro-rollout may still be provider-truncated."),
        "local_8b_next_step": "Use the frozen reference profile later; change only DecisionClient/model. No local 8B run in A2-Final.",
        "llm_call_boundary": {"retrieval": 0, "heldout_scorer": 0, "environment": 0,
                              "rules": 0, "reducer": 0, "judge": 0},
    }
