"""Four frozen 90-minute continuity checks for the selected panel profile."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean

from social_sim.behavior_prior.benchmark import Condition, condition_episode_metrics
from social_sim.daily.models import DailyEpisodeResult
from social_sim.world import OfferState, PersonWorldState, WorldState


@dataclass(frozen=True)
class MicroScenario:
    name: str
    hour: int
    minute: int
    location: str
    hunger: float
    energy: float

    def world(self) -> WorldState:
        return WorldState(
            time=datetime(2026, 1, 1, self.hour, self.minute, tzinfo=timezone.utc),
            people={1: PersonWorldState(1, self.location, 100.0, self.hunger, energy=self.energy)},
            locations=("home", "office", "restaurant", "park"),
            venues={"restaurant": {"meal": OfferState("meal", 20.0, 10)}},
        )


SCENARIOS = (
    MicroScenario("M1_MORNING", 6, 30, "home", 0.30, 0.80),
    MicroScenario("M2_WORK", 9, 15, "office", 0.40, 0.70),
    MicroScenario("M3_MIDDAY", 12, 15, "office", 0.80, 0.55),
    MicroScenario("M4_EVENING", 18, 30, "home", 0.40, 0.45),
)


def micro_arms(selected_corpus: str, selected_prior: str) -> dict[str, tuple[str | None, int]]:
    if selected_corpus not in ("B100", "B1000", "BTRAIN_ALL") or selected_prior not in ("R1", "R3"):
        raise ValueError("micro candidate must be a valid selected profile")
    limit = 1 if selected_prior == "R1" else 3
    arms = {"CONTROL": (None, 0), "CANDIDATE": (selected_corpus, limit)}
    if selected_corpus != "BTRAIN_ALL":
        arms["FULL"] = ("BTRAIN_ALL", limit)
    return arms


def micro_schedule(arms: dict[str, tuple[str | None, int]]) -> list[dict[str, object]]:
    names = tuple(arms)
    if names not in (("CONTROL", "CANDIDATE"), ("CONTROL", "CANDIDATE", "FULL")):
        raise ValueError("micro arms must be control, candidate, optional full")
    result = []
    for repetition in (1, 2):
        for scenario_index, scenario in enumerate(SCENARIOS):
            offset = (scenario_index + repetition - 1) % len(names)
            for position in ((offset + step) % len(names) for step in range(len(names))):
                name = names[position]
                result.append({"episode": len(result) + 1, "scenario": scenario.name,
                               "repetition": repetition, "arm": name,
                               "corpus": arms[name][0] or "B0", "prior_k": arms[name][1]})
    if len(result) not in (16, 24):
        raise RuntimeError("MICRO_SCHEDULE_SIZE")
    return result


_FULL_BEHAVIOR_FIELDS = (
    "idle_minutes", "idle_ratio", "max_idle_streak", "active_minutes",
    "unique_activity_types", "unresolved_need_minutes", "obligation_neglect_minutes",
    "sleep_minutes", "work_minutes", "leisure_minutes", "personal_care_minutes",
    "chores_minutes", "same_state_decision_count", "decision_burst_count",
    "decisions_per_sim_hour", "repeated_invalid_count", "rejection_rate",
)


def micro_episode_row(result: DailyEpisodeResult, item: dict[str, object]) -> dict[str, object]:
    condition = Condition(item["arm"], None if item["corpus"] == "B0" else item["corpus"], item["prior_k"])
    row = condition_episode_metrics(result, segment=item["scenario"], condition=condition)
    row.update(scenario=item["scenario"], repetition=item["repetition"],
               prior_k=item["prior_k"], episode_number=item["episode"],
               partial_observed_minutes=result.observed_minutes if not result.day_completed else None,
               partial_idle_minutes=result.partial_window_metrics["partial_idle_minutes"]
               if result.partial_window_metrics else None)
    if not result.day_completed:
        for field in _FULL_BEHAVIOR_FIELDS:
            row[field] = None
    return row


_COMPARE_FIELDS = ("idle_ratio", "rejection_rate", "decision_count", "repeated_invalid_count",
                   "active_minutes", "unique_activity_types")


def matched_micro(rows: list[dict[str, object]], left: str, right: str) -> dict[str, object]:
    lookup = {(row["scenario"], row["repetition"], row["condition"]): row for row in rows}
    pairs = []
    for scenario in SCENARIOS:
        for repetition in (1, 2):
            a, b = (lookup.get((scenario.name, repetition, arm)) for arm in (left, right))
            if a and b and a["segment_completion"] and b["segment_completion"]:
                pairs.append((a, b))
    return {
        "left": left, "right": right, "matched_complete_count": len(pairs),
        "matched_keys": [{"scenario": a["scenario"], "repetition": a["repetition"]} for a, _ in pairs],
        "deltas_right_minus_left": {
            field: mean(b[field] - a[field] for a, b in pairs) if pairs else None
            for field in _COMPARE_FIELDS
        },
        "max_right_minus_left": {
            field: max(b[field] - a[field] for a, b in pairs) if pairs else None
            for field in ("idle_ratio", "rejection_rate", "decision_count")
        },
    }


def summarize_micro(rows: list[dict[str, object]], arms: dict[str, tuple[str | None, int]]) -> dict[str, object]:
    expected = 8 * len(arms)
    if len(rows) != expected or len({row["episode_number"] for row in rows}) != expected:
        raise ValueError("MICRO_EPISODES_MISSING_OR_DUPLICATE")
    by_arm = {}
    for name in arms:
        selected = [row for row in rows if row["condition"] == name]
        complete = [row for row in selected if row["segment_completion"]]
        by_arm[name] = {
            "episodes": len(selected), "complete": len(complete),
            "termination_counts": dict(Counter(row["termination_reason"] for row in selected)),
            **{f"mean_{field}": mean(row[field] for row in complete) if complete else None
               for field in _COMPARE_FIELDS},
            "personal_care_proposals": sum(row["personal_care_proposals"] or 0 for row in selected),
            "personal_care_accepted": sum(row["personal_care_accepted"] or 0 for row in selected),
            "chores_proposals": sum(row["chores_proposals"] or 0 for row in selected),
            "chores_accepted": sum(row["chores_accepted"] or 0 for row in selected),
            "episodes_without_action_audit": sum(row["personal_care_proposals"] is None for row in selected),
        }
    control = matched_micro(rows, "CONTROL", "CANDIDATE")
    full = matched_micro(rows, "FULL", "CANDIDATE") if "FULL" in arms else None
    if full is None:
        validation = "SAME_AS_FULL" if by_arm["CANDIDATE"]["complete"] >= 4 else "INSUFFICIENT_COMPLETE"
    elif full["matched_complete_count"] < 4:
        validation = "INSUFFICIENT_MATCHED_COMPLETE"
    else:
        maximum = full["max_right_minus_left"]
        validation = "PASS" if (maximum["idle_ratio"] <= 0.10 and maximum["rejection_rate"] <= 0.10
                                and maximum["decision_count"] <= 1) else "DEGRADED"
    return {
        "episodes": len(rows), "complete": sum(row["segment_completion"] for row in rows),
        "provider_timeouts": sum(row["termination_reason"] == "TIMEOUT" for row in rows),
        "max_decisions": sum(row["termination_reason"] == "MAX_DECISIONS" for row in rows),
        "invalid_model_outputs": sum(row["termination_reason"] == "INVALID_MODEL_OUTPUT" for row in rows),
        "architecture_failures": sum(row["termination_reason"] == "ARCHITECTURE_ERROR" for row in rows),
        "by_arm": by_arm, "candidate_vs_control": control, "candidate_vs_full": full,
        "minimum_validation": validation,
        "validation_rule": "Each of >=4 matched complete pairs: candidate-full idle<=0.10, rejection<=0.10, decisions<=1",
    }
