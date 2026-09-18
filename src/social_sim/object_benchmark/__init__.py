"""Object-set necessity benchmark: free generation vs catalog Top-K vs hybrid."""

from .benchmark import (
    ObjectChoiceEvaluator,
    build_choice_prompt,
    build_offline_probe_rows,
    parse_object_choice,
    summarize_rows,
)
from .catalog import ObjectCatalog, build_scenarios, build_synthetic_catalog
from .models import ArchitectureArm, CatalogObject, ObjectDomain, ObjectScenario

__all__ = [
    "ArchitectureArm",
    "CatalogObject",
    "ObjectCatalog",
    "ObjectChoiceEvaluator",
    "ObjectDomain",
    "ObjectScenario",
    "build_choice_prompt",
    "build_offline_probe_rows",
    "build_scenarios",
    "build_synthetic_catalog",
    "parse_object_choice",
    "summarize_rows",
]
