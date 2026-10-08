"""Synthetic metric cases: these tests are not evidence of model benefit."""
from __future__ import annotations

import json

import pytest

from social_sim.continuity.q6_2_panel_reporting import (
    SCHEMA_VERSION,
    paired_comparison,
    render_report,
    summarize,
)


def cell(condition: str, *, pair: str = "p001", accepted: bool = True,
         valid: bool = True, **extra: object) -> dict:
    row = {
        "cell_id": "c001" if condition == "A_RAW" else "c002",
        "pair_id": pair, "scenario_id": "s01", "family": "OWNERSHIP", "repeat": 1,
        "condition": condition,
        "status": "DECISION_ACCEPTED" if accepted else "RULE_REJECTED",
        "intent_registered": True, "client_call_attempted": True,
        "http_response_observed": True, "service_contract_valid": True,
        "strict_json_valid": valid, "catalog_valid": valid, "rule_checked": valid,
        "start_accepted": accepted if valid else None,
        "activity_completed": accepted if valid else None, "invariants_valid": True,
        "proposal_in_feasible_set": accepted if valid else None,
        "requested_model": "offline-alias", "provider_model": "offline-fake",
        "input_tokens": 10, "output_tokens": 4, "reasoning_tokens": 0,
        "prompt_chars": 200 if condition == "A_RAW" else 300,
        "latency_seconds": 0.01, "simulation_minutes": 15 if accepted else 0,
    }
    row.update(extra)
    return row


@pytest.mark.parametrize(
    ("a", "b", "a_rate", "b_rate", "combination"),
    [
        (cell("A_RAW", accepted=False), cell("B_FEASIBLE"), 1, 0,
         "A_REJECTED_B_ACCEPTED"),
        (cell("A_RAW"), cell("B_FEASIBLE"), 0, 0, "A_ACCEPTED_B_ACCEPTED"),
        (cell("A_RAW"), cell("B_FEASIBLE", accepted=False), 0, 1,
         "A_ACCEPTED_B_REJECTED"),
        (cell("A_RAW", valid=False, status="INVALID_MODEL_OUTPUT"),
         cell("B_FEASIBLE", valid=False, status="INVALID_MODEL_OUTPUT"),
         None, None, "A_UNKNOWN_B_UNKNOWN"),
    ],
    ids=["script-a-illegal-b-legal", "script-both-legal", "script-b-worse", "no-valid-denominator"],
)
def test_scripted_cases_do_not_assume_b_wins(a, b, a_rate, b_rate, combination):
    summary = summarize([a, b], mode="offline", session_status="COMPLETED")
    pairs = paired_comparison([a, b])
    assert summary["by_condition"]["A_RAW"]["ratios"]["rule_rejection_rate"]["value"] == a_rate
    assert summary["by_condition"]["B_FEASIBLE"]["ratios"]["rule_rejection_rate"]["value"] == b_rate
    assert pairs[0]["start_combination"] == combination
    assert summary["MODEL_BENEFIT"] == "NOT_TESTED"
    assert summary["real_provider_requests"] == 0
    assert "OFFLINE_SYNTHETIC" in render_report(summary, pairs)


def test_stage_counts_are_observed_not_calls_minus_provider_failures():
    rows = [
        cell("A_RAW", valid=False, status="INVALID_MODEL_OUTPUT",
             strict_json_valid=False, catalog_valid=None),
        cell("B_FEASIBLE", valid=False, status="HTTP_ERROR",
             http_response_observed=True, service_contract_valid=False,
             strict_json_valid=None, catalog_valid=None),
        cell("A_RAW", pair="p002", valid=False, status="REQUEST_CANCELLED",
             http_response_observed=False, service_contract_valid=None,
             strict_json_valid=None, catalog_valid=None),
        cell("B_FEASIBLE", pair="p002", status="NOT_RUN",
             intent_registered=False, client_call_attempted=False),
    ]
    summary = summarize(rows, mode="offline", session_status="STOPPED")
    assert summary["counts"]["client_call_attempted"] == 3
    assert summary["counts"]["http_response_observed"] == 2
    assert summary["counts"]["service_contract_valid"] == 1
    assert summary["counts"]["valid_proposals"] == 0
    assert summary["stage_counts"]["strict_json_valid"] == {
        "true": 0, "false": 1, "unknown": 2, "not_run": 1,
    }
    assert summary["ratios"]["rule_rejection_rate"] == {
        "numerator": 0, "denominator": 0, "value": None,
    }


