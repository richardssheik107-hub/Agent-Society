"""Pre-registered engineering selection; no model or judge calls."""

from __future__ import annotations

from statistics import mean


MIN_PANEL_SUCCESS_RATE = 0.90
MIN_MATCHED_PAIRS = 12  # Of 16 fixed state × repetition pairs per condition.
MIN_CONDITION_SUCCESS_RATE = 0.75
MAX_CONDITION_SUCCESS_GAP = 0.20
MIN_EXACT_HIT_RATE = 0.60
MAX_CORPUS_SCORE_GAP = 0.05
MAX_CORPUS_EXECUTABLE_GAP = 0.05
R3_SCORE_GAIN = 0.03
R3_EXECUTABLE_GAIN = 0.03
R3_TOP3_GAIN = 0.05


def _matched(rows: list[dict[str, object]], left: str, right: str) -> list[tuple[dict, dict]]:
    by_cell = {(row["state_id"], row["repetition"], row["condition"]): row for row in rows}
    pairs = []
    for state_id in (f"S{index}" for index in range(1, 9)):
        for repetition in (1, 2):
            a, b = (by_cell.get((state_id, repetition, condition)) for condition in (left, right))
            if a and b and a["provider_status"] == b["provider_status"] == "SUCCESS":
                pairs.append((a, b))
    return pairs


def pair_comparison(rows: list[dict[str, object]], left: str, right: str) -> dict[str, object]:
    pairs = _matched(rows, left, right)
    fields = ("heldout_action_share", "rule_executable", "heldout_top3_match",
              "context_chars", "input_tokens")
    result = {
        "left": left, "right": right, "matched_success_count": len(pairs),
        "matched_keys": [{"state_id": a["state_id"], "repetition": a["repetition"]} for a, _ in pairs],
    }
    for field in fields:
        valid = [(a, b) for a, b in pairs if a[field] is not None and b[field] is not None]
        result[f"mean_{field}_left"] = mean(float(a[field]) for a, _ in valid) if valid else None
        result[f"mean_{field}_right"] = mean(float(b[field]) for _, b in valid) if valid else None
        result[f"delta_{field}"] = mean(float(b[field]) - float(a[field]) for a, b in valid) if valid else None
        result[f"matched_{field}_count"] = len(valid)
    return result


