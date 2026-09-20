"""Deterministic Q4 outcomes; no model judge and no production-state mutation."""

from __future__ import annotations

from collections import Counter
from statistics import mean, median
from typing import Mapping, Sequence

from social_sim.actions import ActionIntent
from social_sim.behavior_prior.models import CORE7
from social_sim.decision.models import ActionType
from social_sim.rules import RuleEngine

from .models import ResourceLevel, ResourceScenario
from .scenarios import scenario_world


LEVELS = (ResourceLevel.R8, ResourceLevel.R16, ResourceLevel.R32, ResourceLevel.R64)


def _engine() -> RuleEngine:
    return RuleEngine(
        duration_overrides={ActionType.PERSONAL_CARE: 30, ActionType.CHORES: 30},
        experimental_actions_enabled=True,
    )


def _mean(values: Sequence[object]) -> float | None:
    numbers = [float(value) for value in values if isinstance(value, (int, float)) and value is not None]
    return round(float(mean(numbers)), 6) if numbers else None


def _pct_delta(left: object, right: object) -> float | None:
    if not isinstance(left, (int, float)) or not isinstance(right, (int, float)) or left == 0:
        return None
    return round((float(right) - float(left)) / abs(float(left)), 6)


def score_proposal(
    scenario: ResourceScenario,
    action: ActionType | str,
    target: str | None,
    heldout_distribution: object | None = None,
) -> dict[str, object]:
    """Score one parsed proposal against fixed scenario contracts."""
    try:
        action = ActionType(action)
    except (TypeError, ValueError):
        return {
            "resource_alignment": 0,
            "rule_executable": 0,
            "critical_miss": 1,
            "heldout_action_share": None,
            "heldout_rank": None,
            "heldout_top3_match": None,
            "rule_reason_code": "INVALID_ACTION",
        }
    aligned = action in scenario.acceptable_action_set
    intent = ActionIntent(
        actor_id=1,
        action=action,
        target=target,
        params={"quantity": 1} if action in (ActionType.BUY, ActionType.EAT) else {},
    )
    try:
        rule = _engine().evaluate(scenario_world(scenario), intent)
        executable = bool(rule.allowed)
        reason = rule.reason_code.value
    except (TypeError, ValueError):
        executable = False
        reason = "INVALID_INTENT"

    heldout: dict[str, object] = {
        "heldout_action_share": None,
        "heldout_rank": None,
        "heldout_top3_match": None,
    }
    if heldout_distribution is not None and action.value in CORE7:
        # HeldoutDistribution is deliberately duck-typed to keep the benchmark
        # independent from the A2 package's corpus loading path in offline tests.
        heldout.update(heldout_distribution.score(action.value))
    return {
        "resource_alignment": int(aligned),
        "rule_executable": int(executable),
        "critical_miss": int(not aligned),
        **heldout,
        "rule_reason_code": reason,
    }