def test_outside_catalog_is_not_a_valid_proposal_or_rule_rejection():
    rows = [cell("A_RAW", accepted=False, status="OUTSIDE_CATALOG", catalog_valid=False),
            cell("B_FEASIBLE", accepted=False)]
    summary = summarize(rows, mode="offline", session_status="STOPPED")
    assert summary["counts"]["strict_json_valid"] == 2
    assert summary["counts"]["valid_proposals"] == 1
    assert summary["counts"]["outside_catalog"] == 1
    assert summary["counts"]["rule_rejected"] == 1
    assert summary["ratios"]["rule_rejection_rate"] == {
        "numerator": 1, "denominator": 1, "value": 1,
    }
    assert summary["pair_counts"]["incomplete_valid_proposals"] == 1


def test_token_missing_rows_are_not_zero_and_token_categories_are_separate():
    rows = [cell("A_RAW", input_tokens=None, output_tokens=4, reasoning_tokens=None),
            cell("B_FEASIBLE", input_tokens=12, output_tokens=None, reasoning_tokens=3)]
    summary = summarize(rows, mode="offline", session_status="COMPLETED", wall_seconds=2.5)
    costs = summary["costs"]
    assert costs["input_tokens"] == {
        "known_subtotal": 12, "known_rows": 1, "missing_rows": 1, "eligible_rows": 2,
        "coverage": {"numerator": 1, "denominator": 2, "value": 0.5},
    }
    assert costs["output_tokens"]["known_subtotal"] == 4
    assert costs["reasoning_tokens"]["known_subtotal"] == 3
    assert costs["token_fields_are_not_added_together"] is True
    assert summary["wall_seconds"] == 2.5
    assert costs["latency_seconds"]["known_subtotal"] == 0.02
    assert costs["simulation_minutes"]["known_subtotal"] == 30
    assert paired_comparison(rows)[0]["input_tokens_B_minus_A"] is None
    assert paired_comparison(rows)[0]["prompt_chars_B_minus_A"] == 100


def test_entirely_missing_cost_and_dry_not_run_remain_missing():
    row = cell("A_RAW", input_tokens=None, output_tokens=-1, reasoning_tokens=True)
    summary = summarize([row], mode="offline", session_status="COMPLETED")
    for key in ("input_tokens", "output_tokens", "reasoning_tokens"):
        assert summary["costs"][key]["known_subtotal"] is None
        assert summary["costs"][key]["missing_rows"] == 1
    dry = summarize([cell("A_RAW", status="NOT_RUN")], mode="dry-run", session_status="PLANNED")
    assert dry["counts"]["not_run"] == 1
    assert dry["counts"]["client_call_attempted"] == 0
    assert dry["costs"]["input_tokens"]["coverage"]["value"] is None
    assert dry["ratios"]["start_accepted_rate"]["value"] is None
    assert dry["by_scenario"]["s01"]["counts"]["valid_proposals"] == 0


def test_interrupted_intent_has_unknown_send_not_zero_real_requests():
    interrupted = cell("A_RAW", status="UNKNOWN", client_call_attempted=None,
                       http_response_observed=None, service_contract_valid=None,
                       strict_json_valid=None, catalog_valid=None, rule_checked=None,
                       start_accepted=None, activity_completed=None)
    summary = summarize([interrupted], mode="real", session_status="INTERRUPTED")
    assert summary["counts"]["intent_registered"] == 1
    assert summary["counts"]["intent_send_unknown"] == 1
    assert summary["counts"]["client_call_attempted"] == 0
    assert summary["real_provider_requests"] is None
    assert summary["costs"]["input_tokens"]["eligible_rows"] == 0
    assert summary["costs"]["unknown_send_intents_excluded_from_call_costs"] == 1


@pytest.mark.parametrize(("backend_a", "backend_b", "category"), [
    ("model-one", "model-one", "BACKEND_MATCH"),
    ("model-one", "model-two", "BACKEND_DIFFERENT"),
    (None, "model-one", "BACKEND_UNKNOWN"),
    ("sk-secret", "model-one", "BACKEND_UNKNOWN"),
])
def test_backend_comparability_does_not_invent_identity(backend_a, backend_b, category):
    rows = [cell("A_RAW", provider_model=backend_a), cell("B_FEASIBLE", provider_model=backend_b)]
    pairs = paired_comparison(rows)
    assert pairs[0]["backend_comparability"] == category
    assert pairs[0]["valid_proposal_pair_complete"] is True
    assert pairs[0]["comparable_scored_pair"] == (category == "BACKEND_MATCH")
    assert "provider_model" not in pairs[0]


