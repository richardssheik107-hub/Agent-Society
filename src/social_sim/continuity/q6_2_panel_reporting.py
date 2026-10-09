"""Versioned, evidence-based metrics for the independent fixed-state panel.

This module never executes an action or creates a provider client.  Only explicit
stage evidence is counted; absent evidence is not converted into a failure, a
success, or zero token cost.  Model-generated text is deliberately not exported.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter, defaultdict
from typing import Any

from social_sim.provider_runtime.safety import EXCEPTION_TYPES

from .models import TIMED_ACTIVITIES

SCHEMA_VERSION = "Q6_2_FIXED_PANEL_METRICS_V1"
V2_SCHEMA_VERSION = "Q6_2_FIXED_PANEL_METRICS_V2"
CONDITIONS = ("A_RAW", "B_FEASIBLE")
FAMILIES = frozenset({
    "OWNERSHIP", "POST_MEAL_NEED", "MEDIA_PROGRESS", "ACTIVITY_LOCATION",
    "MEAL_PAYMENT", "MEAL_SUPPLY",
})
STATUSES = frozenset({
    "NOT_RUN", "UNKNOWN", "DECISION_ACCEPTED", "RULE_REJECTED", "COMMITMENT_FAILED",
    "HTTP_ERROR", "TRANSPORT_ERROR", "PROVIDER_TIMEOUT", "PROVIDER_ERROR",
    "PROVIDER_CONTRACT_ERROR", "PROVIDER_REFUSAL", "PROVIDER_SCHEMA_MISMATCH",
    "NO_CHOICES", "EMPTY_FINAL_CONTENT", "EMPTY_FINAL_CONTENT_WITH_REASONING",
    "TOOL_CALL_INSTEAD_OF_TEXT", "OUTPUT_BUDGET_EXHAUSTED", "INVALID_MODEL_OUTPUT",
    "OUTSIDE_CATALOG", "REQUEST_CANCELLED", "ARCHITECTURE_ERROR",
    "STATE_INVARIANT_FAILED", "EVIDENCE_INCOMPLETE", "REQUEST_BUDGET_EXHAUSTED",
    "EXECUTION_LIMIT_EXCEEDED", "UNKNOWN_EXECUTION_FAILURE",
})
SESSION_STATUSES = STATUSES | {
    "PLANNED", "DRY_RUN", "COMPLETED", "STOPPED", "INTERRUPTED", "RECOVERED",
    "OFFLINE_SYNTHETIC", "BUDGET_COMPLETED", "EXECUTED", "PREPARED",
    "PANEL_COMPLETED", "RUNNING", "STOPPED_READ_ONLY_RECOVERY",
    "CONSECUTIVE_TIMEOUT_LIMIT", "TIMEOUT_NOT_LOCALLY_SETTLED",
    "TIMEOUT_EVIDENCE_INCOMPLETE", "LOCAL_CALL_NOT_SETTLED",
}
STAGES = (
    "intent_registered", "client_call_attempted", "http_response_observed",
    "service_contract_valid", "strict_json_valid", "catalog_valid", "rule_checked",
    "start_accepted", "activity_completed", "invariants_valid",
)
TOKEN_FIELDS = ("input_tokens", "output_tokens", "reasoning_tokens")
V2_PROTOCOL = "q62_fixed_state_panel_v2"
CONTINUE_REASONS = frozenset({
    "CONTINUE_NORMAL_RESULT", "SINGLE_TIMEOUT_LOCALLY_SETTLED_CONTINUE",
    "CONSECUTIVE_TIMEOUT_LIMIT", "TIMEOUT_NOT_LOCALLY_SETTLED",
    "TIMEOUT_EVIDENCE_INCOMPLETE", "STOP_FATAL", "LOCAL_CALL_NOT_SETTLED",
}) | SESSION_STATUSES
SAFE_TARGETS = frozenset({
    "food_bread", "food_meal", "game_a", "series_a", "home", "restaurant", "office", "park",
})


def _status(row: dict) -> str:
    value = row.get("status")
    return value if isinstance(value, str) and value in STATUSES else "UNKNOWN"


def _id(value: object, kind: str) -> str:
    patterns = {"cell": r"c[0-9]{3}", "pair": r"p[0-9]{3}", "scenario": r"s[0-9]{2}"}
    if isinstance(value, str) and re.fullmatch(patterns[kind], value):
        return value
    # Unknown metadata is grouped without ever retaining its original text.
    encoded = str(value).encode("utf-8")
    return "UNKNOWN_" + hashlib.sha256(encoded).hexdigest()[:12]


def _family(value: object) -> str:
    return value if isinstance(value, str) and value in FAMILIES else "UNKNOWN"


def _number(value: object, *, integer: bool = False) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if ((isinstance(value, float) and not math.isfinite(value))
            or value < 0 or (integer and not isinstance(value, int))):
        return None
    return value


def _flag(row: dict, key: str) -> bool | None:
    if _status(row) == "NOT_RUN":
        return None
    value = row.get(key)
    return value if isinstance(value, bool) else None


def _valid(row: dict) -> bool | None:
    strict, catalog = _flag(row, "strict_json_valid"), _flag(row, "catalog_valid")
    if strict is False or catalog is False:
        return False
    return True if strict is True and catalog is True else None


def _ratio(numerator: int, denominator: int) -> dict:
    return {"numerator": numerator, "denominator": denominator,
            "value": numerator / denominator if denominator else None}


def _stage(rows: list[dict], key: str) -> dict:
    active = [row for row in rows if _status(row) != "NOT_RUN"]
    return {
        "true": sum(_flag(row, key) is True for row in active),
        "false": sum(_flag(row, key) is False for row in active),
        "unknown": sum(_flag(row, key) is None for row in active),
        "not_run": len(rows) - len(active),
    }


def _cost(rows: list[dict], key: str, *, integer: bool = False) -> dict:
    values = [_number(row.get(key), integer=integer) for row in rows]
    known = [value for value in values if value is not None]
    return {
        "known_subtotal": sum(known) if known else None,
        "known_rows": len(known), "missing_rows": len(rows) - len(known),
        "eligible_rows": len(rows), "coverage": _ratio(len(known), len(rows)),
    }


def _aggregate(rows: list[dict]) -> dict:
    stages = {key: _stage(rows, key) for key in STAGES}
    valid = [row for row in rows if _valid(row) is True]
    feasibility = [row for row in valid
                   if isinstance(_flag(row, "proposal_in_feasible_set"), bool)]
    calls = [row for row in rows if _flag(row, "client_call_attempted") is True]
    active = [row for row in rows if _status(row) != "NOT_RUN"]
    known_invariants = [row for row in active
                        if isinstance(_flag(row, "invariants_valid"), bool)]
    rejected = sum(_status(row) == "RULE_REJECTED" for row in valid)
    accepted = sum(_flag(row, "start_accepted") is True for row in valid)
    completed = sum(_flag(row, "activity_completed") is True for row in valid)
    counts = {key: stages[key]["true"] for key in STAGES}
    counts.update(
        planned=len(rows), valid_proposals=len(valid),
        rule_rejected=sum(_status(row) == "RULE_REJECTED" for row in rows),
        commitment_failed=sum(_status(row) == "COMMITMENT_FAILED" for row in rows),
        outside_catalog=sum(_status(row) == "OUTSIDE_CATALOG" for row in rows),
        not_run=len(rows) - len(active), unknown=sum(_status(row) == "UNKNOWN" for row in rows),
        valid_proposal_unknown=sum(_valid(row) is None for row in active),
        intent_send_unknown=sum(_flag(row, "intent_registered") is True
                                and _flag(row, "client_call_attempted") is None for row in rows),
    )
    rates = {
        "rule_rejection_rate": _ratio(rejected, len(valid)),
        "proposal_in_feasible_set_rate": _ratio(
            sum(_flag(row, "proposal_in_feasible_set") is True for row in feasibility),
            len(feasibility)),
        "start_accepted_rate": _ratio(accepted, len(valid)),
        "activity_completed_rate": _ratio(completed, len(valid)),
        "completed_planned_rate": _ratio(completed, len(rows)),
        "invariants_valid_rate": _ratio(
            sum(_flag(row, "invariants_valid") is True for row in known_invariants),
            len(known_invariants)),
    }
    for key, denominator in (
        ("http_response_observed", "client_call_attempted"),
        ("service_contract_valid", "http_response_observed"),
        ("strict_json_valid", "service_contract_valid"),
        ("catalog_valid", "strict_json_valid"),
    ):
        eligible = [row for row in rows if _flag(row, denominator) is True]
        rates[key + "_rate"] = _ratio(
            sum(_flag(row, key) is True for row in eligible), len(eligible))
    return {
        "counts": counts, "stage_counts": stages,
        "status_counts": dict(sorted(Counter(_status(row) for row in rows).items())),
        "ratios": rates,
        "missing_evidence": {
            "feasible_membership_for_valid_proposals": len(valid) - len(feasibility),
            "invariants_for_run_rows": len(active) - len(known_invariants),
        },
        "costs": {
            **{key: _cost(calls, key, integer=True) for key in TOKEN_FIELDS},
            "prompt_chars": _cost(rows, "prompt_chars", integer=True),
            "latency_seconds": _cost(calls, "latency_seconds"),
            "simulation_minutes": _cost(active, "simulation_minutes"),
            "unknown_send_intents_excluded_from_call_costs": counts["intent_send_unknown"],
            "token_fields_are_not_added_together": True,
        },
    }


def _backend(value: object) -> str | None:
    # Compare identity without returning a provider-originated arbitrary string.
    if (isinstance(value, str) and not value.startswith(("sk-", "ark-"))
            and re.fullmatch(r"[A-Za-z0-9_.:/-]{1,80}", value)):
        return value
    return None


def _outcome(row: dict | None) -> str:
    if row is None or _status(row) == "NOT_RUN":
        return "NOT_RUN"
    if _valid(row) is not True or _flag(row, "rule_checked") is not True:
        return "UNKNOWN"
    if _status(row) == "RULE_REJECTED":
        return "REJECTED"
    if _flag(row, "start_accepted") is True:
        return "ACCEPTED"
    return "UNKNOWN"


def paired_comparison(cells: list[dict], *, protocol_version: str | None = None) -> list[dict]:
    """Report all planned pairs, including incomplete and backend-unknown pairs."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in cells:
        grouped[_id(row.get("pair_id"), "pair")].append(row)
    pairs = []
    for pair_id, rows in sorted(grouped.items()):
        arms = {condition: [row for row in rows if row.get("condition") == condition]
                for condition in CONDITIONS}
        structure = len(rows) == 2 and all(len(arms[key]) == 1 for key in CONDITIONS)
        a = arms["A_RAW"][0] if len(arms["A_RAW"]) == 1 else None
        b = arms["B_FEASIBLE"][0] if len(arms["B_FEASIBLE"]) == 1 else None
        backend_a = _backend(a.get("provider_model")) if a and _status(a) != "NOT_RUN" else None
        backend_b = _backend(b.get("provider_model")) if b and _status(b) != "NOT_RUN" else None
        backend = "BACKEND_UNKNOWN"
        if backend_a is not None and backend_b is not None:
            backend = "BACKEND_MATCH" if backend_a == backend_b else "BACKEND_DIFFERENT"
        outcome_a, outcome_b = _outcome(a), _outcome(b)
        complete = structure and _valid(a) is True and _valid(b) is True
        scored = complete and outcome_a in {"ACCEPTED", "REJECTED"} and (
            outcome_b in {"ACCEPTED", "REJECTED"})
        metadata_equal = structure and all(
            a.get(key) == b.get(key) for key in ("scenario_id", "family", "repeat"))
        row = {
            "pair_id": pair_id,
            "scenario_id": _id(rows[0].get("scenario_id"), "scenario"),
            "family": _family(rows[0].get("family")),
            "repeat": (rows[0].get("repeat") if type(rows[0].get("repeat")) is int
                       and rows[0].get("repeat") in (1, 2) else None),
            "pair_structure_valid": structure and metadata_equal,
            "a_status": _status(a) if a else "NOT_RUN",
            "b_status": _status(b) if b else "NOT_RUN",
            "a_valid_proposal": _valid(a) if a else None,
            "b_valid_proposal": _valid(b) if b else None,
            "valid_proposal_pair_complete": complete and metadata_equal,
            "scored_pair_complete": scored and metadata_equal,
            "start_combination": f"A_{outcome_a}_B_{outcome_b}",
            "a_activity_completed": _flag(a, "activity_completed") if a else None,
            "b_activity_completed": _flag(b, "activity_completed") if b else None,
            "backend_comparability": backend,
            "comparable_scored_pair": scored and metadata_equal and backend == "BACKEND_MATCH",
            "requested_alias_matches": (
                _backend(a.get("requested_model")) == _backend(b.get("requested_model"))
                if a and b and _backend(a.get("requested_model")) is not None
                and _backend(b.get("requested_model")) is not None else None),
        }
        for key in ("prompt_chars", *TOKEN_FIELDS, "latency_seconds"):
            av = _number(a.get(key), integer=key != "latency_seconds") if a else None
            bv = _number(b.get(key), integer=key != "latency_seconds") if b else None
            row[key + "_B_minus_A"] = bv - av if av is not None and bv is not None else None
        if protocol_version in {V2_PROTOCOL, "v2"}:
            completion_a = _flag(a, "activity_completed") if a else None
            completion_b = _flag(b, "activity_completed") if b else None
            labels = {True: "COMPLETED", False: "NOT_COMPLETED", None: "UNKNOWN"}
            row.update(
                completion_combination=f"A_{labels[completion_a]}_B_{labels[completion_b]}",
                rule_rejection_B_minus_A=(int(outcome_b == "REJECTED")
                                         - int(outcome_a == "REJECTED") if scored else None),
                activity_completed_B_minus_A=(int(completion_b) - int(completion_a)
                    if scored and completion_a is not None and completion_b is not None else None),
            )
            reasons = []
            if not row["pair_structure_valid"]:
                reasons.append("PAIR_STRUCTURE_INVALID")
            for label, arm in (("A", a), ("B", b)):
                if arm is None or _status(arm) == "NOT_RUN":
                    reasons.append(label + "_NOT_RUN")
                elif _valid(arm) is not True:
                    reasons.append(label + "_" + _status(arm))
                elif _outcome(arm) == "UNKNOWN":
                    reasons.append(label + "_RULE_RESULT_UNKNOWN")
            row["incomplete_reasons"] = reasons
        pairs.append(row)
    return pairs


