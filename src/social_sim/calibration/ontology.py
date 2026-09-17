"""Explicit shadow ontology grounded in NHAPS main-activity labels."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from itertools import combinations


CORE5 = ("SLEEP", "WORK", "EAT", "LEISURE", "MOVE")
TARGET_MINUTE_COVERAGE = 0.90  # Engineering threshold, not a scientific estimate.


class EmpiricalActivityType(str, Enum):
    SLEEP = "SLEEP"
    WORK = "WORK"
    EAT = "EAT"
    LEISURE = "LEISURE"
    MOVE = "MOVE"
    PERSONAL_CARE = "PERSONAL_CARE"
    CHORES = "CHORES"
    OTHER = "OTHER"


@dataclass(frozen=True)
class SourceCategory:
    code: int
    label: str
    domain: str
    confidence: str
    rationale: str


# Exact source codes and labels from inspected USA1993hfep.SAV. Code 2 mixes
# personal and household care and is intentionally not inferred into either.
SOURCE_CATEGORIES = (
    SourceCategory(1, "general or other personal care", "PERSONAL_CARE", "medium", "Personal care, broad source category"),
    SourceCategory(6, "wash, dress, personal care", "PERSONAL_CARE", "high", "Explicit hygiene and dressing"),
    SourceCategory(7, "personal medical care", "PERSONAL_CARE", "medium", "Self-directed medical care"),
    SourceCategory(20, "food preparation, cooking", "CHORES", "high", "Meal preparation is household work, not EAT"),
    SourceCategory(21, "set table, wash/put away dishes", "CHORES", "high", "Kitchen household task"),
    SourceCategory(22, "cleaning", "CHORES", "high", "Explicit cleaning"),
    SourceCategory(23, "laundry, ironing, clothing repair", "CHORES", "high", "Household upkeep"),
    SourceCategory(24, "home repairs, maintain vehicle", "CHORES", "medium", "Domestic maintenance; vehicle use not a trip"),
    SourceCategory(25, "other domestic work", "CHORES", "medium", "Source-classified domestic work"),
)
DOMAIN_ORDER = ("PERSONAL_CARE", "CHORES")
SOURCE_BY_CODE = {entry.code: entry for entry in SOURCE_CATEGORIES}


@dataclass(frozen=True)
class BehaviorDomainCandidate:
    name: str
    included_source_categories: tuple[int, ...]
    minute_share: float
    episode_share: float
    cumulative_minute_coverage: float
    cumulative_episode_coverage: float
    mapping_confidence: str
    rationale: str
    recommended: bool


def classify(code: int, baseline: str, domains: tuple[str, ...]) -> str:
    if baseline != "OTHER":
        return baseline
    source = SOURCE_BY_CODE.get(code)
    return source.domain if source and source.domain in domains else "OTHER"


def select_minimal_ontology(coverages: dict[tuple[str, ...], float], target: float = TARGET_MINUTE_COVERAGE) -> tuple[str, ...] | None:
    """Consider only the two explicit domains, minimizing category count."""
    if not (0 <= target <= 1):
        raise ValueError("target must be a fraction")
    for count in range(3):
        for domains in combinations(DOMAIN_ORDER, count):
            if coverages.get(domains, -1) >= target:
                return domains
    return None
