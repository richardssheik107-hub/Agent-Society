"""Template-indexed rule matching for a large Object Set."""

from __future__ import annotations

from .catalog import VirtualObjectCatalog
from .models import RuleTemplate
from .schema import RULE_TEMPLATES


class TemplateRuleEngine:
    """Match rules through type indexes; never create per-object rule edges."""

    def __init__(
        self,
        catalog: VirtualObjectCatalog,
        rule_templates: tuple[RuleTemplate, ...] = RULE_TEMPLATES,
    ) -> None:
        self.catalog = catalog
        self.rule_templates = rule_templates
        self._rules_by_type: dict[int, tuple[RuleTemplate, ...]] = {}
        self._rules_by_action: dict[str, RuleTemplate] = {}
        for rule in rule_templates:
            if rule.action in self._rules_by_action:
                raise ValueError("rule actions must be unique in this benchmark")
            self._rules_by_action[rule.action] = rule
        for spec in catalog.type_specs:
            self._rules_by_type[spec.type_id] = tuple(
                rule for rule in rule_templates
                if rule.required_capabilities <= spec.capabilities
            )

    @property
    def type_rule_index_entries(self) -> int:
        return sum(len(rules) for rules in self._rules_by_type.values())

    @property
    def per_object_rule_edges(self) -> int:
        return 0

    def rules_for_object(self, object_id: int) -> tuple[RuleTemplate, ...]:
        return self._rules_by_type[self.catalog.type_id_for(object_id)]

    def action_allowed(self, object_id: int, action: str) -> bool:
        return any(rule.action == action for rule in self.rules_for_object(object_id))

    def effect_resources(self, object_id: int, action: str) -> tuple[str, ...]:
        for rule in self.rules_for_object(object_id):
            if rule.action == action:
                return rule.affected_resources
        return ()

    def retrieve_and_match(
        self, capability: str, *, k: int = 50, seed: int = 0
    ) -> tuple[tuple[int, ...], int, int, int]:
        retrieval = self.catalog.retrieve(capability, k=k, seed=seed)
        matches = 0
        checksum = 0
        for object_id in retrieval.object_ids:
            rules = self.rules_for_object(object_id)
            matches += len(rules)
            checksum ^= (object_id + 1) * (len(rules) + 17)
        return retrieval.object_ids, retrieval.candidate_touches, matches, checksum

    def validate_query_result(self, capability: str, object_ids: tuple[int, ...]) -> None:
        if any(not self.catalog.has_capability(object_id, capability) for object_id in object_ids):
            raise AssertionError("retrieval returned an object without requested capability")
