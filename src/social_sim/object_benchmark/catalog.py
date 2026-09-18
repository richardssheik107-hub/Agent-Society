"""Deterministic synthetic catalog and Top-K retrieval used by the benchmark."""

from __future__ import annotations

import re
from collections.abc import Iterable

from .models import CatalogObject, ObjectDomain, ObjectScenario


_DOMAIN_TAGS: dict[ObjectDomain, tuple[str, ...]] = {
    ObjectDomain.FOOD: ("breakfast", "quick", "high_satiety", "healthy", "treat", "cheap"),
    ObjectDomain.GAME: ("strategy", "party", "short", "competitive", "relaxing", "coop"),
    ObjectDomain.VIDEO: ("series", "comedy", "documentary", "short", "family", "calm"),
    ObjectDomain.PRODUCT: ("useful", "gadget", "clothing", "gift", "replacement", "hobby"),
    ObjectDomain.ASSET: ("liquid", "travel", "savings", "emergency", "investment", "housing"),
}

_CAPABILITY: dict[ObjectDomain, str] = {
    ObjectDomain.FOOD: "edible",
    ObjectDomain.GAME: "playable",
    ObjectDomain.VIDEO: "watchable",
    ObjectDomain.PRODUCT: "tradable",
    ObjectDomain.ASSET: "usable_asset",
}

_DEFAULTS: dict[ObjectDomain, dict[str, str | int | float | bool]] = {
    ObjectDomain.FOOD: {"price": 12.0, "calories": 450, "satiety": 0.50},
    ObjectDomain.GAME: {"price": 30.0, "session_minutes": 45, "sociality": 0.50},
    ObjectDomain.VIDEO: {"price": 0.0, "duration_minutes": 45, "episode_count": 12},
    ObjectDomain.PRODUCT: {"price": 80.0, "durability": 0.70, "utility": 0.60},
    ObjectDomain.ASSET: {"value": 1000.0, "liquidity": 0.50, "currency": "USD"},
}


def normalize_name(value: str) -> str:
    text = value.casefold().strip()
    return re.sub(r"[^\w]+", "", text, flags=re.UNICODE)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug[:48] or "object"


class ObjectCatalog:
    """Immutable lookup/retrieval surface; the master catalog never enters the prompt."""

    def __init__(self, objects: Iterable[CatalogObject]) -> None:
        items = tuple(objects)
        ids = [item.canonical_id for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate canonical id")
        self.objects = items
        self.by_id = {item.canonical_id: item for item in items}
        names: dict[str, CatalogObject] = {}
        for item in items:
            for label in (item.name, *item.aliases):
                key = normalize_name(label)
                if key and key not in names:
                    names[key] = item
        self.by_name = names

    def resolve(self, value: str) -> CatalogObject | None:
        if value in self.by_id:
            return self.by_id[value]
        return self.by_name.get(normalize_name(value))

    def retrieve(self, scenario: ObjectScenario, *, k: int = 10) -> tuple[CatalogObject, ...]:
        if k <= 0:
            raise ValueError("k must be positive")

        def score(item: CatalogObject) -> tuple[float, str]:
            value = 100.0
            value += 20.0 * len(set(scenario.preference_tags) & set(item.tags))
            price = item.attributes.get("price")
            if scenario.budget is not None and isinstance(price, (int, float)):
                value += 8.0 if float(price) <= scenario.budget else -50.0
            if item.canonical_id not in scenario.history_ids:
                value += 5.0
            if item.canonical_id in scenario.owned_ids:
                value += 3.0
            return value, item.canonical_id

        candidates = [
            item for item in self.objects
            if item.available and item.domain is scenario.domain
        ]
        candidates.sort(key=lambda item: (-score(item)[0], score(item)[1]))
        return tuple(candidates[:k])

    def instantiate_novel(self, name: str, domain: ObjectDomain) -> CatalogObject:
        clean = name.strip()
        if not clean:
            raise ValueError("novel object name must be nonempty")
        defaults = dict(_DEFAULTS[domain])
        return CatalogObject(
            canonical_id=f"novel:{domain.value.lower()}:{_slug(clean)}",
            name=clean,
            domain=domain,
            capabilities=frozenset({_CAPABILITY[domain]}),
            attributes=defaults,
            tags=frozenset({"llm_novel"}),
            estimated_fields=frozenset(defaults),
        )


def _attributes(domain: ObjectDomain, index: int) -> dict[str, str | int | float | bool]:
    if domain is ObjectDomain.FOOD:
        return {
            "price": float(4 + (index % 18)),
            "calories": 120 + (index * 47) % 980,
            "satiety": round(0.20 + ((index * 13) % 70) / 100, 2),
        }
    if domain is ObjectDomain.GAME:
        return {
            "price": float((index * 7) % 70),
            "session_minutes": 15 + 15 * (index % 6),
            "sociality": round(((index * 17) % 100) / 100, 2),
        }
    if domain is ObjectDomain.VIDEO:
        return {
            "price": 0.0,
            "duration_minutes": 10 + 10 * (index % 9),
            "episode_count": 1 + (index % 24),
        }
    if domain is ObjectDomain.PRODUCT:
        return {
            "price": float(10 + (index * 23) % 300),
            "durability": round(0.30 + ((index * 11) % 65) / 100, 2),
            "utility": round(0.25 + ((index * 19) % 70) / 100, 2),
        }
    return {
        "value": float(100 + (index * 977) % 100000),
        "liquidity": round(((index * 9) % 100) / 100, 2),
        "currency": ("USD", "JPY", "EUR", "CNY")[index % 4],
    }


def build_synthetic_catalog(per_domain: int = 200) -> ObjectCatalog:
    """Build a deterministic 1,000-object default catalog without external data."""
    if per_domain < 12:
        raise ValueError("per_domain must be at least 12")
    objects: list[CatalogObject] = []
    for domain in ObjectDomain:
        tags = _DOMAIN_TAGS[domain]
        capability = _CAPABILITY[domain]
        for index in range(per_domain):
            tag = tags[index % len(tags)]
            number = index + 1
            canonical_id = f"{domain.value.lower()}:{tag}:{number:04d}"
            display = f"{tag.replace('_', ' ')} {domain.value.lower()} {number:04d}"
            objects.append(
                CatalogObject(
                    canonical_id=canonical_id,
                    name=display,
                    domain=domain,
                    capabilities=frozenset({capability}),
                    attributes=_attributes(domain, index),
                    tags=frozenset({tag, domain.value.lower()}),
                    aliases=(f"{tag}-{number}",),
                )
            )
    return ObjectCatalog(objects)


def build_scenarios() -> tuple[ObjectScenario, ...]:
    """Thirty fixed states: five object domains times six intents/preferences."""
    scenarios: list[ObjectScenario] = []
    for domain in ObjectDomain:
        for index, tag in enumerate(_DOMAIN_TAGS[domain], 1):
            budget = None if domain is ObjectDomain.ASSET else float(20 + index * 25)
            history = (f"{domain.value.lower()}:{tag}:{1:04d}",)
            scenarios.append(
                ObjectScenario(
                    scenario_id=f"{domain.value[0]}{index}",
                    domain=domain,
                    intent=f"Choose one concrete {domain.value.lower()} for a {tag.replace('_', ' ')} situation.",
                    preference_tags=(tag,),
                    budget=budget,
                    history_ids=history,
                )
            )
    return tuple(scenarios)