def summarize(cells: list[dict], *, mode: str, session_status: str,
              wall_seconds: float | None = None, protocol_version: str | None = None,
              session_termination: str | None = None, cleanup_exception_type: str | None = None,
              cleanup_outcome: str | None = None) -> dict[str, Any]:
    """Summarize recorded facts, not ``calls minus failures`` or answer labels."""
    modes = {"dry-run": "DRY_RUN", "offline": "OFFLINE_SYNTHETIC", "real": "REAL_PROVIDER",
             "DRY_RUN": "DRY_RUN", "OFFLINE_SYNTHETIC": "OFFLINE_SYNTHETIC",
             "REAL_PROVIDER": "REAL_PROVIDER", "REAL_PROVIDER_PANEL": "REAL_PROVIDER"}
    safe_mode = modes.get(mode, "UNKNOWN")
    safe_session = session_status if session_status in SESSION_STATUSES else "UNKNOWN"
    pairs = paired_comparison(cells, protocol_version=protocol_version)
    grouped = {}
    for key, sanitizer in (("scenario_id", lambda value: _id(value, "scenario")),
                           ("family", _family)):
        groups: dict[str, list[dict]] = defaultdict(list)
        for row in cells:
            groups[sanitizer(row.get(key))].append(row)
        grouped[key] = {name: _aggregate(rows) for name, rows in sorted(groups.items())}
    summary = {
        "schema_version": SCHEMA_VERSION, "mode": safe_mode, "session_status": safe_session,
        "valid_proposal_definition": "strict_json_valid IS TRUE AND catalog_valid IS TRUE",
        **_aggregate(cells),
        "by_condition": {key: _aggregate([row for row in cells if row.get("condition") == key])
                         for key in CONDITIONS},
        "by_scenario": grouped["scenario_id"], "by_family": grouped["family"],
        "pair_counts": {
            "planned": len(pairs),
            "complete_valid_proposals": sum(p["valid_proposal_pair_complete"] for p in pairs),
            "incomplete_valid_proposals": sum(not p["valid_proposal_pair_complete"] for p in pairs),
            "complete_scored": sum(p["scored_pair_complete"] for p in pairs),
            "backend_match": sum(p["backend_comparability"] == "BACKEND_MATCH" for p in pairs),
            "backend_different": sum(p["backend_comparability"] == "BACKEND_DIFFERENT"
                                     for p in pairs),
            "backend_unknown": sum(p["backend_comparability"] == "BACKEND_UNKNOWN" for p in pairs),
            "comparable_scored": sum(p["comparable_scored_pair"] for p in pairs),
            "combinations": dict(sorted(Counter(
                p["start_combination"] for p in pairs if p["scored_pair_complete"]).items())),
        },
        "wall_seconds": _number(wall_seconds),
        "real_provider_requests": 0 if safe_mode in {"DRY_RUN", "OFFLINE_SYNTHETIC"} else None,
        "MODEL_BENEFIT": "NOT_TESTED",
        "SHORT_HORIZON_STATE_CONTINUITY": "INSUFFICIENT_EVIDENCE",
        "STATE_FEEDBACK_VISIBLE": "NOT_APPLICABLE",
        "continuous_repeat_rate": "NOT_APPLICABLE",
        "long_term_continuity": "NOT_APPLICABLE",
        "human_accuracy": "NOT_APPLICABLE",
        "contains_secret": False,
    }
    if protocol_version in {V2_PROTOCOL, "v2"}:
        summary.update(_v2_extension(cells, pairs, session_termination or safe_session,
                                     cleanup_exception_type, cleanup_outcome))
        summary["schema_version"] = V2_SCHEMA_VERSION
        summary["protocol_version"] = V2_PROTOCOL
        if safe_mode == "REAL_PROVIDER":
            evidence = summary["provider_request_evidence"]
            # Exact only at the durable client-counter boundary, never server receipt.
            if evidence["missing_call_rows"] == 0 and evidence["unknown_intents"] == 0:
                summary["real_provider_requests"] = (
                    evidence["known_subtotal"] if evidence["known_call_rows"] else 0)
    return summary


