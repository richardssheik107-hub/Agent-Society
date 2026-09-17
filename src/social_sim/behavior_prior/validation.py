"""Read-only coverage and human-inspection samples for retrieval design."""

from __future__ import annotations

from collections import Counter

from .index import BehaviorPriorIndex
from .models import BUCKET_COUNT, CORE7
from .query import PriorQuery


def feasible_prior_count(result, world, rule_engine) -> int:
    """Record executability without feeding rule outcomes to the model."""
    from social_sim.actions.models import ActionIntent
    from social_sim.decision.models import ActionType

    person = world.get_person(1)
    count = 0
    for activity in result.activities:
        action = ActionType(activity)
        if action is ActionType.MOVE:
            targets = [location for location in world.locations if location != person.location]
        elif action is ActionType.EAT:
            targets = [item for item, quantity in person.inventory.items() if quantity > 0]
        else:
            targets = [None]
        if any(rule_engine.evaluate(world, ActionIntent(1, action, target)).allowed for target in targets):
            count += 1
    return count


def query_coverage(index: BehaviorPriorIndex) -> dict[str, object]:
    levels = Counter()
    queries = 0
    for bucket in range(BUCKET_COUNT):
        for previous in (None, *CORE7):
            result = index.query(PriorQuery(bucket, previous), limit=1)
            levels[result.fallback_level] += 1
            queries += 1
    return {
        "query_count": queries, "exact_hit_rate": levels["L0"] / queries,
        "fallback_L1": levels["L1"] / queries,
        "fallback_L2": levels["L2"] / queries,
        "fallback_L3": levels["L3"] / queries,
        "empty_rate": 0.0,
        "counts": {level: levels[level] for level in ("L0", "L1", "L2", "L3")},
    }


def sanity_table(index: BehaviorPriorIndex) -> list[dict[str, object]]:
    rows = []
    for hour, minute in ((7, 0), (9, 0), (12, 0), (18, 30), (21, 0)):
        bucket = (hour * 60 + minute) // 30
        for previous in (None, "MOVE", "WORK", "EAT", "LEISURE"):
            result = index.query(PriorQuery(bucket, previous), limit=3)
            rows.append({"time": f"{hour:02d}:{minute:02d}", "previous": previous,
                         "activities": list(result.activities), "fallback_level": result.fallback_level,
                         "support_count": result.support_count})
    return rows