def select_engineering_baseline(rows: list[dict[str, object]],
                                exact_hit_rates: dict[str, float]) -> dict[str, object]:
    if len(rows) != 80 or len({row["case_id"] for row in rows}) != 80:
        raise ValueError("PANEL_MUST_HAVE_80_UNIQUE_ROWS")
    success = sum(row["provider_status"] == "SUCCESS" for row in rows)
    condition_rates = {name: sum(row["provider_status"] == "SUCCESS" for row in rows
                                 if row["condition"] == name) / 16
                       for name in ("C0", "C1", "C2", "C3", "C4")}
    comparisons = {
        "prior_C0_C3": pair_comparison(rows, "C0", "C3"),
        "corpus_C1_C3": pair_comparison(rows, "C1", "C3"),
        "corpus_C2_C3": pair_comparison(rows, "C2", "C3"),
        "prior_size_C3_C4": pair_comparison(rows, "C3", "C4"),
    }
    reliable = success / 80 >= MIN_PANEL_SUCCESS_RATE
    corpus_checks = {}
    minimum_corpus = "UNRESOLVED"
    for name, condition in (("B100", "C1"), ("B1000", "C2"), ("BTRAIN_ALL", "C3")):
        comparison = comparisons[f"corpus_{condition}_C3"] if condition != "C3" else None
        matched = comparison["matched_success_count"] if comparison else 16 * condition_rates["C3"]
        score_gap = abs(comparison["delta_heldout_action_share"]) if comparison and comparison["delta_heldout_action_share"] is not None else 0.0
        executable_gap = abs(comparison["delta_rule_executable"]) if comparison and comparison["delta_rule_executable"] is not None else 0.0
        condition_ok = (condition_rates[condition] >= MIN_CONDITION_SUCCESS_RATE and
                        abs(condition_rates[condition] - condition_rates["C3"]) <= MAX_CONDITION_SUCCESS_GAP)
        passes = (reliable and exact_hit_rates[name] >= MIN_EXACT_HIT_RATE and
                  matched >= MIN_MATCHED_PAIRS and score_gap <= MAX_CORPUS_SCORE_GAP and
                  executable_gap <= MAX_CORPUS_EXECUTABLE_GAP and condition_ok)
        corpus_checks[name] = {
            "exact_hit_rate": exact_hit_rates[name], "matched_success_count": matched,
            "absolute_heldout_share_gap": score_gap, "absolute_executable_rate_gap": executable_gap,
            "condition_success_rate": condition_rates[condition], "passes": passes,
        }
        if passes and minimum_corpus == "UNRESOLVED":
            minimum_corpus = name
    prior_comparison = comparisons["prior_size_C3_C4"]
    prior_ready = (reliable and prior_comparison["matched_success_count"] >= MIN_MATCHED_PAIRS and
                   condition_rates["C4"] >= MIN_CONDITION_SUCCESS_RATE and
                   abs(condition_rates["C4"] - condition_rates["C3"]) <= MAX_CONDITION_SUCCESS_GAP and
                   prior_comparison["matched_input_tokens_count"] >= MIN_MATCHED_PAIRS)
    minimum_prior = "UNRESOLVED"
    if prior_ready:
        share = prior_comparison["delta_heldout_action_share"]
        executable = prior_comparison["delta_rule_executable"]
        top3 = prior_comparison["delta_heldout_top3_match"]
        cost_higher = (prior_comparison["delta_context_chars"] > 0 and
                       prior_comparison["delta_input_tokens"] > 0)
        if share < R3_SCORE_GAIN and executable < R3_EXECUTABLE_GAIN and top3 <= R3_TOP3_GAIN and cost_higher:
            minimum_prior = "R1"
        elif ((share >= R3_SCORE_GAIN or executable >= R3_EXECUTABLE_GAIN or top3 > R3_TOP3_GAIN)
              and share >= -R3_SCORE_GAIN and executable >= -R3_EXECUTABLE_GAIN
              and top3 >= -R3_TOP3_GAIN):
            minimum_prior = "R3"
    # The matrix tests R3 only with BTRAIN_ALL. Do not assert an untested
    # smaller-corpus/R3 combination is an engineering minimum.
    if minimum_corpus == "UNRESOLVED" or minimum_prior == "UNRESOLVED":
        selected_corpus, selected_prior, selection_basis = "BTRAIN_ALL", "R1", "CONSERVATIVE_FALLBACK_NOT_MINIMUM"
    elif minimum_prior == "R3":
        selected_corpus, selected_prior, selection_basis = "BTRAIN_ALL", "R3", "TESTED_R3_FULL_CORPUS_ONLY"
    else:
        selected_corpus, selected_prior, selection_basis = minimum_corpus, minimum_prior, "PRE_REGISTERED_MINIMUM"
    return {
        "panel_requests": len(rows), "success": success, "success_rate": success / 80,
        "reference_provider_stable_enough": reliable,
        "condition_success_rates": condition_rates, "comparisons": comparisons,
        "corpus_checks": corpus_checks, "prior_comparison_ready": prior_ready,
        "minimum_corpus_at_R1": minimum_corpus, "minimum_prior_at_full_train": minimum_prior,
        "selected_corpus": selected_corpus, "selected_prior": selected_prior,
        "selection_basis": selection_basis,
        "thresholds": {
            "min_panel_success_rate": MIN_PANEL_SUCCESS_RATE,
            "min_matched_pairs_of_16": MIN_MATCHED_PAIRS,
            "min_condition_success_rate": MIN_CONDITION_SUCCESS_RATE,
            "max_condition_success_gap": MAX_CONDITION_SUCCESS_GAP,
            "min_exact_hit_rate": MIN_EXACT_HIT_RATE,
            "max_corpus_share_gap": MAX_CORPUS_SCORE_GAP,
            "max_corpus_executable_gap": MAX_CORPUS_EXECUTABLE_GAP,
            "r3_share_gain": R3_SCORE_GAIN,
            "r3_executable_gain": R3_EXECUTABLE_GAIN,
            "r3_top3_gain": R3_TOP3_GAIN,
        },
    }