def _timeout_summary(rows: list[dict]) -> dict:
    calls = [row for row in rows if _flag(row, "client_call_attempted") is True]
    # Primary timeout receipts survive even when call-entry evidence is unknown.
    timeouts = [row for row in rows if _status(row) == "PROVIDER_TIMEOUT"]
    streaks = [_number(row.get("timeout_streak_after"), integer=True) for row in calls]
    known_streaks = [value for value in streaks if value is not None]
    audit = []
    for row in calls:
        reason = row.get("continue_or_stop_reason")
        audit.append({
            "cell_id": _id(row.get("cell_id"), "cell"), "status": _status(row),
            "timeout_streak_before": _number(row.get("timeout_streak_before"), integer=True),
            "timeout_streak_after": _number(row.get("timeout_streak_after"), integer=True),
            "continue_or_stop_reason": (reason if isinstance(reason, str)
                                        and reason in CONTINUE_REASONS else "UNKNOWN"),
            "local_call_settled": _flag(row, "local_call_settled"),
            "timeout_locally_safe": _flag(row, "timeout_locally_safe"),
        })
    return {
        "provider_timeout_count": len(timeouts),
        "single_timeout_continued_count": sum(
            row.get("continue_or_stop_reason") == "SINGLE_TIMEOUT_LOCALLY_SETTLED_CONTINUE"
            and _flag(row, "timeout_locally_safe") is True for row in timeouts),
        "max_timeout_streak": max(known_streaks) if known_streaks else None,
        "streak_coverage": _ratio(len(known_streaks), len(calls)),
        "local_call_settled": _stage(calls, "local_call_settled"),
        "timeout_locally_safe": _stage(timeouts, "timeout_locally_safe"),
        "by_condition": {condition: sum(row.get("condition") == condition for row in timeouts)
                         for condition in CONDITIONS},
        "call_audit": audit,
        "server_receipt_or_billing_proven_by_local_settlement": False,
    }


