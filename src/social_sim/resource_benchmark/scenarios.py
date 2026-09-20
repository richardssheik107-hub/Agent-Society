"""Frozen 24-state Q4 manifest and objective-world builders."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from social_sim.behavior_prior.models import CORE7
from social_sim.behavior_prior.query import PriorQuery
from social_sim.decision.models import ActionType
from social_sim.world import OfferState, PersonWorldState, WorldState

from .models import ResourceScenario, ResourceTruth
from .schema import ALL_RESOURCE_FIELDS

if TYPE_CHECKING:
    from social_sim.behavior_prior.index import BehaviorPriorIndex


AVAILABLE_ACTIONS = (
    ActionType.WAIT, ActionType.REST, ActionType.MOVE, ActionType.BUY,
    ActionType.EAT, ActionType.SLEEP, ActionType.WORK, ActionType.LEISURE,
    ActionType.PERSONAL_CARE, ActionType.CHORES,
)
AVAILABLE_TARGETS = ("home", "office", "restaurant", "park", "meal")
_DEFAULT_PRIOR = {
    "hunger": ("EAT",), "hunger_trend": ("EAT",), "food_security": ("BUY",),
    "sleep_pressure": ("SLEEP",), "sleep_quality": ("SLEEP",), "sleep_debt": ("SLEEP",),
    "work_urgency": ("WORK",), "work_progress": ("WORK",), "work_deadline_pressure": ("WORK",),
    "hygiene_need": ("PERSONAL_CARE",), "personal_care_recency": ("PERSONAL_CARE",),
    "shower_due": ("PERSONAL_CARE",), "chores_backlog": ("CHORES",),
    "chores_recency": ("CHORES",), "kitchen_cleaning_need": ("CHORES",),
    "leisure_need": ("LEISURE",), "social_need": ("LEISURE",),
    "entertainment_novelty_need": ("LEISURE",), "budget_pressure": ("BUY",),
    "discretionary_budget_remaining": ("BUY",), "cash_reserve_pressure": ("BUY",),
    "commute_pressure": ("MOVE",), "commute_minutes_pressure": ("MOVE",),
    "transport_availability": ("MOVE",),
}


@dataclass(frozen=True)
class _Spec:
    scenario_id: str
    family: str
    time: str
    location: str
    previous_activity: str | None
    primary_resource: str
    acceptable: tuple[ActionType, ...]


_SPECS = (
    _Spec("hunger_1", "food", "2026-01-01T12:30:00+00:00", "office", "WORK", "hunger", (ActionType.EAT,)),
    _Spec("hunger_2", "food", "2026-01-01T12:45:00+00:00", "home", "WORK", "hunger_trend", (ActionType.EAT, ActionType.BUY)),
    _Spec("hunger_3", "food", "2026-01-01T18:30:00+00:00", "home", "MOVE", "food_security", (ActionType.BUY, ActionType.EAT)),
    _Spec("energy_1", "physiology", "2026-01-01T21:30:00+00:00", "home", "LEISURE", "sleep_pressure", (ActionType.SLEEP, ActionType.REST)),
    _Spec("energy_2", "physiology", "2026-01-01T21:45:00+00:00", "home", "WORK", "sleep_quality", (ActionType.SLEEP, ActionType.REST)),
    _Spec("energy_3", "physiology", "2026-01-01T06:30:00+00:00", "home", "SLEEP", "sleep_debt", (ActionType.SLEEP, ActionType.REST)),
    _Spec("work_1", "work", "2026-01-01T09:15:00+00:00", "office", "MOVE", "work_urgency", (ActionType.WORK,)),
    _Spec("work_2", "work", "2026-01-01T10:30:00+00:00", "office", "WORK", "work_progress", (ActionType.WORK, ActionType.REST)),
    _Spec("work_3", "work", "2026-01-01T16:30:00+00:00", "office", "WORK", "work_deadline_pressure", (ActionType.WORK, ActionType.MOVE)),
    _Spec("personal_care_1", "personal_care", "2026-01-01T07:00:00+00:00", "home", "SLEEP", "hygiene_need", (ActionType.PERSONAL_CARE,)),
    _Spec("personal_care_2", "personal_care", "2026-01-01T20:00:00+00:00", "home", "EAT", "personal_care_recency", (ActionType.PERSONAL_CARE,)),
    _Spec("personal_care_3", "personal_care", "2026-01-01T22:00:00+00:00", "home", "LEISURE", "shower_due", (ActionType.PERSONAL_CARE,)),
    _Spec("chores_1", "chores", "2026-01-01T19:30:00+00:00", "home", "EAT", "chores_backlog", (ActionType.CHORES,)),
    _Spec("chores_2", "chores", "2026-01-01T18:45:00+00:00", "home", "MOVE", "chores_recency", (ActionType.CHORES,)),
    _Spec("chores_3", "chores", "2026-01-01T20:30:00+00:00", "home", "LEISURE", "kitchen_cleaning_need", (ActionType.CHORES,)),
    _Spec("leisure_1", "leisure", "2026-01-01T18:30:00+00:00", "home", "WORK", "leisure_need", (ActionType.LEISURE, ActionType.REST)),
    _Spec("leisure_2", "leisure", "2026-01-01T19:45:00+00:00", "home", "CHORES", "social_need", (ActionType.LEISURE,)),
    _Spec("leisure_3", "leisure", "2026-01-01T21:00:00+00:00", "home", "LEISURE", "entertainment_novelty_need", (ActionType.LEISURE,)),
    _Spec("finance_1", "finance", "2026-01-01T12:00:00+00:00", "restaurant", "MOVE", "budget_pressure", (ActionType.BUY, ActionType.EAT)),
    _Spec("finance_2", "finance", "2026-01-01T17:30:00+00:00", "restaurant", "MOVE", "discretionary_budget_remaining", (ActionType.BUY,)),
    _Spec("finance_3", "finance", "2026-01-01T19:00:00+00:00", "home", "EAT", "cash_reserve_pressure", (ActionType.BUY, ActionType.MOVE)),
    _Spec("mobility_1", "mobility", "2026-01-01T08:30:00+00:00", "home", "SLEEP", "commute_pressure", (ActionType.MOVE,)),
    _Spec("mobility_2", "mobility", "2026-01-01T08:45:00+00:00", "home", "PERSONAL_CARE", "commute_minutes_pressure", (ActionType.MOVE,)),
    _Spec("mobility_3", "mobility", "2026-01-01T09:00:00+00:00", "home", "PERSONAL_CARE", "transport_availability", (ActionType.MOVE, ActionType.REST)),
)


def _truth(primary: str) -> ResourceTruth:
    values = {name: 0.20 for name in ALL_RESOURCE_FIELDS}
    values[primary] = 0.92
    values["energy"] = 0.65
    values["hunger"] = 0.75 if primary in {"hunger", "hunger_trend", "food_security"} else values["hunger"]
    return ResourceTruth(values)


def _prior_for(spec: _Spec, prior_index: BehaviorPriorIndex | None) -> tuple[str, ...]:
    if prior_index is None:
        return _DEFAULT_PRIOR.get(spec.primary_resource, ("WAIT",))
    query = PriorQuery.at(datetime.fromisoformat(spec.time), spec.previous_activity if spec.previous_activity in CORE7 else None)
    return prior_index.query(query, limit=1).activities


def build_scenarios(prior_index: BehaviorPriorIndex | None = None) -> tuple[ResourceScenario, ...]:
    """Build the frozen 24-state manifest; only prior values may be injected."""
    scenarios: list[ResourceScenario] = []
    for spec in _SPECS:
        truth = _truth(spec.primary_resource)
        world_facts = {
            "object_catalog": ["meal", "coffee", "book"],
            "available_targets": list(AVAILABLE_TARGETS),
            "venue_availability": {"restaurant": {"meal": {"price": 20.0, "available": True}}},
            "inventory": {"meal": 1} if spec.family == "food" else {},
        }
        scenarios.append(ResourceScenario(
            scenario_id=spec.scenario_id,
            family=spec.family,
            time=spec.time,
            location=spec.location,
            previous_activity=spec.previous_activity,
            recent_events=(f"{spec.previous_activity or 'NONE'}_COMPLETED",),
            behavior_prior=_prior_for(spec, prior_index),
            world_facts=world_facts,
            truth=truth,
            acceptable_action_set=spec.acceptable,
            critical_resources=(spec.primary_resource,),
            available_actions=AVAILABLE_ACTIONS,
            available_targets=AVAILABLE_TARGETS,
        ))
    if len(scenarios) != 24 or len({scenario.scenario_id for scenario in scenarios}) != 24:
        raise RuntimeError("Q4_SCENARIO_MANIFEST_INVALID")
    return tuple(scenarios)


def scenario_world(scenario: ResourceScenario) -> WorldState:
    """Return the same objective world for all four resource projections."""
    when = datetime.fromisoformat(scenario.time)
    inventory = dict(scenario.world_facts.get("inventory", {}))
    return WorldState(
        time=when if when.tzinfo else when.replace(tzinfo=timezone.utc),
        people={1: PersonWorldState(
            1, scenario.location, 100.0, scenario.truth.values["hunger"],
            inventory=inventory, energy=scenario.truth.values["energy"],
        )},
        locations=("home", "office", "restaurant", "park"),
        venues={"restaurant": {"meal": OfferState("meal", 20.0, 10)}},
    )


def smoke_scenarios(scenarios: tuple[ResourceScenario, ...]) -> tuple[ResourceScenario, ...]:
    wanted = ("hunger_1", "work_1", "personal_care_1", "chores_1")
    by_id = {scenario.scenario_id: scenario for scenario in scenarios}
    return tuple(by_id[name] for name in wanted)