def _metrics(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    success = [row for row in rows if row.get("provider_status") == "SUCCESS"]
    result: dict[str, object] = {"rows": len(success)}
    for key in (
        "resource_alignment", "rule_executable", "critical_miss",
        "heldout_action_share", "heldout_top3_match", "input_tokens",
        "output_tokens", "reasoning_tokens", "prompt_chars", "context_chars",
        "latency_seconds",
    ):
        result[key] = _mean([row.get(key) for row in success])
    input_values = [row["input_tokens"] for row in success if isinstance(row.get("input_tokens"), (int, float))]
    result["median_input_tokens"] = round(float(median(input_values)), 6) if input_values else None
    result["strict_parse_rate"] = _mean([row.get("strict_parse_valid") for row in success])
    return result


def _matched_rows(rows: Sequence[Mapping[str, object]]) -> tuple[set[tuple[str, int]], dict[tuple[str, int, str], Mapping[str, object]]]:
    by_cell = {(str(row["scenario_id"]), int(row["repetition"]), str(row["level"])): row for row in rows}
    keys = {
        (scenario_id, repetition)
        for scenario_id, repetition, _ in by_cell
        if all(
            by_cell.get((scenario_id, repetition, level.value), {}).get("provider_status") == "SUCCESS"
            for level in LEVELS
        )
    }
    return keys, by_cell


def summarize_resource_rows(rows: list[dict[str, object]]) -> dict[str, object]:
    statuses = Counter(str(row.get("provider_status", "UNKNOWN")) for row in rows)
    successful = [row for row in rows if row.get("provider_status") == "SUCCESS"]
    levels = {level.value: _metrics([row for row in successful if row.get("level") == level.value]) for level in LEVELS}
    matched_keys, by_cell = _matched_rows(rows)
    matched_levels = {
        level.value: _metrics([
            by_cell[(scenario_id, repetition, level.value)]
            for scenario_id, repetition in sorted(matched_keys)
        ])
        for level in LEVELS
    }
    positive = ("resource_alignment", "rule_executable", "heldout_action_share", "heldout_top3_match")
    best = {key: max((float(matched_levels[level.value][key] or 0.0) for level in LEVELS), default=0.0) for key in positive}
    minimum_critical = min((float(matched_levels[level.value]["critical_miss"] or 1.0) for level in LEVELS), default=1.0)
    minimum = "UNRESOLVED"
    if len(matched_keys) >= 30:
        for level in LEVELS:
            metric = matched_levels[level.value]
            if all(best[key] - float(metric[key] or 0.0) <= 0.05 for key in positive) and \
                    float(metric["critical_miss"] or 1.0) <= minimum_critical + 0.05:
                minimum = level.value
                break
    marginal: list[dict[str, object]] = []
    low_start = "NONE"
    overload = False
    for lower, higher in zip(LEVELS, LEVELS[1:]):
        a, b = matched_levels[lower.value], matched_levels[higher.value]
        alignment_delta = round(float(b["resource_alignment"] or 0.0) - float(a["resource_alignment"] or 0.0), 6)
        rule_delta = round(float(b["rule_executable"] or 0.0) - float(a["rule_executable"] or 0.0), 6)
        heldout_delta = None if a["heldout_action_share"] is None or b["heldout_action_share"] is None else round(float(b["heldout_action_share"]) - float(a["heldout_action_share"]), 6)
        critical_delta = round(float(b["critical_miss"] or 0.0) - float(a["critical_miss"] or 0.0), 6)
        token_pct = _pct_delta(a["input_tokens"], b["input_tokens"])
        latency_pct = _pct_delta(a["latency_seconds"], b["latency_seconds"])
        low = alignment_delta < 0.03 and (heldout_delta is None or heldout_delta < 0.03) and rule_delta < 0.03 and (token_pct is not None and token_pct >= 0.15 or latency_pct is not None and latency_pct >= 0.15)
        signal = "LOW_MARGINAL_RETURN" if low else "NONE"
        if low and low_start == "NONE":
            low_start = higher.value
        if alignment_delta < -0.03 or critical_delta > 0.03:
            overload = True
            signal = "RESOURCE_OVERLOAD_SIGNAL"
        marginal.append({
            "from": lower.value, "to": higher.value,
            "alignment_delta": alignment_delta, "rule_delta": rule_delta,
            "heldout_delta": heldout_delta, "critical_miss_delta": critical_delta,
            "token_delta_pct": token_pct, "latency_delta_pct": latency_pct,
            "signal": signal,
        })
    if len(matched_keys) < 30:
        result_status = "UNRESOLVED"
    elif minimum != "UNRESOLVED":
        result_status = "CLOSED_ENGINEERING"
    elif float(matched_levels["R8"]["resource_alignment"] or 0.0) < float(matched_levels["R16"]["resource_alignment"] or 0.0):
        result_status = "PARTIALLY_RESOLVED"
    else:
        result_status = "UNRESOLVED"
    top3_degraded = any(best["heldout_top3_match"] - float(matched_levels[level.value]["heldout_top3_match"] or 0.0) > 0.10 for level in LEVELS)
    return {
        "scheduled": len(rows),
        "success": len(successful),
        "timeout": statuses.get("TIMEOUT", 0),
        "http_error": statuses.get("HTTP_ERROR", 0),
        "parse_error": statuses.get("PARSE_ERROR", 0),
        "architecture_error": statuses.get("ARCHITECTURE_ERROR", 0),
        "status_counts": dict(sorted(statuses.items())),
        "http_status_counts": dict(sorted(Counter(str(row["http_status"]) for row in rows if isinstance(row.get("http_status"), int)).items())),
        "http_error_code_counts": dict(sorted(Counter(str(row["http_error_code"]) for row in rows if row.get("http_error_code")).items())),
        "backend_model_counts": dict(sorted(Counter(str(row["provider_model"]) for row in successful if row.get("provider_model")).items())),
        "levels": levels,
        "matched_quadruples": len(matched_keys),
        "matched_quadruple_denominator": 48,
        "matched_levels": matched_levels,
        "marginal_returns": marginal,
        "minimum_tested_resource_set": minimum,
        "low_marginal_return_starts_at": low_start,
        "resource_overload_signal": "YES" if overload else "NO",
        "top3_degraded": top3_degraded,
        "resource_set_result": result_status,
    }