def _action_distribution(rows: list[dict]) -> dict:
    counts = Counter()
    valid = [row for row in rows if _valid(row) is True]
    for row in valid:
        activity = row.get("proposal_activity")
        if (not isinstance(activity, str)
                or activity not in {*TIMED_ACTIVITIES, "MEAL", "WATCH", "PLAY", "TRAVEL"}):
            activity = "UNKNOWN"
        target = row.get("proposal_target")
        target = ("null" if target is None else target
                  if isinstance(target, str) and target in SAFE_TARGETS else "UNKNOWN")
        counts[(activity, target)] += 1
    return {"eligible_valid_proposals": len(valid), "choices": [
        {"activity": activity, "target": target, "count": count}
        for (activity, target), count in sorted(counts.items())]}


def _paired_descriptive(pairs: list[dict]) -> dict:
    result = {}
    for group, eligible in (
        ("all_complete_scored", [pair for pair in pairs if pair["scored_pair_complete"]]),
        ("backend_matched_complete_scored", [pair for pair in pairs
                                             if pair["comparable_scored_pair"]]),
    ):
        values = {"eligible_pairs": len(eligible)}
        for field in ("rule_rejection_B_minus_A", "activity_completed_B_minus_A",
                      "input_tokens_B_minus_A"):
            known = [pair[field] for pair in eligible if pair.get(field) is not None]
            values[field] = {
                "known_pairs": len(known), "missing_pairs": len(eligible) - len(known),
                "known_subtotal": sum(known) if known else None,
                "mean": sum(known) / len(known) if known else None,
                "coverage": _ratio(len(known), len(eligible)),
            }
        values["completion_combinations"] = dict(sorted(Counter(
            pair["completion_combination"] for pair in eligible).items()))
        result[group] = values
    return result


