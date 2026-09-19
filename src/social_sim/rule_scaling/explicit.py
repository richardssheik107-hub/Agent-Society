"""Naive explicit object-rule-resource graph for a bounded comparison baseline."""

from __future__ import annotations

from array import array
from dataclasses import dataclass
import time

from .catalog import VirtualObjectCatalog
from .models import RuleTemplate
from .schema import RESOURCES, RULE_TEMPLATES


_NO_RESOURCE = 255


def applicable_rules(
    capabilities: frozenset[str],
    rules: tuple[RuleTemplate, ...] = RULE_TEMPLATES,
) -> tuple[RuleTemplate, ...]:
    return tuple(rule for rule in rules if rule.required_capabilities <= capabilities)


def relations_per_type(
    catalog: VirtualObjectCatalog,
    rules: tuple[RuleTemplate, ...] = RULE_TEMPLATES,
) -> dict[int, int]:
    result: dict[int, int] = {}
    for spec in catalog.type_specs:
        result[spec.type_id] = sum(
            1 + len(rule.affected_resources)
            for rule in applicable_rules(spec.capabilities, rules)
        )
    return result


def estimate_explicit_relations(
    catalog: VirtualObjectCatalog,
    rules: tuple[RuleTemplate, ...] = RULE_TEMPLATES,
) -> int:
    per_type = relations_per_type(catalog, rules)
    return sum(
        catalog.count_for_type(type_id) * relation_count
        for type_id, relation_count in per_type.items()
    )


@dataclass(frozen=True)
class ExplicitMaterialization:
    object_count: int
    relation_count: int
    packed_bytes: int
    build_seconds: float
    checksum: int


class PackedExplicitEdgeGraph:
    """Optimistic baseline using packed uint64 relations."""

    def __init__(
        self,
        catalog: VirtualObjectCatalog,
        rules: tuple[RuleTemplate, ...] = RULE_TEMPLATES,
    ) -> None:
        self.catalog = catalog
        self.rules = rules
        self.resource_ids = {name: index for index, name in enumerate(RESOURCES)}

    @staticmethod
    def _encode(object_id: int, rule_id: int, resource_id: int) -> int:
        return (object_id << 24) | (rule_id << 8) | resource_id

    def materialize(self, *, maximum_objects: int = 100_000) -> ExplicitMaterialization:
        if self.catalog.object_count > maximum_objects:
            raise ValueError("explicit materialization intentionally capped")
        started = time.perf_counter()
        packed = array("Q")
        checksum = 0
        for object_id in range(self.catalog.object_count):
            capabilities = self.catalog.type_for(object_id).capabilities
            for rule in applicable_rules(capabilities, self.rules):
                encoded = self._encode(object_id, rule.rule_id, _NO_RESOURCE)
                packed.append(encoded)
                checksum ^= encoded
                for resource in rule.affected_resources:
                    encoded = self._encode(
                        object_id, rule.rule_id, self.resource_ids[resource]
                    )
                    packed.append(encoded)
                    checksum ^= encoded
        elapsed = time.perf_counter() - started
        return ExplicitMaterialization(
            object_count=self.catalog.object_count,
            relation_count=len(packed),
            packed_bytes=len(packed) * packed.itemsize,
            build_seconds=elapsed,
            checksum=checksum,
        )
