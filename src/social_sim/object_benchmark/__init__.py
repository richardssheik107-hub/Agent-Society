"""Object-set necessity benchmark: free generation vs catalog Top-K vs hybrid."""

from .benchmark import (
    ATTRIBUTE_RANGES,
    ObjectChoiceEvaluator,
    build_choice_prompt,
    build_offline_probe_rows,
    parse_object_choice,
    required_effect_fields,
    summarize_rows,
    validate_effect_attributes,
)
from .catalog import ObjectCatalog, build_scenarios, build_synthetic_catalog
from .models import ArchitectureArm, CatalogObject, ObjectDomain, ObjectScenario

__all__ = [
    "ArchitectureArm",
    "ATTRIBUTE_RANGES",
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
    "required_effect_fields",
    "summarize_rows",
    "validate_effect_attributes",
]