def _v2_extension(cells: list[dict], pairs: list[dict], termination: str,
                  cleanup_exception_type: str | None, cleanup_outcome: str | None) -> dict:
    calls = [row for row in cells if _flag(row, "client_call_attempted") is True]
    backend_groups: dict[str, list[dict]] = defaultdict(list)
    for row in calls:
        backend_groups[_backend(row.get("provider_model")) or "UNKNOWN"].append(row)
    known_provider = [_number(row.get("provider_requests"), integer=True) for row in calls]
    known_counts = [value for value in known_provider if value is not None]
    unknown_intents = sum(_flag(row, "intent_registered") is True
                          and _flag(row, "client_call_attempted") is None for row in cells)
    return {
        "session_termination": termination if termination in SESSION_STATUSES else "UNKNOWN",
        "cleanup": {
            "outcome": cleanup_outcome if cleanup_outcome in {
                "PASS", "FAIL", "CLOSED", "FAILED", "NOT_REQUIRED", "UNKNOWN",
                "NOT_LOCALLY_SETTLED"} else "UNKNOWN",
            "exception_type": (cleanup_exception_type if cleanup_exception_type in EXCEPTION_TYPES
                               else "OtherException" if cleanup_exception_type else None),
            "does_not_replace_primary_termination": True,
        },
        "timeout_summary": _timeout_summary(cells),
        "provider_request_evidence": {
            "known_subtotal": sum(known_counts) if known_counts else None,
            "known_call_rows": len(known_counts), "missing_call_rows": len(calls) - len(known_counts),
            "unknown_intents": unknown_intents,
            "server_receipt_proven": False,
        },
        "actual_backend_distribution": {name: len(rows)
                                        for name, rows in sorted(backend_groups.items())},
        "by_actual_backend": {name: _aggregate(rows)
                              for name, rows in sorted(backend_groups.items())},
        "action_distribution": {condition: _action_distribution(
            [row for row in cells if row.get("condition") == condition]) for condition in CONDITIONS},
        "paired_descriptive": _paired_descriptive(pairs),
    }


