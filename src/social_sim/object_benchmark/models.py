"""Domain-neutral models for the Object Set Necessity benchmark."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


Scalar = str | int | float | bool


class ObjectDomain(str, Enum):
    FOOD = "FOOD"
    GAME = "GAME"
    VIDEO = "VIDEO"
    PRODUCT = "PRODUCT"
    ASSET = "ASSET"


class ArchitectureArm(str, Enum):
    LLM_ONLY = "A_LLM_ONLY"
    CATALOG_TOPK = "B_CATALOG_TOPK"
    HYBRID = "C_HYBRID"


@dataclass(frozen=True)
class CatalogObject:
    canonical_id: str
    name: str
    domain: ObjectDomain
    capabilities: frozenset[str]
    attributes: Mapping[str, Scalar]
    tags: frozenset[str] = frozenset()
    aliases: tuple[str, ...] = ()
    available: bool = True
    estimated_fields: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.canonical_id.strip() or not self.name.strip():
            raise ValueError("catalog object id/name must be nonempty")
        if not self.capabilities:
            raise ValueError("catalog object needs at least one capability")
        if not set(self.estimated_fields).issubset(self.attributes):
            raise ValueError("estimated_fields must exist in attributes")


@dataclass(frozen=True)
class ObjectScenario:
    scenario_id: str
    domain: ObjectDomain
    intent: str
    preference_tags: tuple[str, ...]
    budget: float | None = None
    history_ids: tuple[str, ...] = ()
    owned_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.scenario_id or not self.intent.strip():
            raise ValueError("scenario id/intent must be nonempty")
        if not self.preference_tags:
            raise ValueError("scenario needs at least one preference tag")
        if self.budget is not None and self.budget < 0:
            raise ValueError("budget must be nonnegative")
