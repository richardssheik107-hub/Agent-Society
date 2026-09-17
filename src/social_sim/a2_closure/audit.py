"""Deterministic, prompt-free classification of MAX_DECISIONS micro episodes."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timedelta


CAUSES = (
    "A_REPEATED_REJECTED_ACTION", "B_IMMEDIATE_ACTION_CHURN",
    "C_SAME_STATE_REDECISION", "D_TRIGGER_OR_DURATION_MECHANICS",
    "E_PRIOR_WORLD_MISMATCH", "F_NEED_OR_OBLIGATION_LOOP",
    "G_MODEL_ACTION_OSCILLATION", "H_MIXED_NO_DOMINANT_CAUSE",
    "I_DATA_INSUFFICIENT",
)
IMMEDIATE = frozenset(("MOVE", "BUY", "EAT"))
MECHANICAL_TRIGGERS = frozenset(("ACTIVITY_COMPLETED", "OBLIGATION_BOUNDARY"))
_PRIOR_NAME = re.compile(r"->\s*([A-Z_]+)")


def _person(snapshot: dict) -> dict:
    people = snapshot["people"]
    return people.get("1", people.get(1))


def _core(snapshot: dict) -> tuple[object, ...]:
    person = _person(snapshot)
    time = datetime.fromisoformat(snapshot["time"])
    return (person["location"], person.get("activity"), person["money"],
            tuple(sorted(person["inventory"].items())), round(person["hunger"], 1),
            round(person["energy"], 1) if person.get("energy") is not None else None,
            9 <= time.hour < 17)


def _prior(step: dict) -> str | None:
    hints = json.loads(step["context"]).get("h", [])
    if not hints:
        return None
    if len(hints) != 1:
        raise ValueError("EXPECTED_AT_MOST_ONE_PRIOR_HINT")
    match = _PRIOR_NAME.search(hints[0])
    if match is None:
        raise ValueError("PRIOR_HINT_UNPARSEABLE")
    return match.group(1)


def _rejection_signature(step: dict) -> tuple[str, object, str]:
    return (step["proposal"]["action"], step["proposal"].get("target"),
            step["rule_reason_code"])


def classify_max_decisions(row: dict, trajectory: dict, daily: dict) -> dict[str, object]:
    """Score seven evidence types; ties within 0.10 become MIXED."""
    if row["termination_reason"] != "MAX_DECISIONS" or trajectory["termination_reason"] != "MAX_DECISIONS":
        raise ValueError("EXPECTED_MAX_DECISIONS")
    steps = trajectory["steps"]
    ticks = daily["ticks"]
    if len(steps) != row["decision_count"] or len(ticks) * 15 != row["observed_minutes"]:
        raise ValueError("DECISION_OR_TICK_COUNT_MISMATCH")
    missing = [name for name in ("simulation_time", "trigger_reason", "state_before", "state_after",
                                   "proposal", "rule_allowed", "rule_reason_code", "context")
               if any(name not in step for step in steps)]
    if missing:
        return {"cell_id": row["episode_number"], "primary_root_cause": CAUSES[-1],
                "secondary_causes": [], "missing_fields": missing}
    n = len(steps)
    if n != 4:
        raise ValueError("MAX_DECISION_CELL_EXPECTED_FOUR_STEPS")
    priors = [_prior(step) for step in steps]
    followed = [prior is not None and prior == step["proposal"]["action"]
                for prior, step in zip(priors, steps)]
    prior_rejected = [is_followed and not step["rule_allowed"]
                      for is_followed, step in zip(followed, steps)]
    immediate_followups = []
    same_tick_duplicates = []
    same_state = []
    repeated_rejected = []
    for index in range(1, n):
        previous, current = steps[index - 1], steps[index]
        delta = datetime.fromisoformat(current["simulation_time"]) - datetime.fromisoformat(
            previous["simulation_time"])
        adjacent = timedelta(0) < delta <= timedelta(minutes=15)
        if delta == timedelta(0):
            same_tick_duplicates.append(index)
        if (adjacent and previous["rule_allowed"]
                and previous["proposal"]["action"] in IMMEDIATE
                and not current.get("active_activity")):
            immediate_followups.append(index)
        if adjacent and _core(previous["state_before"]) == _core(current["state_before"]):
            same_state.append(index)
        if (adjacent and not previous["rule_allowed"] and not current["rule_allowed"]
                and _rejection_signature(previous) == _rejection_signature(current)
                and _core(previous["state_before"]) == _core(current["state_before"])):
            repeated_rejected.append(index)
    mechanical = [index for index, step in enumerate(steps)
                  if step["trigger_reason"] in MECHANICAL_TRIGGERS]
    need_no_progress = [index for index, step in enumerate(steps)
                        if step["trigger_reason"] == "CRITICAL_NEED" and not step["rule_allowed"]]
    locations = [_person(step["state_before"])["location"] for step in steps]
    cycles = [index for index in range(2, n)
              if locations[index] == locations[index - 2] != locations[index - 1]]
    counts = {
        CAUSES[0]: len(repeated_rejected), CAUSES[1]: len(immediate_followups),
        CAUSES[2]: len(same_state), CAUSES[3]: len(mechanical),
        CAUSES[4]: sum(prior_rejected), CAUSES[5]: len(need_no_progress),
        CAUSES[6]: len(cycles),
    }
    scores = {name: round(count / (sum(followed) if name == CAUSES[4] and sum(followed) else n), 6)
              for name, count in counts.items()}
    ranked = sorted(scores, key=lambda name: (-scores[name], CAUSES.index(name)))
    first, second = ranked[:2]
    primary = CAUSES[7] if scores[first] - scores[second] < 0.10 else first
    secondary = [name for name in ranked if name != primary and scores[name] >= 0.25]
    trigger_distribution = dict(Counter(step["trigger_reason"] for step in steps))
    rejection_reasons = dict(Counter(step["rule_reason_code"] for step in steps
                                     if not step["rule_allowed"]))
    activity_minutes = dict(Counter(tick["active_activity"] for tick in ticks
                                    if tick["active_activity"] is not None))
    activity_minutes = {name: count * 15 for name, count in activity_minutes.items()}
    trace = []
    for step, prior in zip(steps, priors):
        proposal = step["proposal"]
        trace.append(
            f"{datetime.fromisoformat(step['simulation_time']):%H:%M} {step['trigger_reason']} "
            f"prior={prior or '-'} proposal={proposal['action']}:{proposal.get('target') or '-'} "
            f"{'accepted' if step['rule_allowed'] else 'rejected:' + step['rule_reason_code']} "
            f"location={_person(step['state_before'])['location']}"
        )
    return {
        "cell_id": row["episode_number"], "scenario": row["scenario"], "condition": row["condition"],
        "observed_minutes": row["observed_minutes"], "decision_count": n,
        "accepted_count": sum(step["rule_allowed"] for step in steps),
        "rejected_count": sum(not step["rule_allowed"] for step in steps),
        "activity_minutes": activity_minutes, "prior_count": sum(prior is not None for prior in priors),
        "termination_point": ticks[-1]["end_time"], "trigger_reason_distribution": trigger_distribution,
        "repeated_rejected_count": len(repeated_rejected), "rejection_reasons": rejection_reasons,
        "max_consecutive_identical_rejection_streak": 1 + len(repeated_rejected)
        if repeated_rejected else (1 if rejection_reasons else 0),
        "immediate_followup_count": len(immediate_followups), "same_state_redecision_count": len(same_state),
        "same_tick_duplicate_count": len(same_tick_duplicates),
        "cycle_signature": [f"{locations[index - 2]}>{locations[index - 1]}>{locations[index]}"
                            for index in cycles],
        "prior_mentions": sum(prior is not None for prior in priors),
        "prior_followed": sum(followed),
        "prior_followed_and_executable": sum(is_followed and step["rule_allowed"]
                                              for is_followed, step in zip(followed, steps)),
        "prior_followed_and_rejected": sum(prior_rejected),
        "prior_not_followed": sum(prior is not None and not is_followed
                                  for prior, is_followed in zip(priors, followed)),
        "prior_related_invalid_share_of_decisions": sum(prior_rejected) / n,
        "evidence_counts": counts, "evidence_scores": scores,
        "primary_root_cause": primary, "secondary_causes": secondary,
        "compact_trace": trace, "missing_fields": [],
    }


def summarize_audit(cells: list[dict[str, object]]) -> tuple[dict[str, object], dict[str, object]]:
    if len(cells) != 7 or len({cell["cell_id"] for cell in cells}) != 7:
        raise ValueError("SEVEN_UNIQUE_MAX_DECISION_CELLS_REQUIRED")
    counts = Counter(cell["primary_root_cause"] for cell in cells)
    dominant = next((name for name, count in counts.items() if count >= 4), "NONE")
    signal_cells = [cell["cell_id"] for cell in cells
                    if cell.get("prior_followed_and_rejected", 0) >= 1
                    and cell.get("prior_related_invalid_share_of_decisions", 0) >= 0.25]
    signal = "YES" if len(signal_cells) >= 3 else "NO"
    if any(cell["primary_root_cause"] == CAUSES[-1] for cell in cells):
        signal = "INSUFFICIENT"
    return (
        {"audited": len(cells), "primary_counts": {name: counts[name] for name in CAUSES},
         "global_dominant_cause": dominant, "dominance_threshold_cells": 4,
         "same_tick_duplicate_count": sum(cell.get("same_tick_duplicate_count", 0) for cell in cells),
         "dominance_is_statistical_claim": False},
        {"prior_loop_signal": signal, "qualifying_cells": signal_cells,
         "rule": "At least 3/7 cells each have >=1 prior-followed rejected action and such actions are >=25% of that cell's decisions.",
         "prior_mentions": sum(cell.get("prior_mentions", 0) for cell in cells),
         "prior_followed": sum(cell.get("prior_followed", 0) for cell in cells),
         "prior_followed_and_executable": sum(cell.get("prior_followed_and_executable", 0) for cell in cells),
         "prior_followed_and_rejected": sum(cell.get("prior_followed_and_rejected", 0) for cell in cells),
         "prior_not_followed": sum(cell.get("prior_not_followed", 0) for cell in cells)},
    )


def decide_runtime_change(summary: dict[str, object], prior: dict[str, object]) -> dict[str, object]:
    """Apply the closure decision gate without treating intended instant effects as a bug."""
    dominant = summary["global_dominant_cause"]
    signal = prior["prior_loop_signal"]
    if dominant == "NONE" and signal == "NO" and summary["same_tick_duplicate_count"] == 0:
        decision = "NO_RUNTIME_CHANGE_NEEDED"
        reason = "No global root cause, no prior loop signal, and no same-tick trigger duplicate."
    elif dominant == "B_IMMEDIATE_ACTION_CHURN" and summary["same_tick_duplicate_count"] == 0:
        decision = "BEHAVIORAL_CAUSE_UNRESOLVED"
        reason = ("Instant MOVE/BUY/EAT actions are followed by ordinary next-tick decisions, "
                  "not duplicate calls in one tick. A prior-feasibility filter could omit three "
                  "infeasible prior names, but replacement decisions are unobserved and no evidence "
                  "shows it would resolve the five-cell global dominant cause; no single evidence-backed "
                  "runtime repair is justified under the one-fix rule.")
    else:
        decision = "BEHAVIORAL_CAUSE_UNRESOLVED"
        reason = "The audit does not isolate one safely fixable deterministic runtime defect."
    return {
        "decision": decision, "global_dominant_cause": dominant,
        "prior_loop_signal": signal, "reason": reason,
        "runtime_behavior_change": "NONE", "runtime_guard": "NONE",
        "real_continuity_rerun": "NOT_NEEDED",
        "rerun_reason": "No justified runtime behavior change; the optional 8-episode provider confirmation is not permitted.",
    }