def _format_ratio(value: dict) -> str:
    rate = value.get("value")
    display = "null（无有效分母）" if rate is None else f"{rate:.3f}"
    return f"{value['numerator']}/{value['denominator']} = {display}"


def render_report(summary: dict, pairs: list[dict]) -> str:
    """Render the safe summary; never interpolate raw rows or provider messages."""
    lines = [
        "# Q6.2 固定状态配对面板报告", "",
        f"统计口径：`{summary.get('schema_version', SCHEMA_VERSION)}`。",
        "研究问题：在完全相同初态下，额外展示现行规则可执行的 activity/target 候选，"
        "是否减少不可执行提案，增加多少上下文成本？",
        "唯一干预：A_RAW 原提示不变；B_FEASIBLE 仅增加既有 executable_options 与选择说明。"
        "规则、所有权、对象目录、需求、模型契约均不随臂改变。", "",
        f"模式：`{summary['mode']}`；session 状态：`{summary['session_status']}`。",
        "`OFFLINE_SYNTHETIC` 仅为 fake provider 脚本验证，不能解释为真实模型行为或收益。",
        "所有权、餐后需求、媒体进度、地点、支付能力与库存各含两状态；每状态均保留合法选择。"
        "这些是覆盖条件，不是模型标准答案，不因为连续吃饭而判错。", "",
        "## 覆盖与阶段证据", "",
        "有效提案：严格 JSON 合法且目录合法。OUTSIDE_CATALOG 单列，不纳入规则拒绝分子。",
        "缺失字段为 UNKNOWN，未运行单元为 NOT_RUN；不会用调用数减失败数推算成功。", "",
        "|阶段|已观测真|已观测假|未知|未运行|", "|---|---:|---:|---:|---:|",
    ]
    for key in STAGES:
        values = summary["stage_counts"][key]
        lines.append(f"|{key}|{values['true']}|{values['false']}|"
                     f"{values['unknown']}|{values['not_run']}|")
    counts = summary["counts"]
    lines.extend([
        "", f"计划 {counts['planned']} 单元；有效提案 {counts['valid_proposals']}；"
        f"规则拒绝 {counts['rule_rejected']}；活动失败 {counts['commitment_failed']}；"
        f"目录外输出 {counts['outside_catalog']}；NOT_RUN {counts['not_run']}；"
        f"UNKNOWN {counts['unknown']}。", "",
        "|逐单元终态|数量|", "|---|---:|",
    ])
    for status, count in summary["status_counts"].items():
        lines.append(f"|{status}|{count}|")
    lines.extend([
        "", "## 比较与成本", "", "|条件|规则拒绝/有效提案|启动接受/有效提案|活动完成/有效提案|",
        "|---|---|---|---|",
    ])
    for condition in CONDITIONS:
        ratios = summary["by_condition"][condition]["ratios"]
        lines.append(f"|{condition}|{_format_ratio(ratios['rule_rejection_rate'])}|"
                     f"{_format_ratio(ratios['start_accepted_rate'])}|"
                     f"{_format_ratio(ratios['activity_completed_rate'])}|")
    lines.extend([
        "", "提案在可执行集合比例："
        + _format_ratio(summary["ratios"]["proposal_in_feasible_set_rate"]) + "。",
        "世界不变量有效比例（仅已知检查）："
        + _format_ratio(summary["ratios"]["invariants_valid_rate"]) + "。",
        "活动完成 / 全部计划："
        + _format_ratio(summary["ratios"]["completed_planned_rate"]) + "。",
    ])
    lines.extend(["", "token 只报告已知小计（known subtotal）、缺失行数与覆盖率，"
                  "不把输入、输出、reasoning 相加；无证据不当作零成本。", "",
                  "|成本字段|已知小计|缺失行|覆盖率|", "|---|---:|---:|---|"])
    for key in (*TOKEN_FIELDS, "prompt_chars", "latency_seconds", "simulation_minutes"):
        cost = summary["costs"][key]
        lines.append(f"|{key}|{cost['known_subtotal']}|{cost['missing_rows']}|"
                     f"{_format_ratio(cost['coverage'])}|")
    lines.extend(["", f"整轮墙钟时间：{summary['wall_seconds']} 秒。调用耗时与活动仿真分钟分别列示。",
                  "请求意图登记但发送未知的单元单列，不冒充 0 请求，也不补跑。", "",
                  "## 配对覆盖", "", "|配对|状态|A/B有效提案|接受/拒绝组合|后端可比性|",
                  "|---|---|---|---|---|"])
    for pair in pairs:
        lines.append(f"|{pair['pair_id']}|{pair['scenario_id']}|"
                     f"{pair['a_valid_proposal']}/{pair['b_valid_proposal']}|"
                     f"{pair['start_combination']}|{pair['backend_comparability']}|")
    pc = summary["pair_counts"]
    lines.extend(["", f"计划 {pc['planned']} 对；有效提案完整 {pc['complete_valid_proposals']} 对；"
                  f"不完整 {pc['incomplete_valid_proposals']} 对；可评分 {pc['complete_scored']} 对；"
                  f"同后端且可评分 {pc['comparable_scored']} 对。",
                  "失败停止导致剩余单元 NOT_RUN；完整配对与全部分配覆盖同时报告。"
                  "后端未知或不同不能假定同模型，也不会为凑同后端重跑。",
                  "24 配对来自 12 状态的两次重复，不是 24 个独立人群，不强加显著性检验。", "",
                  "## 状态与家族", "", "|分组|计划|有效提案|规则拒绝|活动完成|",
                  "|---|---:|---:|---:|---:|"])
    for group in ("by_scenario", "by_family"):
        for name, values in summary[group].items():
            c = values["counts"]
            lines.append(f"|{name}|{c['planned']}|{c['valid_proposals']}|"
                         f"{c['rule_rejected']}|{c['activity_completed']}|")
    lines.extend(["", "## 解释边界", "",
                  "未来真实结果允许无差异、B 更差或覆盖不足；脚本场景不内置 B 必胜。"
                  "活动评分来自真实规则执行而非候选成员身份。规则拒绝可继续，fatal 错误停止全轮；"
                  "失败之前合法发生的旅行等效果保留。",
                  "每个单元仅一次高层决策，STATE_FEEDBACK_VISIBLE、连续重复率、长期连续性均为 "
                  "NOT_APPLICABLE。面板没有真人标签，不能推出长期真人行为、真人正确率或人类相似性。",
                  "`MODEL_BENEFIT = NOT_TESTED`；"
                  "`SHORT_HORIZON_STATE_CONTINUITY = INSUFFICIENT_EVIDENCE`。", ""])
    if summary.get("protocol_version") == V2_PROTOCOL:
        lines.extend(_v2_report_lines(summary, pairs))
    return "\n".join(lines)


