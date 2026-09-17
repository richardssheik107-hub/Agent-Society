"""Finalize the offline closure gate without touching A2-Final history or provider."""

from __future__ import annotations

from a2_closure_audit import MARKER, OUTPUT_ROOT, read_json, write_json
from social_sim.a2_closure.audit import decide_runtime_change


def main() -> None:
    output = OUTPUT_ROOT / read_json(MARKER)["experiment_id"]
    cells = read_json(output / "max_decision_audit.json")
    root = read_json(output / "root_cause_summary.json")
    prior = read_json(output / "prior_loop_audit.json")
    if len(cells) != 7 or root["audited"] != 7:
        raise RuntimeError("CLOSURE_AUDIT_INCOMPLETE")
    same_tick = 0
    for cell in cells:
        times = [line.split(" ", 1)[0] for line in cell["compact_trace"]]
        same_tick += len(times) - len(set(times))
    root_for_gate = {**root, "same_tick_duplicate_count": same_tick}
    decision = decide_runtime_change(root_for_gate, prior)
    if decision["decision"] != "BEHAVIORAL_CAUSE_UNRESOLVED":
        raise RuntimeError("UNEXPECTED_RUNTIME_GATE_REQUIRES_REVIEW")
    write_json(output / "max_decision_cells.json", [
        {key: cell[key] for key in ("cell_id", "scenario", "condition", "observed_minutes",
                                    "decision_count", "accepted_count", "rejected_count",
                                    "activity_minutes", "prior_count", "termination_point")}
        for cell in cells
    ])
    write_json(output / "scoring_method.json", {
        "denominator": "four completed decisions per capped cell except E, whose denominator is prior-followed decisions",
        "A": "adjacent identical rejected action/target/reason with unchanged coarse core state / 4",
        "B": "accepted instantaneous MOVE/BUY/EAT followed by a new decision within 15 simulated minutes and no timed activity / 4",
        "C": "adjacent decision pre-states equal on location, activity, money, inventory, hunger/energy rounded to 0.1 and work_due / 4",
        "D": "ACTIVITY_COMPLETED or OBLIGATION_BOUNDARY trigger count / 4",
        "E": "prior-followed rejected action count / prior-followed decision count; zero if none",
        "F": "rejected proposal under CRITICAL_NEED / 4",
        "G": "location A>B>A cycle participation / 4",
        "H": "largest and second-largest evidence scores differ by less than 0.10",
        "I": "required trajectory field absent",
        "global_dominance": "one primary cause in at least four of seven cells",
        "same_tick_duplicate_count": same_tick,
        "scores_are_engineering_evidence_not_probabilities": True,
    })
    write_json(output / "runtime_change_decision.json", decision)
    final = {
        "schema_version": 1,
        "historical_a2_final_stage_a_preserved": True,
        "historical_a2_final_stage_b_cells_rerun": False,
        "max_decisions_audited": 7,
        "root_causes": root["primary_counts"],
        "global_dominant_cause": root["global_dominant_cause"],
        "prior_loop_signal": prior["prior_loop_signal"],
        "architecture_error_historical_cell_remains_invalid": True,
        "architecture_harness_fix_regression": "PASS",
        "runtime_change_decision": decision["decision"],
        "runtime_guard": "NONE",
        "real_continuity_rerun": "NOT_NEEDED",
        "continuity_confirmation_episodes": 0,
        "provider_requests": 0,
        "current_minimum_tested_corpus_diaries": 2572,
        "current_minimum_prior": "R1",
        "current_reference_context_structure": (
            "recommended compact current state + needs/obligation + 1–3 short recent events + R1 prior; "
            "the 1–3 range was not jointly tested, last relevant event is a candidate, "
            "C3_recent3 is the tested runtime event policy"
        ),
        "question_1_decision_layer_status": "CLOSED_ENGINEERING",
        "question_1_continuity_layer_status": "PARTIALLY_UNRESOLVED",
        "question_2_status": "CLOSED_ENGINEERING",
        "open_data_calibration_worthwhile": "YES",
        "production_config_modified": False,
        "llm_calls": {"audit": 0, "retrieval": 0, "environment": 0,
                      "rules": 0, "reducer": 0, "judge": 0},
        "contains_raw_prompt": False,
        "contains_hidden_reasoning": False,
        "final_status": "RESEARCH QUESTION 1 PARTIALLY UNRESOLVED",
    }
    write_json(output / "final_closure.json", final)
    print(f"A2_CLOSURE_FINALIZED status={final['final_status']} provider_requests=0 output={output}")


if __name__ == "__main__":
    main()
