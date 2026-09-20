"""The preregistered nested R8/R16/R32/R64 resource schema."""

from __future__ import annotations

from collections.abc import Mapping

from .models import ResourceLevel


R8_FIELDS = (
    "hunger", "energy", "sleep_pressure", "work_urgency",
    "hygiene_need", "chores_backlog", "leisure_need", "budget_pressure",
)
R16_FIELDS = R8_FIELDS + (
    "stress", "social_need", "commute_pressure", "discretionary_budget_remaining",
    "work_progress", "meal_recency", "personal_care_recency", "chores_recency",
)
R32_FIELDS = R16_FIELDS + (
    "physical_fatigue", "mental_fatigue", "sleep_debt", "sleep_quality",
    "hunger_trend", "food_security", "cash_on_hand", "checking_balance",
    "credit_available", "debt_pressure", "work_minutes_today", "work_deadline_pressure",
    "commute_minutes_pressure", "household_load", "leisure_minutes_today",
    "recent_spending_ratio",
)
R64_FIELDS = R32_FIELDS + (
    "hydration_need", "caffeine_level", "physical_discomfort", "temperature_discomfort",
    "sickness_signal", "exercise_fatigue", "work_stress", "financial_stress",
    "social_stress", "social_contact_recency", "friend_availability",
    "family_contact_recency", "loneliness", "shower_due", "dental_care_due",
    "clothing_cleanliness_need", "laundry_load", "dish_load", "trash_load",
    "kitchen_cleaning_need", "bedroom_cleaning_need", "cooking_prep_need",
    "grocery_stock_pressure", "appointment_urgency", "transport_availability",
    "mobility_friction", "cash_reserve_pressure", "savings_health", "credit_pressure",
    "currency_liquidity", "entertainment_novelty_need", "routine_disruption",
)

ALL_RESOURCE_FIELDS = R64_FIELDS
LEVEL_FIELDS: dict[ResourceLevel, tuple[str, ...]] = {
    ResourceLevel.R8: R8_FIELDS,
    ResourceLevel.R16: R16_FIELDS,
    ResourceLevel.R32: R32_FIELDS,
    ResourceLevel.R64: R64_FIELDS,
}


def resource_fields(level: ResourceLevel | str) -> tuple[str, ...]:
    return LEVEL_FIELDS[ResourceLevel(level)]


def nested_resource_schema() -> dict[str, list[str]]:
    return {level.value: list(fields) for level, fields in LEVEL_FIELDS.items()}


def projection_is_nested(projections: Mapping[ResourceLevel, Mapping[str, float]]) -> bool:
    for lower, higher in zip((ResourceLevel.R8, ResourceLevel.R16, ResourceLevel.R32),
                             (ResourceLevel.R16, ResourceLevel.R32, ResourceLevel.R64)):
        if tuple(projections[lower]) != resource_fields(lower):
            return False
        if tuple(projections[higher])[: len(resource_fields(lower))] != resource_fields(lower):
            return False
    return tuple(projections[ResourceLevel.R64]) == R64_FIELDS
