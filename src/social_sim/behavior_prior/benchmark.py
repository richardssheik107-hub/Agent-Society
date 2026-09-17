"""A2-Fast fixed conditions, rotation, and matched-complete comparisons."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from statistics import mean

from social_sim.daily.calibrated import SEGMENTS, episode_metrics
from social_sim.daily.models import DailyEpisodeResult


@dataclass(frozen=True)
class Condition:
    name: str
    corpus: str | None
    prior_limit: int


CONDITIONS = (
    Condition("C0", None, 0), Condition("C1", "B100", 1),
    Condition("C2", "B1000", 1), Condition("C3", "BALL", 1),
    Condition("C4", "BALL", 3),
)


def schedule() -> list[dict[str, object]]:
    rotations = ((0, 1, 2, 3, 4), (2, 3, 4, 0, 1), (4, 0, 1, 2, 3), (1, 2, 3, 4, 0))
    result = []
    for segment, positions in zip(SEGMENTS, rotations):
        for position in positions:
            result.append({"episode": len(result) + 1, "segment": segment,
                           "condition": CONDITIONS[position].name})
    return result


def condition_episode_metrics(result: DailyEpisodeResult, *, segment: str, condition: Condition) -> dict[str, object]:
    row = episode_metrics(result, segment=segment, repeat=1)
    del row["profile"]
    row.update(condition=condition.name, corpus=condition.corpus or "B0", prior_limit=condition.prior_limit)
    records = result.prior_audit
    followed = [record["followed"] for record in records if record["followed"] is not None]
    levels = Counter(record["fallback_level"] for record in records)
    added = []
    for step in result.trajectory.steps:
        context = json.loads(step.context)
        if "h" in context:
            without = dict(context)
            del without["h"]
            added.append(len(step.context) - len(json.dumps(without, ensure_ascii=False, sort_keys=True, separators=(",", ":"))))
    row.update(
        prior_query_count=len(records), prior_follow_count=sum(followed),
        prior_follow_rate=sum(followed) / len(followed) if followed else None,
        prior_feasible_count=sum(record["feasible_prior_count"] for record in records),
        prior_fallback_counts={level: levels[level] for level in ("L0", "L1", "L2", "L3")},
        prior_support_mean=mean(record["support_count"] for record in records) if records else None,
        prior_excluded_other_mass_mean=mean(record["excluded_other_mass"] for record in records) if records else None,
        avg_added_context_chars=mean(added) if added else 0.0,
        personal_care_prior_mentions=sum("PERSONAL_CARE" in record["activities"] for record in records),
        chores_prior_mentions=sum("CHORES" in record["activities"] for record in records),
        repeated_invalid_count=result.idle_metrics["repeated_invalid_count"],
    )
    return row


_BEHAVIOR = (
    "idle_minutes", "idle_ratio", "repeated_invalid_count", "same_state_decision_count",
    "decision_count", "decision_burst_count", "rejection_rate", "unresolved_need_minutes",
    "obligation_neglect_minutes", "unique_activity_types", "active_minutes",
)
_COST = ("avg_context_chars", "avg_prompt_chars", "input_tokens", "output_tokens",
         "reasoning_tokens", "latency_seconds", "avg_added_context_chars")


def aggregate_condition(rows: list[dict[str, object]]) -> dict[str, object]:
    complete = [row for row in rows if row["segment_completion"]]
    return {
        "complete_segments": len(complete), "truncated_segments": len(rows) - len(complete),
        "provider_timeouts": sum(row["termination_reason"] == "TIMEOUT" for row in rows),
        "max_decisions_terminations": sum(row["termination_reason"] == "MAX_DECISIONS" for row in rows),
        "architecture_failures": sum(row["termination_reason"] == "ARCHITECTURE_ERROR" for row in rows),
        **{f"avg_{field}": mean(row[field] for row in complete if row[field] is not None)
           if any(row[field] is not None for row in complete) else None for field in (*_BEHAVIOR, *_COST)},
        "prior_mentions": {
            activity: sum(row[f"{activity.lower()}_prior_mentions"] for row in rows)
            for activity in ("PERSONAL_CARE", "CHORES")
        },
        "prior_follow_count": sum(row["prior_follow_count"] for row in rows),
        "prior_query_count": sum(row["prior_query_count"] for row in rows),
        "prior_feasible_count": sum(row["prior_feasible_count"] for row in rows),
        "personal_care_proposals": sum(row["personal_care_proposals"] for row in rows),
        "personal_care_accepted": sum(row["personal_care_accepted"] for row in rows),
        "chores_proposals": sum(row["chores_proposals"] for row in rows),
        "chores_accepted": sum(row["chores_accepted"] for row in rows),
    }


def matched_comparisons(rows: list[dict[str, object]]) -> dict[str, object]:
    by_cell = {(row["condition"], row["segment"]): row for row in rows}

    def compare(left: str, right: str) -> dict[str, object]:
        cells = [(segment, by_cell.get((left, segment)), by_cell.get((right, segment))) for segment in SEGMENTS]
        complete = [(segment, a, b) for segment, a, b in cells
                    if a is not None and b is not None and a["segment_completion"] and b["segment_completion"]]
        return {
            "left": left, "right": right,
            "matched_complete_segments": [segment for segment, _, _ in complete],
            "matched_complete_count": len(complete),
            "deltas_right_minus_left": {
                field: mean(b[field] - a[field] for _, a, b in complete) if complete else None
                for field in _BEHAVIOR
            },
            "paired_values": [
                {"segment": segment, "left": {field: a[field] for field in _BEHAVIOR},
                 "right": {field: b[field] for field in _BEHAVIOR}}
                for segment, a, b in complete
            ],
        }

    triple = [segment for segment in SEGMENTS if all(
        (row := by_cell.get((name, segment))) is not None and row["segment_completion"]
        for name in ("C1", "C2", "C3")
    )]
    return {
        "prior_effect_C0_C3": compare("C0", "C3"),
        "corpus_size_C1_C2": compare("C1", "C2"),
        "corpus_size_C2_C3": compare("C2", "C3"),
        "corpus_size_triple_complete_segments": triple,
        "retrieval_size_C3_C4": compare("C3", "C4"),
    }
