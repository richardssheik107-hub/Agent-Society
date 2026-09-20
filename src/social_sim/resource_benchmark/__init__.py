"""Independent Research Q4 resource-visibility benchmark."""

from .benchmark import (
    build_offline_rows,
    build_schedule,
    capability_summary,
    parse_resource_proposal,
)
from .context import (
    build_resource_context,
    build_resource_prompt,
    context_without_resources,
    fixed_context_signature,
)
from .models import (
    PilotConfig,
    ResourceLevel,
    ResourceProjection,
    ResourceScenario,
    ResourceTruth,
    ScheduleEntry,
)
from .scenarios import (
    AVAILABLE_ACTIONS,
    AVAILABLE_TARGETS,
    build_scenarios,
    scenario_world,
    smoke_scenarios,
)
from .schema import (
    ALL_RESOURCE_FIELDS,
    R8_FIELDS,
    R16_FIELDS,
    R32_FIELDS,
    R64_FIELDS,
    nested_resource_schema,
    projection_is_nested,
    resource_fields,
)
from .scorer import score_proposal, summarize_resource_rows

__all__ = [
    "ALL_RESOURCE_FIELDS", "AVAILABLE_ACTIONS", "AVAILABLE_TARGETS",
    "PilotConfig", "R8_FIELDS", "R16_FIELDS", "R32_FIELDS", "R64_FIELDS",
    "ResourceLevel", "ResourceProjection", "ResourceScenario", "ResourceTruth",
    "ScheduleEntry", "build_offline_rows", "build_resource_context",
    "build_resource_prompt", "build_schedule", "build_scenarios", "capability_summary",
    "context_without_resources", "fixed_context_signature", "nested_resource_schema",
    "parse_resource_proposal", "projection_is_nested", "resource_fields", "scenario_world",
    "score_proposal", "smoke_scenarios", "summarize_resource_rows",
]
