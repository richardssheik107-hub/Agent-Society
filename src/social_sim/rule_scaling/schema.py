"""Human-maintained Type/Capability/Resource/Rule templates for Q5."""

from __future__ import annotations

from .models import RuleTemplate, TypeSpec


RESOURCES = (
    "money", "inventory", "ownership", "availability",
    "hunger", "energy", "leisure_need", "progress",
    "location", "time_budget", "asset_value", "schedule",
    "stress", "social_need", "mobility", "stock",
)

TYPE_SPECS = (
    TypeSpec(0, "food", frozenset({"purchasable", "ownable", "edible"})),
    TypeSpec(1, "game", frozenset({"purchasable", "ownable", "playable"})),
    TypeSpec(2, "video", frozenset({"purchasable", "ownable", "watchable"})),
    TypeSpec(3, "product", frozenset({"purchasable", "ownable", "usable"})),
    TypeSpec(4, "asset", frozenset({"tradable", "ownable"})),
    TypeSpec(5, "vehicle", frozenset({"purchasable", "ownable", "drivable", "usable"})),
    TypeSpec(6, "place", frozenset({"visitable"})),
    TypeSpec(7, "service", frozenset({"purchasable", "bookable", "usable"})),
    TypeSpec(8, "tool", frozenset({"purchasable", "ownable", "usable"})),
    TypeSpec(9, "book", frozenset({"purchasable", "ownable", "readable"})),
)

CAPABILITIES = tuple(sorted({cap for spec in TYPE_SPECS for cap in spec.capabilities}))

RULE_TEMPLATES = (
    RuleTemplate(0, "BUY", frozenset({"purchasable"}), ("money", "ownership", "availability"), 4),
    RuleTemplate(1, "SELL", frozenset({"tradable"}), ("money", "ownership"), 3),
    RuleTemplate(2, "INVEST", frozenset({"tradable"}), ("money", "asset_value", "ownership"), 4),
    RuleTemplate(3, "EAT", frozenset({"edible"}), ("inventory", "hunger", "energy"), 3),
    RuleTemplate(4, "PLAY", frozenset({"playable"}), ("leisure_need", "energy", "progress"), 3),
    RuleTemplate(5, "WATCH", frozenset({"watchable"}), ("leisure_need", "progress"), 2),
    RuleTemplate(6, "USE", frozenset({"usable"}), ("energy", "progress"), 2),
    RuleTemplate(7, "DRIVE", frozenset({"drivable"}), ("location", "energy", "money"), 4),
    RuleTemplate(8, "VISIT", frozenset({"visitable"}), ("location", "time_budget"), 2),
    RuleTemplate(9, "BOOK", frozenset({"bookable"}), ("money", "schedule"), 3),
    RuleTemplate(10, "READ", frozenset({"readable"}), ("leisure_need", "progress"), 2),
)


def validate_schema() -> None:
    if [spec.type_id for spec in TYPE_SPECS] != list(range(len(TYPE_SPECS))):
        raise ValueError("type ids must be dense and ordered")
    if [rule.rule_id for rule in RULE_TEMPLATES] != list(range(len(RULE_TEMPLATES))):
        raise ValueError("rule ids must be dense and ordered")
    resources = set(RESOURCES)
    capabilities = set(CAPABILITIES)
    if len(resources) != len(RESOURCES):
        raise ValueError("resources must be unique")
    for rule in RULE_TEMPLATES:
        if not rule.required_capabilities <= capabilities:
            raise ValueError(f"unknown capability in {rule.action}")
        if not set(rule.affected_resources) <= resources:
            raise ValueError(f"unknown resource in {rule.action}")


validate_schema()
