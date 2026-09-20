"""No-network correctness and scaling gates for Research Q5."""

from __future__ import annotations

from social_sim.rule_scaling import (
    CAPABILITIES,
    RESOURCES,
    RULE_TEMPLATES,
    TYPE_SPECS,
    PackedExplicitEdgeGraph,
    ScaleBenchmarkConfig,
    TemplateRuleEngine,
    VirtualObjectCatalog,
    estimate_explicit_relations,
    run_scale_benchmark,
)
from social_sim.rule_scaling.explicit import relations_per_type


def test_schema_is_small_unique_and_human_maintainable() -> None:
    assert len(TYPE_SPECS) == 10
    assert len(CAPABILITIES) >= 10
    assert len(RESOURCES) == 16
    assert len(RULE_TEMPLATES) == 11
    assert len({spec.type_id for spec in TYPE_SPECS}) == len(TYPE_SPECS)
    assert len({rule.action for rule in RULE_TEMPLATES}) == len(RULE_TEMPLATES)


def test_virtual_catalog_addresses_10m_without_materializing_objects() -> None:
    catalog = VirtualObjectCatalog(10_000_000, TYPE_SPECS)
    assert catalog.type_for(9_999_999).name
    assert sum(
        catalog.count_for_type(spec.type_id) for spec in TYPE_SPECS
    ) == 10_000_000
    assert not hasattr(catalog, "objects")


def test_topk_retrieval_is_bounded_deterministic_and_correct() -> None:
    catalog = VirtualObjectCatalog(10_000_000, TYPE_SPECS)
    first = catalog.retrieve("purchasable", k=50, seed=2026)
    second = catalog.retrieve("purchasable", k=50, seed=2026)
    assert first == second
    assert len(first.object_ids) == 50
    assert first.candidate_touches == 50
    assert first.object_scan_count == 0
    assert all(
        catalog.has_capability(object_id, "purchasable")
        for object_id in first.object_ids
    )
    assert max(first.object_ids) >= 5_000_000


def test_rule_matching_depends_on_type_not_object_count() -> None:
    small = TemplateRuleEngine(VirtualObjectCatalog(10_000, TYPE_SPECS))
    large = TemplateRuleEngine(VirtualObjectCatalog(10_000_000, TYPE_SPECS))
    assert small.type_rule_index_entries == large.type_rule_index_entries
    assert small.per_object_rule_edges == large.per_object_rule_edges == 0
    for object_id in (0, 1, 5, 9):
        assert [rule.action for rule in small.rules_for_object(object_id)] == [
            rule.action for rule in large.rules_for_object(object_id)
        ]


def test_action_and_effect_lookup_are_template_driven() -> None:
    engine = TemplateRuleEngine(VirtualObjectCatalog(10_000, TYPE_SPECS))
    assert engine.action_allowed(0, "EAT")
    assert not engine.action_allowed(1, "EAT")
    assert engine.effect_resources(0, "EAT") == (
        "inventory", "hunger", "energy"
    )
    assert engine.action_allowed(1, "PLAY")


def test_explicit_estimate_matches_packed_materialization() -> None:
    catalog = VirtualObjectCatalog(10_000, TYPE_SPECS)
    estimate = estimate_explicit_relations(catalog)
    materialized = PackedExplicitEdgeGraph(catalog).materialize(
        maximum_objects=100_000
    )
    assert estimate == materialized.relation_count
    assert materialized.packed_bytes == estimate * 8


def test_explicit_relations_scale_linearly_while_templates_stay_constant() -> None:
    small = VirtualObjectCatalog(10_000, TYPE_SPECS)
    large = VirtualObjectCatalog(10_000_000, TYPE_SPECS)
    assert (
        estimate_explicit_relations(large)
        == estimate_explicit_relations(small) * 1000
    )
    assert len(RULE_TEMPLATES) == 11
    assert sum(relations_per_type(small).values()) > len(RULE_TEMPLATES)


def test_full_benchmark_reaches_10m_and_closes_structural_question() -> None:
    result = run_scale_benchmark(
        ScaleBenchmarkConfig(
            sizes=(10_000, 100_000, 1_000_000, 10_000_000),
            top_k=20,
            queries_per_size=40,
            explicit_materialize_max_objects=10_000,
            seed=2026,
        )
    )
    decision = result["decision"]
    assert decision["status"] == "CLOSED_ENGINEERING"
    assert decision["largest_object_count"] == 10_000_000
    assert decision["object_scan_count_zero"]
    assert decision["per_object_rule_edges_zero"]
    assert decision["candidate_touches_bounded_by_top_k"]
    assert result["rows"][-1]["explicit_materialized"] is False


def test_explicit_materialization_is_refused_above_safety_cap() -> None:
    graph = PackedExplicitEdgeGraph(
        VirtualObjectCatalog(100_001, TYPE_SPECS)
    )
    try:
        graph.materialize(maximum_objects=100_000)
    except ValueError as exc:
        assert "capped" in str(exc)
    else:
        raise AssertionError("unsafe explicit materialization was not refused")


def test_unknown_capability_returns_empty_without_scan() -> None:
    result = VirtualObjectCatalog(10_000_000, TYPE_SPECS).retrieve(
        "does_not_exist",
        k=50,
        seed=1,
    )
    assert result.object_ids == ()
    assert result.candidate_touches == 0
    assert result.object_scan_count == 0


def test_10m_explicit_lower_bound_is_large_but_target_edges_are_zero() -> None:
    catalog = VirtualObjectCatalog(10_000_000, TYPE_SPECS)
    engine = TemplateRuleEngine(catalog)
    relations = estimate_explicit_relations(catalog)
    assert relations == 75_000_000
    assert relations * 8 == 600_000_000
    assert engine.per_object_rule_edges == 0
