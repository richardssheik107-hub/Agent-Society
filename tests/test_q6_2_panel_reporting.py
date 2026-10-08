"""Synthetic metric cases: these tests are not evidence of model benefit."""
from __future__ import annotations

import json

import pytest

from social_sim.continuity.q6_2_panel_reporting import (
    SCHEMA_VERSION,
    V2_PROTOCOL,
    V2_SCHEMA_VERSION,
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


def timeout_cell(condition, *, before=0, after=1, reason="SINGLE_TIMEOUT_LOCALLY_SETTLED_CONTINUE",
                 **extra):
    return cell(condition, valid=False, status="PROVIDER_TIMEOUT",
                strict_json_valid=None, catalog_valid=None, rule_checked=None,
                start_accepted=None, activity_completed=None, http_response_observed=False,
                service_contract_valid=None, provider_model=None,
                input_tokens=None, output_tokens=None, reasoning_tokens=None,
                timeout_streak_before=before, timeout_streak_after=after,
                continue_or_stop_reason=reason, local_call_settled=True,
                timeout_locally_safe=True, provider_requests=1, **extra)


def test_v2_second_timeout_keeps_cell_status_and_separate_session_termination():
    rows = [timeout_cell("A_RAW"), timeout_cell("B_FEASIBLE", before=1, after=2,
                                              reason="CONSECUTIVE_TIMEOUT_LIMIT")]
    summary = summarize(rows, mode="real", session_status="CONSECUTIVE_TIMEOUT_LIMIT",
                        protocol_version=V2_PROTOCOL, session_termination="CONSECUTIVE_TIMEOUT_LIMIT")
    assert summary["schema_version"] == V2_SCHEMA_VERSION
    assert summary["status_counts"] == {"PROVIDER_TIMEOUT": 2}
    assert summary["session_termination"] == "CONSECUTIVE_TIMEOUT_LIMIT"
    assert summary["timeout_summary"]["provider_timeout_count"] == 2
    assert summary["timeout_summary"]["single_timeout_continued_count"] == 1
    assert summary["timeout_summary"]["max_timeout_streak"] == 2
    assert summary["timeout_summary"]["by_condition"] == {"A_RAW": 1, "B_FEASIBLE": 1}
    assert summary["ratios"]["rule_rejection_rate"]["value"] is None
    assert summary["provider_request_evidence"]["known_subtotal"] == 2
    assert summary["MODEL_BENEFIT"] == "NOT_TESTED"


def test_v2_timeout_statistics_and_not_run_coverage_are_independent():
    rows = [timeout_cell("A_RAW"), cell("B_FEASIBLE", status="NOT_RUN")]
    summary = summarize(rows, mode="real", session_status="TIMEOUT_NOT_LOCALLY_SETTLED",
                        protocol_version="v2")
    assert summary["counts"]["not_run"] == 1
    assert summary["timeout_summary"]["provider_timeout_count"] == 1
    assert summary["costs"]["input_tokens"]["missing_rows"] == 1
    assert summary["actual_backend_distribution"] == {"UNKNOWN": 1}
    assert summary["pair_counts"]["incomplete_valid_proposals"] == 1


def test_v2_missing_streak_and_local_termination_are_not_invented():
    row = timeout_cell("A_RAW")
    row.update(timeout_streak_before=None, timeout_streak_after=None,
               local_call_settled=None, timeout_locally_safe=None,
               continue_or_stop_reason="TIMEOUT_EVIDENCE_INCOMPLETE")
    summary = summarize([row], mode="real", session_status="TIMEOUT_EVIDENCE_INCOMPLETE",
                        protocol_version="v2")
    data = summary["timeout_summary"]
    assert data["provider_timeout_count"] == 1
    assert data["max_timeout_streak"] is None
    assert data["streak_coverage"]["value"] == 0
    assert data["timeout_locally_safe"]["unknown"] == 1
    assert data["single_timeout_continued_count"] == 0
    assert data["server_receipt_or_billing_proven_by_local_settlement"] is False


def test_v2_primary_timeout_receipt_is_counted_with_unknown_client_entry():
    row = timeout_cell("A_RAW")
    row["client_call_attempted"] = None
    summary = summarize([row], mode="real", session_status="INTERRUPTED", protocol_version="v2")
    assert summary["timeout_summary"]["provider_timeout_count"] == 1
    assert summary["counts"]["client_call_attempted"] == 0
    assert summary["provider_request_evidence"]["unknown_intents"] == 1


def test_v2_cleanup_does_not_replace_primary_failure():
    summary = summarize([timeout_cell("A_RAW")], mode="real", session_status="PROVIDER_TIMEOUT",
                        protocol_version="v2", session_termination="PROVIDER_TIMEOUT",
                        cleanup_exception_type="TimeoutError", cleanup_outcome="FAIL")
    assert summary["session_status"] == "PROVIDER_TIMEOUT"
    assert summary["session_termination"] == "PROVIDER_TIMEOUT"
    assert summary["cleanup"] == {"outcome": "FAIL", "exception_type": "TimeoutError",
                                  "does_not_replace_primary_termination": True}


def test_v1_calls_and_reports_do_not_gain_v2_fields():
    rows = [cell("A_RAW"), cell("B_FEASIBLE")]
    old = summarize(rows, mode="offline", session_status="PANEL_COMPLETED")
    explicit = summarize(rows, mode="offline", session_status="PANEL_COMPLETED", protocol_version="v1")
    assert old == explicit
    assert old["schema_version"] == SCHEMA_VERSION
    assert "timeout_summary" not in old
    assert "action_distribution" not in old
    assert "completion_combination" not in paired_comparison(rows)[0]
    assert render_report(old, paired_comparison(rows)) == render_report(
        explicit, paired_comparison(rows, protocol_version="v1"))
    assert "v2 超时" not in render_report(old, paired_comparison(rows))


def test_v2_action_distribution_keeps_only_canonical_choices():
    rows = [cell("A_RAW", proposal_activity="MEAL", proposal_target="food_meal"),
            cell("B_FEASIBLE", proposal_activity="LEISURE", proposal_target=None),
            cell("B_FEASIBLE", pair="p002", proposal_activity="EVIL_SENTINEL",
                 proposal_target="EVIL_SENTINEL")]
    summary = summarize(rows, mode="offline", session_status="PANEL_COMPLETED", protocol_version="v2")
    assert summary["action_distribution"]["A_RAW"]["choices"] == [
        {"activity": "MEAL", "target": "food_meal", "count": 1}]
    assert summary["action_distribution"]["B_FEASIBLE"]["choices"] == [
        {"activity": "LEISURE", "target": "null", "count": 1},
        {"activity": "UNKNOWN", "target": "UNKNOWN", "count": 1}]
    assert "EVIL_SENTINEL" not in json.dumps(summary)


def test_v2_paired_differences_keep_all_and_backend_sensitivity_without_assuming_b_win():
    rows = [cell("A_RAW", accepted=False, input_tokens=10),
            cell("B_FEASIBLE", input_tokens=30),
            cell("A_RAW", pair="p002", provider_model="model-one", input_tokens=None),
            cell("B_FEASIBLE", pair="p002", accepted=False, provider_model="model-two")]
    pairs = paired_comparison(rows, protocol_version="v2")
    summary = summarize(rows, mode="offline", session_status="PANEL_COMPLETED", protocol_version="v2")
    assert pairs[0]["rule_rejection_B_minus_A"] == -1
    assert pairs[1]["rule_rejection_B_minus_A"] == 1
    assert pairs[0]["activity_completed_B_minus_A"] == 1
    assert pairs[1]["activity_completed_B_minus_A"] == -1
    all_pairs = summary["paired_descriptive"]["all_complete_scored"]
    matched = summary["paired_descriptive"]["backend_matched_complete_scored"]
    assert all_pairs["rule_rejection_B_minus_A"]["mean"] == 0
    assert all_pairs["activity_completed_B_minus_A"]["mean"] == 0
    assert all_pairs["input_tokens_B_minus_A"]["mean"] == 20
    assert all_pairs["input_tokens_B_minus_A"]["missing_pairs"] == 1
    assert matched["eligible_pairs"] == 1
    assert matched["rule_rejection_B_minus_A"]["mean"] == -1
    assert summary["actual_backend_distribution"] == {
        "model-one": 1, "model-two": 1, "offline-fake": 2}


def test_v2_pair_incomplete_reasons_and_safe_report_include_timeout_and_missing_cost():
    rows = [timeout_cell("A_RAW"), cell("B_FEASIBLE", status="NOT_RUN")]
    summary = summarize(rows, mode="real", session_status="PROVIDER_TIMEOUT", protocol_version="v2")
    pairs = paired_comparison(rows, protocol_version="v2")
    assert pairs[0]["incomplete_reasons"] == ["A_PROVIDER_TIMEOUT", "B_NOT_RUN"]
    assert pairs[0]["rule_rejection_B_minus_A"] is None
    text = render_report(summary, pairs)
    assert "Q6_2_FIXED_PANEL_METRICS_V2" in text
    assert "v2 超时" in text
    assert "不代表服务端没有收到" in text
    assert "客户端尝试及计数边界" in text
    assert "A_PROVIDER_TIMEOUT,B_NOT_RUN" in text


def test_v2_sensitive_optional_fields_are_not_copied():
    sentinel = "sk-SENSITIVE_SENTINEL"
    row = timeout_cell("A_RAW")
    row.update(continue_or_stop_reason=sentinel, provider_model=sentinel,
               proposal_activity=sentinel, proposal_target=sentinel)
    summary = summarize([row], mode="offline", session_status="STOPPED", protocol_version="v2",
                        session_termination=sentinel, cleanup_outcome=sentinel,
                        cleanup_exception_type=sentinel)
    exported = json.dumps(summary) + render_report(summary, paired_comparison([row], protocol_version="v2"))
    assert sentinel not in exported
    assert summary["session_termination"] == "UNKNOWN"
    assert summary["cleanup"]["exception_type"] == "OtherException"


@pytest.mark.parametrize(("counts", "expected"), [
    ([1, 1], 2), ([1, 0], 1), ([1, None], None), ([None, None], None),
])
def test_v2_exact_provider_count_requires_every_call_counter(counts, expected):
    rows = [cell("A_RAW", provider_requests=counts[0]),
            cell("B_FEASIBLE", provider_requests=counts[1])]
    summary = summarize(rows, mode="real", session_status="PANEL_COMPLETED", protocol_version="v2")
    assert summary["real_provider_requests"] == expected
    assert summary["provider_request_evidence"]["missing_call_rows"] == counts.count(None)
    assert summary["provider_request_evidence"]["server_receipt_proven"] is False
    assert summarize(rows, mode="real", session_status="PANEL_COMPLETED")["real_provider_requests"] is None


def test_v2_zero_provider_count_requires_no_unknown_send_intent():
    row = cell("A_RAW", status="UNKNOWN", client_call_attempted=None, intent_registered=True)
    unknown = summarize([row], mode="real", session_status="INTERRUPTED", protocol_version="v2")
    assert unknown["counts"]["client_call_attempted"] == 0
    assert unknown["provider_request_evidence"]["unknown_intents"] == 1
    assert unknown["real_provider_requests"] is None
    empty = summarize([], mode="real", session_status="PLANNED", protocol_version="v2")
    assert empty["real_provider_requests"] == 0
    planned = summarize([cell("A_RAW", status="NOT_RUN", intent_registered=False)],
                        mode="real", session_status="NOT_RUN", protocol_version="v2")
    assert planned["real_provider_requests"] == 0


def test_v2_known_counts_are_still_inexact_with_additional_unknown_intent():
    rows = [cell("A_RAW", provider_requests=1),
            cell("B_FEASIBLE", status="UNKNOWN", client_call_attempted=None, intent_registered=True)]
    summary = summarize(rows, mode="real", session_status="INTERRUPTED", protocol_version="v2")
    assert summary["provider_request_evidence"]["known_subtotal"] == 1
    assert summary["provider_request_evidence"]["missing_call_rows"] == 0
    assert summary["provider_request_evidence"]["unknown_intents"] == 1
    assert summary["real_provider_requests"] is None


def test_v2_not_locally_settled_cleanup_is_retained_without_replacing_failure():
    summary = summarize([timeout_cell("A_RAW")], mode="real", session_status="PROVIDER_TIMEOUT",
                        protocol_version="v2", session_termination="TIMEOUT_NOT_LOCALLY_SETTLED",
                        cleanup_outcome="NOT_LOCALLY_SETTLED", cleanup_exception_type="TimeoutError")
    assert summary["cleanup"]["outcome"] == "NOT_LOCALLY_SETTLED"
    assert summary["session_termination"] == "TIMEOUT_NOT_LOCALLY_SETTLED"
    assert summary["status_counts"] == {"PROVIDER_TIMEOUT": 1}
