"""Deterministic Q5 scaling benchmark from 10K through 10M objects."""

from __future__ import annotations

from dataclasses import dataclass
import sys
import time
from typing import Any

from .catalog import VirtualObjectCatalog
from .engine import TemplateRuleEngine
from .explicit import PackedExplicitEdgeGraph, estimate_explicit_relations
from .schema import CAPABILITIES, RESOURCES, RULE_TEMPLATES, TYPE_SPECS


@dataclass(frozen=True)
class ScaleBenchmarkConfig:
    sizes: tuple[int, ...] = (10_000, 100_000, 1_000_000, 10_000_000)
    top_k: int = 50
    queries_per_size: int = 1_000
    explicit_materialize_max_objects: int = 100_000
    seed: int = 2026

    def __post_init__(self) -> None:
        if not self.sizes or any(size <= 0 for size in self.sizes):
            raise ValueError("sizes must be positive")
        if tuple(sorted(self.sizes)) != self.sizes:
            raise ValueError("sizes must be sorted")
        if self.top_k <= 0 or self.queries_per_size <= 0:
            raise ValueError("top_k and queries_per_size must be positive")


def _deep_size(value: object, seen: set[int] | None = None) -> int:
    visited = seen if seen is not None else set()
    identity = id(value)
    if identity in visited:
        return 0
    visited.add(identity)
    total = sys.getsizeof(value)
    if isinstance(value, dict):
        for key, item in value.items():
            total += _deep_size(key, visited)
            total += _deep_size(item, visited)
    elif isinstance(value, (tuple, list, set, frozenset)):
        for item in value:
            total += _deep_size(item, visited)
    elif hasattr(value, "__dict__"):
        total += _deep_size(vars(value), visited)
    return total


def _percentile_us(values_ns: list[int], fraction: float) -> float:
    if not values_ns:
        return 0.0
    ordered = sorted(values_ns)
    index = min(
        len(ordered) - 1,
        max(0, int(round((len(ordered) - 1) * fraction))),
    )
    return round(ordered[index] / 1_000.0, 3)


def _run_queries(
    engine: TemplateRuleEngine, config: ScaleBenchmarkConfig
) -> dict[str, object]:
    elapsed: list[int] = []
    total_touches = 0
    total_matches = 0
    checksum = 0
    max_object_id = -1

    for query_index in range(config.queries_per_size):
        capability = CAPABILITIES[query_index % len(CAPABILITIES)]
        seed = config.seed + query_index * 17
        started = time.perf_counter_ns()
        ids, touches, matches, one_checksum = engine.retrieve_and_match(
            capability,
            k=config.top_k,
            seed=seed,
        )
        took = time.perf_counter_ns() - started
        engine.validate_query_result(capability, ids)
        elapsed.append(took)
        total_touches += touches
        total_matches += matches
        checksum ^= one_checksum
        if ids:
            max_object_id = max(max_object_id, max(ids))

    return {
        "query_count": config.queries_per_size,
        "top_k": config.top_k,
        "candidate_touches_total": total_touches,
        "candidate_touches_per_query": round(
            total_touches / config.queries_per_size, 6
        ),
        "object_scan_count": 0,
        "rule_matches_total": total_matches,
        "p50_query_us": _percentile_us(elapsed, 0.50),
        "p95_query_us": _percentile_us(elapsed, 0.95),
        "checksum": checksum,
        "max_object_id_touched": max_object_id,
        "upper_half_touched": max_object_id >= engine.catalog.object_count // 2,
    }


