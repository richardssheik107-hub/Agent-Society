"""Episode/session versus full-day duration candidates and mechanical replay."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass

from social_sim.daily.time import LEISURE_DURATION_MINUTES, SLEEP_DURATION_MINUTES, WORK_DURATION_MINUTES
from social_sim.human_data.models import HumanDayDiary
from social_sim.human_data.stats import distribution

from .coverage import merged_shadow
from .ontology import CORE5, DOMAIN_ORDER


@dataclass(frozen=True)
class DurationComparison:
    activity: str
    simulator_current_minutes: int | None
    empirical_episode_median: float | None
    empirical_episode_p25: float | None
    empirical_episode_p75: float | None
    empirical_daily_median: float | None
    comparison_status: str
    recommended_candidate: int | None
    rationale: str


def duration_stats(diaries: tuple[HumanDayDiary, ...], domains: tuple[str, ...]) -> dict[str, dict[str, dict[str, float | int | None]]]:
    episode_values: dict[str, list[int]] = defaultdict(list)
    daily_values: dict[str, list[int]] = defaultdict(list)
    for diary in diaries:
        totals: dict[str, int] = defaultdict(int)
        for episode in merged_shadow(diary, domains):
            episode_values[episode.activity].append(episode.duration_minutes)
            totals[episode.activity] += episode.duration_minutes
        for activity in (*CORE5, *DOMAIN_ORDER, "OTHER"):
            daily_values[activity].append(totals[activity])
    return {activity: {"episode": distribution(episode_values[activity], episode=True), "daily": distribution(daily_values[activity], episode=True)} for activity in (*CORE5, *DOMAIN_ORDER, "OTHER")}


def comparisons(stats: dict[str, dict[str, dict[str, float | int | None]]]) -> tuple[DurationComparison, ...]:
    current = {"SLEEP": SLEEP_DURATION_MINUTES, "WORK": WORK_DURATION_MINUTES, "LEISURE": LEISURE_DURATION_MINUTES}
    rationale = {
        "SLEEP": "Midnight splits sleep bouts; 06:00–24:00 simulator omits overnight time. Retain current 360 as conservative experimental placeholder pending semantics.",
        "WORK": "90-minute session is below empirical merged-episode IQR; median is a shadow-session candidate, not a production rule.",
        "LEISURE": "Current timed session is compared to merged recreational sessions; use median only in experimental replay.",
        "EAT": "Instant hunger/inventory effect has no session duration. Candidate is future occupancy, not a change to consumption effect.",
        "MOVE": "Immediate world-location transition is not empirical travel time. Candidate is future occupancy, not a destination-rule change.",
        "PERSONAL_CARE": "New shadow domain; no production action or current session exists.",
        "CHORES": "New shadow domain; no production action or current session exists.",
    }
    result = []
    for activity in (*CORE5, *DOMAIN_ORDER):
        ep, daily = stats[activity]["episode"], stats[activity]["daily"]
        minutes = current.get(activity)
        status = "NOT_COMPARABLE" if minutes is None or ep["p25"] is None else (
            "BELOW_EMPIRICAL_IQR" if minutes < ep["p25"] else
            "ABOVE_EMPIRICAL_IQR" if minutes > ep["p75"] else "WITHIN_EMPIRICAL_IQR"
        )
        candidate = (SLEEP_DURATION_MINUTES if activity == "SLEEP" else round(ep["median"])) if ep["median"] is not None else None
        result.append(DurationComparison(activity, minutes, ep["median"], ep["p25"], ep["p75"], daily["median"], status, candidate, rationale[activity]))
    return tuple(result)


def as_rows(values: tuple[DurationComparison, ...]) -> list[dict[str, object]]:
    return [asdict(row) for row in values]


def decision_frequency_counterfactual(comparisons_by_activity: dict[str, DurationComparison]) -> dict[str, object]:
    """Fixed 18-hour scripted occupancy: sleep 360 + work 480 + leisure 240.

    Only existing timed activities are compared; instantaneous EAT/MOVE are
    excluded from completion events on both sides to avoid a false reduction.
    """
    blocks = {"SLEEP": 360, "WORK": 480, "LEISURE": 240}
    current_events = sum(block // comparisons_by_activity[name].simulator_current_minutes for name, block in blocks.items())
    candidate_events = sum(block // comparisons_by_activity[name].recommended_candidate for name, block in blocks.items())
    return {"scripted_blocks_minutes": blocks, "horizon_minutes": 1080,
            "semantics": "One initial decision plus each full timed-session completion within fixed blocks; truncated remainders and scripted boundary changes are not completion events. Immediate EAT/MOVE excluded.",
            "current_profile_activity_completion_events": current_events,
            "candidate_profile_activity_completion_events": candidate_events,
            "current_profile_estimated_decisions_per_day": current_events + 1,
            "calibrated_profile_estimated_decisions_per_day": candidate_events + 1,
            "estimated_decision_reduction": current_events - candidate_events,
            "caution": "Mechanical schedule replay only; not a real model run, quality estimate, or predicted API-call saving."}