def _v2_report_lines(summary: dict, pairs: list[dict]) -> list[str]:
    timeouts, cleanup = summary["timeout_summary"], summary["cleanup"]
    lines = [
        "## v2 超时、收尾与结果描述", "",
        f"协议：`{V2_PROTOCOL}`；原 session 终止原因：`{summary['session_termination']}`。",
        f"超时 {timeouts['provider_timeout_count']}；单次安全超时后继续 "
        f"{timeouts['single_timeout_continued_count']}；最大已知连续超时 "
        f"{timeouts['max_timeout_streak']}。",
        "安全超时只结束原单元并占用预算，不重发。连续两次超时停止全轮；"
        "本地调用安全终结不代表服务端没有收到、计费或完成请求。",
        f"cleanup：`{cleanup['outcome']}`；安全异常类型：`{cleanup['exception_type']}`。"
        "收尾失败不覆盖首个停止原因。", "",
        "|调用单元|原状态|streak 前/后|本地已终结|超时可安全继续|继续/停止原因|",
        "|---|---|---|---|---|---|",
    ]
    for row in timeouts["call_audit"]:
        lines.append(f"|{row['cell_id']}|{row['status']}|"
                     f"{row['timeout_streak_before']}/{row['timeout_streak_after']}|"
                     f"{row['local_call_settled']}|{row['timeout_locally_safe']}|"
                     f"{row['continue_or_stop_reason']}|")
    evidence = summary["provider_request_evidence"]
    lines.extend([
        "", f"请求计数证据：已知小计 {evidence['known_subtotal']}；"
        f"调用行缺失 {evidence['missing_call_rows']}；登记但发送未知 {evidence['unknown_intents']}。"
        "客户端尝试及计数边界不是服务端必然收到的证明。", "",
        "|实际后端|调用行数|", "|---|---:|",
    ])
    for backend, count in summary["actual_backend_distribution"].items():
        lines.append(f"|{backend}|{count}|")
    lines.extend(["", "|条件|activity|target|有效提案次数|", "|---|---|---|---:|"])
    for condition, distribution in summary["action_distribution"].items():
        for row in distribution["choices"]:
            lines.append(f"|{condition}|{row['activity']}|{row['target']}|{row['count']}|")
    lines.extend(["", "行为分布只描述选择，不增加事后标准答案。更多 LEISURE 等易合法活动，"
                  "不能自动解释为需求满足、适当性或真人相似性改善。", "",
                  "|配对|完成组合|不完整原因|", "|---|---|---|"])
    for pair in pairs:
        lines.append(f"|{pair['pair_id']}|{pair.get('completion_combination', 'UNKNOWN')}|"
                     f"{','.join(pair.get('incomplete_reasons', [])) or 'NONE'}|")
    lines.extend(["", "|描述子集|可评分配对|拒绝 B−A|完成 B−A|输入 token B−A|输入成本覆盖|",
                  "|---|---:|---:|---:|---:|---|"])
    for name, values in summary["paired_descriptive"].items():
        rejection = values["rule_rejection_B_minus_A"]["mean"]
        completion = values["activity_completed_B_minus_A"]["mean"]
        inputs = values["input_tokens_B_minus_A"]
        lines.append(f"|{name}|{values['eligible_pairs']}|{rejection}|{completion}|"
                     f"{inputs['mean']}|{_format_ratio(inputs['coverage'])}|")
    lines.extend([
        "", "先报告全部分配单元，再报告完整配对及同后端完整配对敏感性描述；"
        "不选择有利子集。超时可能不随机，完整配对不能消除全部选择偏差。",
        "拒绝率低不等于真正完成活动更多。s06 的合法长历史及时间、需求差异继续作为限制，"
        "固定面板不能证明真实模型连续追完一部剧。",
        "runner 的 MODEL_BENEFIT=NOT_TESTED 不等于零真实请求。"
        "研究方向必须在真实阶段结束后依据覆盖、失败及多个指标作独立透明解释。", "",
    ])
    return lines