def test_acceptance_is_distinct_from_activity_completion():
    rows = [cell("A_RAW", status="COMMITMENT_FAILED", activity_completed=False),
            cell("B_FEASIBLE")]
    summary = summarize(rows, mode="offline", session_status="COMPLETED")
    assert summary["ratios"]["start_accepted_rate"]["value"] == 1
    assert summary["ratios"]["activity_completed_rate"]["value"] == 0.5
    assert summary["counts"]["commitment_failed"] == 1
    assert paired_comparison(rows)[0]["start_combination"] == "A_ACCEPTED_B_ACCEPTED"


def test_invalid_pair_structure_and_unscored_valid_proposals_are_not_complete_scores():
    duplicate = [cell("A_RAW"), cell("A_RAW")]
    pair = paired_comparison(duplicate)[0]
    assert pair["pair_structure_valid"] is False
    assert pair["valid_proposal_pair_complete"] is False
    rows = [cell("A_RAW", status="EVIDENCE_INCOMPLETE", rule_checked=None,
                 start_accepted=None, activity_completed=None), cell("B_FEASIBLE")]
    pair = paired_comparison(rows)[0]
    assert pair["valid_proposal_pair_complete"] is True
    assert pair["scored_pair_complete"] is False


def test_all_48_allocated_cells_and_24_pairs_remain_in_coverage():
    rows = []
    for index in range(24):
        for condition in ("A_RAW", "B_FEASIBLE"):
            rows.append(cell(condition, pair=f"p{index + 1:03d}",
                             scenario_id=f"s{index // 2 + 1:02d}", repeat=index % 2 + 1,
                             status="NOT_RUN" if index > 0 else "DECISION_ACCEPTED"))
    summary = summarize(rows, mode="offline", session_status="STOPPED")
    assert summary["counts"]["planned"] == 48
    assert summary["counts"]["not_run"] == 46
    assert len(summary["by_scenario"]) == 12
    assert summary["pair_counts"]["planned"] == 24
    assert summary["pair_counts"]["complete_valid_proposals"] == 1
    assert summary["pair_counts"]["incomplete_valid_proposals"] == 23
    assert summary["ratios"]["completed_planned_rate"] == {
        "numerator": 2, "denominator": 48, "value": 2 / 48,
    }


def test_extra_strings_secret_sentinels_and_raw_provider_text_are_not_exported():
    sentinel = "DO_NOT_PERSIST_SECRET_SENTINEL"
    rows = [cell("A_RAW", status=sentinel, family=sentinel, scenario_id=sentinel,
                 pair_id=sentinel, provider_model=sentinel, requested_model=sentinel,
                 error_body=sentinel, completion=sentinel, prompt=sentinel,
                 hidden_reasoning=sentinel, target=sentinel, stop_reason=sentinel)]
    summary = summarize(rows, mode=sentinel, session_status=sentinel)
    pairs = paired_comparison(rows)
    exported = json.dumps([summary, pairs], ensure_ascii=False) + render_report(summary, pairs)
    assert sentinel not in exported
    assert summary["schema_version"] == SCHEMA_VERSION
    assert summary["contains_secret"] is False
    assert summary["STATE_FEEDBACK_VISIBLE"] == "NOT_APPLICABLE"
    assert summary["continuous_repeat_rate"] == "NOT_APPLICABLE"
    assert summary["long_term_continuity"] == "NOT_APPLICABLE"
    assert summary["SHORT_HORIZON_STATE_CONTINUITY"] == "INSUFFICIENT_EVIDENCE"
    assert "NOT_TESTED" in exported


@pytest.mark.parametrize("status", ["PANEL_COMPLETED", "RUNNING", "STOPPED_READ_ONLY_RECOVERY"])
def test_integrated_session_statuses_are_preserved(status):
    summary = summarize([], mode="offline", session_status=status)
    assert summary["session_status"] == status


def test_unknown_execution_failure_is_preserved_without_claiming_rule_rejection():
    summary = summarize([cell("A_RAW", status="UNKNOWN_EXECUTION_FAILURE",
                              activity_completed=False)],
                        mode="offline", session_status="UNKNOWN_EXECUTION_FAILURE")
    assert summary["status_counts"] == {"UNKNOWN_EXECUTION_FAILURE": 1}
    assert summary["counts"]["rule_rejected"] == 0
    assert summary["ratios"]["activity_completed_rate"]["value"] == 0
