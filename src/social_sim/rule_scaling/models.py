"""Small immutable schemas for the Q5 scaling benchmark."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TypeSpec:
    type_id: int
    name: str
    capabilities: frozenset[str]

    def __post_init__(self) -> None:
        if self.type_id < 0 or not self.name:
            raise ValueError("invalid type spec")
        if not self.capabilities:
            raise ValueError("type must expose at least one capability")


@dataclass(frozen=True)
class RuleTemplate:
    rule_id: int
    action: str
    required_capabilities: frozenset[str]
    affected_resources: tuple[str, ...]
    precondition_count: int

    def __post_init__(self) -> None:
        if self.rule_id < 0 or not self.action:
            raise ValueError("invalid rule template")
        if not self.required_capabilities:
            raise ValueError("rule needs at least one required capability")
        if not self.affected_resources:
            raise ValueError("rule needs at least one affected resource")
        if self.precondition_count < 1:
            raise ValueError("precondition_count must be positive")


@dataclass(frozen=True)
class RetrievalResult:
    object_ids: tuple[int, ...]
    candidate_touches: int
    object_scan_count: int = 0
