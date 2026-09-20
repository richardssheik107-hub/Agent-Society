"""Evaluation, prompts, offline system probe, and aggregate metrics."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from math import isfinite
import re

from .catalog import ObjectCatalog
from .models import ArchitectureArm, CatalogObject, ObjectDomain, ObjectScenario


_REQUIRED_CAPABILITY: dict[ObjectDomain, str] = {
    ObjectDomain.FOOD: "edible",
    ObjectDomain.GAME: "playable",
    ObjectDomain.VIDEO: "watchable",
    ObjectDomain.PRODUCT: "tradable",
    ObjectDomain.ASSET: "usable_asset",
}

_EFFECT_FIELDS: dict[ObjectDomain, tuple[str, ...]] = {
    ObjectDomain.FOOD: ("price", "calories", "satiety"),
    ObjectDomain.GAME: ("price", "session_minutes", "sociality"),
    ObjectDomain.VIDEO: ("price", "duration_minutes", "episode_count"),
    ObjectDomain.PRODUCT: ("price", "durability", "utility"),
    ObjectDomain.ASSET: ("value", "liquidity", "currency"),
}

ATTRIBUTE_RANGES: dict[ObjectDomain, dict[str, tuple[float, float] | str]] = {
    ObjectDomain.FOOD: {
        "price": (0.0, 1000.0),
        "calories": (0.0, 5000.0),
        "satiety": (0.0, 1.0),
    },
    ObjectDomain.GAME: {
        "price": (0.0, 1000.0),
        "session_minutes": (1.0, 1440.0),
        "sociality": (0.0, 1.0),
    },
    ObjectDomain.VIDEO: {
        "price": (0.0, 1000.0),
        "duration_minutes": (1.0, 1000.0),
        "episode_count": (1.0, 10000.0),
    },
    ObjectDomain.PRODUCT: {
        "price": (0.0, 1_000_000.0),
        "durability": (0.0, 1.0),
        "utility": (0.0, 1.0),
    },
    ObjectDomain.ASSET: {
        "value": (0.0, 1_000_000_000_000.0),
        "liquidity": (0.0, 1.0),
        "currency": "uppercase_short_string",
    },
}


def required_effect_fields(domain: ObjectDomain) -> tuple[str, ...]:
    return _EFFECT_FIELDS[domain]


def validate_effect_attributes(
    domain: ObjectDomain, attributes: object
) -> tuple[bool, tuple[str, ...], tuple[str, ...]]:
    """Validate only required fields and bounded plausibility.

    Returns ``(all_valid, missing_fields, invalid_fields)``. Extra model fields
    are retained but do not affect the simulator effect contract.
    """
    if not isinstance(attributes, dict):
        return False, _EFFECT_FIELDS[domain], ()
    missing: list[str] = []
    invalid: list[str] = []
    for field in _EFFECT_FIELDS[domain]:
        if field not in attributes:
            missing.append(field)
            continue
        value = attributes[field]
        if domain is ObjectDomain.ASSET and field == "currency":
            valid = isinstance(value, str) and bool(re.fullmatch(r"[A-Z]{1,5}", value))
        else:
            valid = (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and isfinite(float(value))
                and ATTRIBUTE_RANGES[domain][field][0] <= float(value) <= ATTRIBUTE_RANGES[domain][field][1]  # type: ignore[index]
            )
        if not valid:
            invalid.append(field)
    return not missing and not invalid, tuple(missing), tuple(invalid)


def parse_object_choice(raw_text: str) -> dict[str, object]:
    """Strict unified object protocol parser; no fuzzy repair or second call."""
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError("INVALID_JSON") from exc
    if not isinstance(payload, dict) or set(payload) != {"object", "attributes"}:
        raise ValueError("INVALID_OBJECT_SCHEMA")
    value = payload["object"]
    if not isinstance(value, str) or not value.strip() or len(value) > 128:
        raise ValueError("INVALID_OBJECT_VALUE")
    attributes = payload["attributes"]
    if not isinstance(attributes, dict) or any(
        not isinstance(key, str) or not isinstance(attr_value, (str, int, float, bool))
        for key, attr_value in attributes.items()
    ):
        raise ValueError("INVALID_ATTRIBUTES_SCHEMA")
    return {"object": value.strip(), "attributes": attributes}


def _compact_candidate(item: CatalogObject) -> str:
    attrs = item.attributes
    if item.domain is ObjectDomain.FOOD:
        detail = f"price={attrs['price']},cal={attrs['calories']}"
    elif item.domain is ObjectDomain.GAME:
        detail = f"price={attrs['price']},minutes={attrs['session_minutes']}"
    elif item.domain is ObjectDomain.VIDEO:
        detail = f"minutes={attrs['duration_minutes']},episodes={attrs['episode_count']}"
    elif item.domain is ObjectDomain.PRODUCT:
        detail = f"price={attrs['price']},utility={attrs['utility']}"
    else:
        detail = f"value={attrs['value']},liquidity={attrs['liquidity']}"
    return f"{item.canonical_id}|{item.name}|{detail}"


def build_choice_prompt(
    scenario: ObjectScenario,
    arm: ArchitectureArm,
    candidates: tuple[CatalogObject, ...] = (),
) -> tuple[str, str]:
    required = ", ".join(_EFFECT_FIELDS[scenario.domain])
    system = (
        'Choose one concrete object. Return JSON only in exactly this shape: '
        '{"object":"...","attributes":{}}. Do not add top-level fields or explain reasoning. '
        f"The simulator-required {scenario.domain.value} attributes are: {required}."
    )
    parts = [
        f"domain={scenario.domain.value}",
        f"intent={scenario.intent}",
        f"preferences={','.join(scenario.preference_tags)}",
    ]
    if scenario.budget is not None:
        parts.append(f"budget={scenario.budget:.2f}")
    if scenario.history_ids:
        parts.append(f"recent_objects={','.join(scenario.history_ids[-3:])}")
    if arm is ArchitectureArm.CATALOG_TOPK:
        parts.append("choose exactly one available candidate ID; attributes may be {}:")
        parts.extend(_compact_candidate(item) for item in candidates)
    elif arm is ArchitectureArm.HYBRID:
        parts.append(
            "choose one available candidate ID with attributes {}, or NEW:<short object name> "
            f"with complete {required} attributes if none fits:"
        )
        parts.extend(_compact_candidate(item) for item in candidates)
    else:
        parts.append(
            "name any concrete object you would choose; no catalog is shown. "
            f"You must provide complete attributes: {required}."
        )
    return system, "\n".join(parts)


class ObjectChoiceEvaluator:
    def __init__(self, catalog: ObjectCatalog, *, top_k: int = 10) -> None:
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        self.catalog = catalog
        self.top_k = top_k

    def evaluate(
        self,
        scenario: ObjectScenario,
        arm: ArchitectureArm,
        raw_choice: str | dict[str, object],
    ) -> dict[str, object]:
        choice = {"object": raw_choice, "attributes": {}} if isinstance(raw_choice, str) else raw_choice
        object_name = choice.get("object")
        model_attributes = choice.get("attributes", {})
        if not isinstance(object_name, str) or not isinstance(model_attributes, dict):
            raise ValueError("INVALID_OBJECT_SCHEMA")
        candidates = self.catalog.retrieve(scenario, k=self.top_k)
        candidate_ids = {item.canonical_id for item in candidates}
        novel_created = False
        candidate_compliant: bool | None
        attribute_source = "NONE"
        catalog_accidental_match = False
        if arm is ArchitectureArm.LLM_ONLY:
            accidental = self.catalog.resolve(object_name)
            catalog_accidental_match = accidental is not None and accidental.domain is scenario.domain
            record = self.catalog.instantiate_model_object(
                object_name, scenario.domain, model_attributes
            )
            candidate_compliant = None
            attribute_source = "MODEL_ESTIMATED"
        elif arm is ArchitectureArm.HYBRID and object_name.startswith("NEW:"):
            if not object_name[4:].strip():
                raise ValueError("INVALID_OBJECT_VALUE")
            record = self.catalog.instantiate_novel(
                object_name[4:].strip(), scenario.domain, model_attributes
            )
            novel_created = True
            candidate_compliant = False
            attribute_source = "MODEL_ESTIMATED"
        else:
            record = self.catalog.resolve(object_name)
            candidate_compliant = (
                record is not None and record.canonical_id in candidate_ids
            )
            attribute_source = "CATALOG_AUTHORITATIVE" if candidate_compliant else "NONE"

        resolvable = record is not None and (arm is not ArchitectureArm.LLM_ONLY or catalog_accidental_match)
        domain_match = bool(record and record.domain is scenario.domain)
        capability = _REQUIRED_CAPABILITY[scenario.domain]
        required = _EFFECT_FIELDS[scenario.domain]
        effect_attributes = dict(record.attributes) if record else dict(model_attributes)
        if arm is ArchitectureArm.LLM_ONLY or novel_created:
            effect_attributes = dict(model_attributes)
        attributes_valid, missing_fields, invalid_fields = validate_effect_attributes(
            scenario.domain, effect_attributes
        )
        usable_fields = sum(
            field not in missing_fields and field not in invalid_fields for field in required
        )
        executable = bool(
            record
            and domain_match
            and capability in record.capabilities
            and (arm is ArchitectureArm.LLM_ONLY or candidate_compliant or novel_created)
            and attributes_valid
        )
        usable_effect_coverage = usable_fields / len(required)
        authoritative_fields = sum(
            field in effect_attributes and field not in (record.estimated_fields if record else ())
            for field in required
        ) if attribute_source == "CATALOG_AUTHORITATIVE" else 0
        model_estimated_fields = (
            sum(field in model_attributes for field in required)
            if arm is ArchitectureArm.LLM_ONLY or novel_created
            else 0
        )
        authoritative_effect_coverage = authoritative_fields / len(required)
        model_estimated_field_rate = model_estimated_fields / len(required)

        return {
            "scenario_id": scenario.scenario_id,
            "domain": scenario.domain.value,
            "arm": arm.value,
            "choice": object_name,
            "attributes": dict(model_attributes),
            "canonical_id": record.canonical_id if record else None,
            "resolvable": resolvable,
            "catalog_accidental_match": catalog_accidental_match,
            "domain_match": domain_match,
            "candidate_compliant": candidate_compliant,
            "structured_object": True,
            "runtime_executable": executable,
            "executable": executable,
            "usable_effect_coverage": round(usable_effect_coverage, 6),
            "authoritative_effect_coverage": round(authoritative_effect_coverage, 6),
            "exact_effect_coverage": round(authoritative_effect_coverage, 6),
            "model_estimated_field_rate": round(model_estimated_field_rate, 6),
            "attribute_source": attribute_source,
            "attribute_plausible": attributes_valid,
            "missing_attribute_fields": list(missing_fields),
            "invalid_attribute_fields": list(invalid_fields),
            "novel_created": novel_created,
            "estimated_field_count": len(record.estimated_fields) if record else None,
            "top_k": self.top_k if arm is not ArchitectureArm.LLM_ONLY else 0,
        }


def _offline_choice(
    catalog: ObjectCatalog,
    scenario: ObjectScenario,
    arm: ArchitectureArm,
    repetition: int,
) -> dict[str, object]:
    candidates = catalog.retrieve(scenario, k=10)
    if arm is ArchitectureArm.CATALOG_TOPK:
        return {
            "object": candidates[(repetition - 1) % min(3, len(candidates))].canonical_id,
            "attributes": {},
        }
    if arm is ArchitectureArm.HYBRID:
        if (int(scenario.scenario_id[1:]) + repetition) % 4 == 0:
            return {
                "object": f"NEW:novel {scenario.preference_tags[0]} {scenario.domain.value.lower()}",
                "attributes": dict(candidates[0].attributes),
            }
        return {
            "object": candidates[(repetition - 1) % min(3, len(candidates))].canonical_id,
            "attributes": {},
        }

    # This is deliberately a systems-capability probe, not simulated model behavior:
    # A supplies a complete, plausible object description and does not need catalog resolution.
    target = candidates[(repetition - 1) % min(3, len(candidates))]
    attrs = dict(target.attributes)
    if (int(scenario.scenario_id[1:]) + repetition) % 3 == 0:
        target_name = f"unregistered {scenario.preference_tags[0]} {scenario.domain.value.lower()}"
    else:
        target_name = target.aliases[0] if target.aliases else target.name
    return {"object": target_name, "attributes": attrs}


def build_offline_probe_rows(
    catalog: ObjectCatalog | None = None,
    *,
    repetitions: int = 2,
) -> list[dict[str, object]]:
    """Run a no-LLM systems probe over 30 states × 3 arms × repetitions."""
    if repetitions <= 0:
        raise ValueError("repetitions must be positive")
    from .catalog import build_scenarios, build_synthetic_catalog

    store = catalog or build_synthetic_catalog()
    evaluator = ObjectChoiceEvaluator(store)
    rows: list[dict[str, object]] = []
    for repetition in range(1, repetitions + 1):
        for scenario in build_scenarios():
            for arm in ArchitectureArm:
                choice = _offline_choice(store, scenario, arm, repetition)
                row = evaluator.evaluate(scenario, arm, choice)
                row["repetition"] = repetition
                row["probe_kind"] = "SYSTEM_CAPABILITY_PROBE_NOT_MODEL_BEHAVIOR"
                rows.append(row)
    return rows


def summarize_rows(rows: Iterable[dict[str, object]]) -> dict[str, dict[str, float | int]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["arm"])].append(row)
    result: dict[str, dict[str, float | int]] = {}
    for arm, items in grouped.items():
        count = len(items)
        def mean(key: str) -> float:
            return sum(
                float(bool(item[key])) if isinstance(item[key], bool) else float(item[key])
                for item in items
            ) / count
        result[arm] = {
            "rows": count,
            "structured_object_rate": round(mean("structured_object"), 6),
            "runtime_executable_rate": round(mean("runtime_executable"), 6),
            "resolution_rate": round(mean("resolvable"), 6),
            "executable_rate": round(mean("runtime_executable"), 6),
            "usable_effect_coverage": round(mean("usable_effect_coverage"), 6),
            "authoritative_effect_coverage": round(mean("authoritative_effect_coverage"), 6),
            "exact_effect_coverage": round(mean("authoritative_effect_coverage"), 6),
            "model_estimated_field_rate": round(mean("model_estimated_field_rate"), 6),
            "attribute_plausible_rate": round(mean("attribute_plausible"), 6),
            "candidate_compliance_rate": round(
                sum(bool(item["candidate_compliant"]) for item in items if item["candidate_compliant"] is not None)
                / max(1, sum(item["candidate_compliant"] is not None for item in items)), 6
            ),
            "novel_creation_rate": round(mean("novel_created"), 6),
        }
    return result
