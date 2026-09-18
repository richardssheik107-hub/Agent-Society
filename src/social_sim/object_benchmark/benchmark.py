"""Evaluation, prompts, offline system probe, and aggregate metrics."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable

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


def parse_object_choice(raw_text: str) -> str:
    """Strict one-field JSON parser; no fuzzy repair and no second model call."""
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError("INVALID_JSON") from exc
    if not isinstance(payload, dict) or set(payload) != {"object"}:
        raise ValueError("INVALID_OBJECT_SCHEMA")
    value = payload["object"]
    if not isinstance(value, str) or not value.strip() or len(value) > 128:
        raise ValueError("INVALID_OBJECT_VALUE")
    return value.strip()


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
    system = (
        'Choose one concrete object. Return JSON only: {"object":"..."}. '
        "Do not explain your reasoning."
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
        parts.append("choose exactly one candidate ID:")
        parts.extend(_compact_candidate(item) for item in candidates)
    elif arm is ArchitectureArm.HYBRID:
        parts.append("choose one candidate ID, or NEW:<short object name> if none fits:")
        parts.extend(_compact_candidate(item) for item in candidates)
    else:
        parts.append("name any concrete object you would choose; no catalog is shown.")
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
        raw_choice: str,
    ) -> dict[str, object]:
        candidates = self.catalog.retrieve(scenario, k=self.top_k)
        candidate_ids = {item.canonical_id for item in candidates}
        novel_created = False
        candidate_compliant: bool | None
        if arm is ArchitectureArm.HYBRID and raw_choice.startswith("NEW:"):
            record = self.catalog.instantiate_novel(raw_choice[4:].strip(), scenario.domain)
            novel_created = True
            candidate_compliant = False
        else:
            record = self.catalog.resolve(raw_choice)
            candidate_compliant = (
                None if arm is ArchitectureArm.LLM_ONLY
                else record is not None and record.canonical_id in candidate_ids
            )

        resolvable = record is not None
        domain_match = bool(record and record.domain is scenario.domain)
        capability = _REQUIRED_CAPABILITY[scenario.domain]
        executable = bool(
            record
            and domain_match
            and capability in record.capabilities
            and (arm is not ArchitectureArm.CATALOG_TOPK or candidate_compliant)
        )
        required = _EFFECT_FIELDS[scenario.domain]
        present = sum(bool(record and field in record.attributes) for field in required)
        exact = sum(
            bool(record and field in record.attributes and field not in record.estimated_fields)
            for field in required
        )
        usable_effect_coverage = present / len(required)
        exact_effect_coverage = exact / len(required)

        return {
            "scenario_id": scenario.scenario_id,
            "domain": scenario.domain.value,
            "arm": arm.value,
            "choice": raw_choice,
            "canonical_id": record.canonical_id if record else None,
            "resolvable": resolvable,
            "domain_match": domain_match,
            "candidate_compliant": candidate_compliant,
            "executable": executable,
            "usable_effect_coverage": round(usable_effect_coverage, 6),
            "exact_effect_coverage": round(exact_effect_coverage, 6),
            "novel_created": novel_created,
            "estimated_field_count": len(record.estimated_fields) if record else None,
            "top_k": self.top_k if arm is not ArchitectureArm.LLM_ONLY else 0,
        }


def _offline_choice(
    catalog: ObjectCatalog,
    scenario: ObjectScenario,
    arm: ArchitectureArm,
    repetition: int,
) -> str:
    candidates = catalog.retrieve(scenario, k=10)
    if arm is ArchitectureArm.CATALOG_TOPK:
        return candidates[(repetition - 1) % min(3, len(candidates))].canonical_id
    if arm is ArchitectureArm.HYBRID:
        if (int(scenario.scenario_id[1:]) + repetition) % 4 == 0:
            return f"NEW:novel {scenario.preference_tags[0]} {scenario.domain.value.lower()}"
        return candidates[(repetition - 1) % min(3, len(candidates))].canonical_id

    # This is deliberately a systems-capability probe, not simulated model behavior:
    # some free names happen to map to known aliases; others are outside the store.
    if (int(scenario.scenario_id[1:]) + repetition) % 3 == 0:
        return f"unregistered {scenario.preference_tags[0]} {scenario.domain.value.lower()}"
    target = candidates[(repetition - 1) % min(3, len(candidates))]
    return target.aliases[0] if target.aliases else target.name


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
        mean = lambda key: sum(float(bool(item[key])) if isinstance(item[key], bool)
                               else float(item[key]) for item in items) / count
        result[arm] = {
            "rows": count,
            "resolution_rate": round(mean("resolvable"), 6),
            "executable_rate": round(mean("executable"), 6),
            "usable_effect_coverage": round(mean("usable_effect_coverage"), 6),
            "exact_effect_coverage": round(mean("exact_effect_coverage"), 6),
            "novel_creation_rate": round(mean("novel_created"), 6),
        }
    return result