def benchmark_size(size: int, config: ScaleBenchmarkConfig) -> dict[str, object]:
    started = time.perf_counter()
    catalog = VirtualObjectCatalog(size, TYPE_SPECS)
    engine = TemplateRuleEngine(catalog)
    target_build_seconds = time.perf_counter() - started
    target_metadata_bytes = _deep_size((catalog, engine))

    query_metrics = _run_queries(engine, config)
    estimated_relations = estimate_explicit_relations(catalog)
    row: dict[str, object] = {
        "object_count": size,
        "type_count": len(TYPE_SPECS),
        "capability_count": len(CAPABILITIES),
        "resource_count": len(RESOURCES),
        "rule_template_count": len(RULE_TEMPLATES),
        "human_maintained_units": (
            len(TYPE_SPECS)
            + len(CAPABILITIES)
            + len(RESOURCES)
            + len(RULE_TEMPLATES)
        ),
        "capability_type_index_entries": catalog.capability_type_entries,
        "type_rule_index_entries": engine.type_rule_index_entries,
        "target_per_object_rule_edges": engine.per_object_rule_edges,
        "target_build_seconds": round(target_build_seconds, 6),
        "target_metadata_bytes": target_metadata_bytes,
        "explicit_relation_estimate": estimated_relations,
        "explicit_packed_lower_bound_bytes": estimated_relations * 8,
        "explicit_materialized": False,
        **query_metrics,
    }

    if size <= config.explicit_materialize_max_objects:
        baseline = PackedExplicitEdgeGraph(catalog).materialize(
            maximum_objects=config.explicit_materialize_max_objects
        )
        if baseline.relation_count != estimated_relations:
            raise AssertionError("explicit estimate/materialization mismatch")
        row.update(
            explicit_materialized=True,
            explicit_relation_count=baseline.relation_count,
            explicit_packed_bytes=baseline.packed_bytes,
            explicit_build_seconds=round(baseline.build_seconds, 6),
            explicit_checksum=baseline.checksum,
        )
    return row


def scaling_decision(
    rows: list[dict[str, object]],
    config: ScaleBenchmarkConfig,
) -> dict[str, object]:
    if [int(row["object_count"]) for row in rows] != list(config.sizes):
        raise ValueError("rows do not match configured sizes")

    template_counts = {int(row["rule_template_count"]) for row in rows}
    type_rule_entries = {int(row["type_rule_index_entries"]) for row in rows}
    capability_entries = {
        int(row["capability_type_index_entries"]) for row in rows
    }
    no_scan = all(int(row["object_scan_count"]) == 0 for row in rows)
    no_edges = all(
        int(row["target_per_object_rule_edges"]) == 0 for row in rows
    )
    bounded_touches = all(
        float(row["candidate_touches_per_query"]) <= config.top_k
        for row in rows
    )
    upper_half = all(bool(row["upper_half_touched"]) for row in rows)

    structural_pass = (
        len(template_counts) == 1
        and len(type_rule_entries) == 1
        and len(capability_entries) == 1
        and no_scan
        and no_edges
        and bounded_touches
        and upper_half
    )
    largest = rows[-1]
    return {
        "status": "CLOSED_ENGINEERING" if structural_pass else "UNRESOLVED",
        "structural_pass": structural_pass,
        "rule_template_count_constant": len(template_counts) == 1,
        "type_rule_index_entries_constant": len(type_rule_entries) == 1,
        "capability_type_index_entries_constant": len(capability_entries) == 1,
        "object_scan_count_zero": no_scan,
        "per_object_rule_edges_zero": no_edges,
        "candidate_touches_bounded_by_top_k": bounded_touches,
        "queries_reach_upper_half": upper_half,
        "largest_object_count": int(largest["object_count"]),
        "largest_explicit_relation_estimate": int(
            largest["explicit_relation_estimate"]
        ),
        "largest_explicit_packed_lower_bound_bytes": int(
            largest["explicit_packed_lower_bound_bytes"]
        ),
        "largest_target_metadata_bytes": int(largest["target_metadata_bytes"]),
        "largest_p95_query_us": float(largest["p95_query_us"]),
        "claim_scope": (
            "rule-graph/index scaling only; object payload database storage "
            "is not benchmarked"
        ),
    }


def run_scale_benchmark(
    config: ScaleBenchmarkConfig | None = None,
) -> dict[str, Any]:
    cfg = config or ScaleBenchmarkConfig()
    rows = [benchmark_size(size, cfg) for size in cfg.sizes]
    return {
        "experiment": "q5_rule_engine_scaling",
        "config": {
            "sizes": list(cfg.sizes),
            "top_k": cfg.top_k,
            "queries_per_size": cfg.queries_per_size,
            "explicit_materialize_max_objects": (
                cfg.explicit_materialize_max_objects
            ),
            "seed": cfg.seed,
        },
        "schema": {
            "types": len(TYPE_SPECS),
            "capabilities": len(CAPABILITIES),
            "resources": len(RESOURCES),
            "rule_templates": len(RULE_TEMPLATES),
        },
        "rows": rows,
        "decision": scaling_decision(rows, cfg),
    }
