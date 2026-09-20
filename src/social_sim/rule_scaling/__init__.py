"""Research Q5: rule-graph scaling without per-object rule edges."""

from .benchmark import ScaleBenchmarkConfig, run_scale_benchmark, scaling_decision
from .catalog import VirtualObjectCatalog
from .engine import TemplateRuleEngine
from .explicit import PackedExplicitEdgeGraph, estimate_explicit_relations
from .schema import CAPABILITIES, RESOURCES, RULE_TEMPLATES, TYPE_SPECS

__all__ = [
    "CAPABILITIES",
    "RESOURCES",
    "RULE_TEMPLATES",
    "TYPE_SPECS",
    "PackedExplicitEdgeGraph",
    "ScaleBenchmarkConfig",
    "TemplateRuleEngine",
    "VirtualObjectCatalog",
    "estimate_explicit_relations",
    "run_scale_benchmark",
    "scaling_decision",
]
