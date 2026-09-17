"""High-confidence, lexicon-reviewed ATUS mapping with OTHER fallback."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .models import HumanActivityType


@dataclass(frozen=True)
class MappingRule:
    prefix: str
    label: str
    canonical: HumanActivityType
    rationale: str
    confidence: str


class ActivityMapping:
    def __init__(self, rules: tuple[MappingRule, ...], version: str, other_labels: dict[str, str] | None = None) -> None:
        self.rules = tuple(sorted(rules, key=lambda rule: -len(rule.prefix)))
        self.version = version
        self.other_labels = dict(other_labels or {})

    def classify(self, code: str) -> tuple[HumanActivityType, str]:
        for rule in self.rules:
            if code.startswith(rule.prefix):
                return rule.canonical, rule.label
        for prefix in sorted(self.other_labels, key=len, reverse=True):
            if code.startswith(prefix):
                return HumanActivityType.OTHER, self.other_labels[prefix]
        return HumanActivityType.OTHER, "Unmapped ATUS activity"


def load_mapping(path: Path) -> ActivityMapping:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    rules = tuple(MappingRule(prefix=str(row["prefix"]), label=row["label"], canonical=HumanActivityType(row["canonical"]), rationale=row["rationale"], confidence=row["confidence"]) for row in data["rules"])
    if len({rule.prefix for rule in rules}) != len(rules):
        raise ValueError("duplicate mapping prefixes")
    return ActivityMapping(rules, data["version"], data.get("other_labels"))
