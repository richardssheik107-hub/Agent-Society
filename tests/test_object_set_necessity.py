"""No-network gates for the Object Set Necessity benchmark."""

from __future__ import annotations

import asyncio
import json

from social_sim.decision.client import DecisionClientError, DecisionReply, DecisionResponseMetadata
from social_sim.object_benchmark import (
    ArchitectureArm,
    ObjectChoiceEvaluator,
    ObjectDomain,
    build_choice_prompt,
    build_offline_probe_rows,
    build_scenarios,
    build_synthetic_catalog,
    parse_object_choice,
    summarize_rows,
)
from social_sim.object_benchmark.benchmark import validate_effect_attributes
from social_sim.object_benchmark.real_pilot import (
    PilotConfig,
    pilot_schedule,
    run_real_pilot,
)


def test_catalog_is_large_deterministic_and_resolves_aliases() -> None:
    first = build_synthetic_catalog()
    second = build_synthetic_catalog()
    assert len(first.objects) == len(second.objects) == 1000
    assert [item.canonical_id for item in first.objects[:20]] == [
        item.canonical_id for item in second.objects[:20]
    ]
    item = first.objects[0]
    assert first.resolve(item.canonical_id) == item
    assert first.resolve(item.name) == item
    assert first.resolve(item.aliases[0]) == item


def test_thirty_scenarios_cover_five_domains() -> None:
    scenarios = build_scenarios()
    assert len(scenarios) == 30
    assert len({scenario.domain for scenario in scenarios}) == 5
    assert all(sum(s.domain is domain for s in scenarios) == 6 for domain in {s.domain for s in scenarios})


def test_topk_is_domain_scoped_bounded_and_deterministic() -> None:
    catalog = build_synthetic_catalog()
    scenario = build_scenarios()[0]
    first = catalog.retrieve(scenario, k=10)
    second = catalog.retrieve(scenario, k=10)
    assert first == second and len(first) == 10
    assert all(item.domain is scenario.domain for item in first)


def test_arm_semantics_separate_resolution_executability_and_precision() -> None:
    catalog = build_synthetic_catalog()
    scenario = build_scenarios()[0]
    evaluator = ObjectChoiceEvaluator(catalog)
    candidate = catalog.retrieve(scenario, k=10)[0]

    free_unknown = evaluator.evaluate(
        scenario,
        ArchitectureArm.LLM_ONLY,
        {
            "object": "croissant",
            "attributes": {"price": 4.5, "calories": 300, "satiety": 0.35},
        },
    )
    assert not free_unknown["resolvable"]
    assert free_unknown["runtime_executable"]
    assert free_unknown["authoritative_effect_coverage"] == 0
    assert free_unknown["model_estimated_field_rate"] == 1
    assert free_unknown["usable_effect_coverage"] == 1

    topk = evaluator.evaluate(
        scenario,
        ArchitectureArm.CATALOG_TOPK,
        {"object": candidate.canonical_id, "attributes": {}},
    )
    assert topk["resolvable"] and topk["candidate_compliant"] and topk["runtime_executable"]
    assert topk["authoritative_effect_coverage"] == 1
    assert topk["model_estimated_field_rate"] == 0

    hybrid = evaluator.evaluate(
        scenario,
        ArchitectureArm.HYBRID,
        {
            "object": "NEW:handmade moon bread",
            "attributes": {"price": 4.5, "calories": 300, "satiety": 0.35},
        },
    )
    assert hybrid["resolvable"] and hybrid["runtime_executable"] and hybrid["novel_created"]
    assert hybrid["usable_effect_coverage"] == 1
    assert hybrid["authoritative_effect_coverage"] == 0
    assert hybrid["model_estimated_field_rate"] == 1


def test_llm_only_missing_or_implausible_attributes_are_not_executable() -> None:
    catalog = build_synthetic_catalog()
    scenario = build_scenarios()[0]
    evaluator = ObjectChoiceEvaluator(catalog)
    missing = evaluator.evaluate(
        scenario,
        ArchitectureArm.LLM_ONLY,
        {"object": "croissant", "attributes": {"price": 4.5, "calories": 300}},
    )
    assert not missing["runtime_executable"]
    assert missing["missing_attribute_fields"] == ["satiety"]
    invalid = evaluator.evaluate(
        scenario,
        ArchitectureArm.LLM_ONLY,
        {"object": "croissant", "attributes": {"price": 4.5, "calories": 300, "satiety": 4}},
    )
    assert not invalid["runtime_executable"]
    assert invalid["invalid_attribute_fields"] == ["satiety"]


def test_attribute_validator_is_bounded_and_domain_specific() -> None:
    valid, missing, invalid = validate_effect_attributes(
        ObjectDomain.ASSET,
        {"value": 10, "liquidity": 0.5, "currency": "USD"},
    )
    assert valid and not missing and not invalid
    valid, _, invalid = validate_effect_attributes(
        ObjectDomain.ASSET,
        {"value": 10, "liquidity": 0.5, "currency": "usd"},
    )
    assert not valid and invalid == ("currency",)


def test_prompt_never_exposes_master_catalog() -> None:
    catalog = build_synthetic_catalog()
    scenario = build_scenarios()[7]
    candidates = catalog.retrieve(scenario, k=10)
    _, free = build_choice_prompt(scenario, ArchitectureArm.LLM_ONLY)
    _, bounded = build_choice_prompt(scenario, ArchitectureArm.CATALOG_TOPK, candidates)
    assert "candidate ID" not in free
    assert len(candidates) == 10
    assert sum(item.canonical_id in bounded for item in candidates) == 10
    outside = next(item for item in catalog.objects if item.domain is scenario.domain and item not in candidates)
    assert outside.canonical_id not in bounded


def test_strict_choice_parser() -> None:
    assert parse_object_choice(
        '{"object":"game:strategy:0001","attributes":{}}'
    ) == {"object": "game:strategy:0001", "attributes": {}}
    for value in (
        '{"object":"x"}',
        '{"object":"x","attributes":{},"extra":1}',
        '{"object":3,"attributes":{}}',
        '{"object":"x","attributes":{"price":[]}}',
        "not-json",
    ):
        try:
            parse_object_choice(value)
        except ValueError:
            pass
        else:
            raise AssertionError(value)


def test_offline_probe_is_explicitly_not_model_behavior_and_has_180_rows() -> None:
    rows = build_offline_probe_rows(repetitions=2)
    assert len(rows) == 30 * 3 * 2 == 180
    assert {row["probe_kind"] for row in rows} == {"SYSTEM_CAPABILITY_PROBE_NOT_MODEL_BEHAVIOR"}
    summary = summarize_rows(rows)
    assert summary[ArchitectureArm.CATALOG_TOPK.value]["resolution_rate"] == 1
    assert summary[ArchitectureArm.CATALOG_TOPK.value]["exact_effect_coverage"] == 1
    assert summary[ArchitectureArm.HYBRID.value]["usable_effect_coverage"] == 1
    assert summary[ArchitectureArm.LLM_ONLY.value]["resolution_rate"] < 1


class _CandidateFake:
    async def complete(self, system_prompt: str, user_prompt: str) -> DecisionReply:
        for line in user_prompt.splitlines():
            if "|" in line and ":" in line:
                return DecisionReply(
                    json.dumps({"object": line.split("|", 1)[0], "attributes": {}}),
                    provider_request_count=0,
                )
        return DecisionReply(
            json.dumps(
                {
                    "object": "unregistered free object",
                    "attributes": {"price": 4, "calories": 300, "satiety": 0.4},
                }
            ),
            provider_request_count=0,
        )


def test_real_runner_can_be_gated_with_fake_client_without_network() -> None:
    config = PilotConfig(repetitions=1, top_k=5, max_scenarios=2)
    assert len(pilot_schedule(config)) == 2 * 3
    rows, _ = asyncio.run(run_real_pilot(_CandidateFake(), build_synthetic_catalog(), config))
    assert len(rows) == 6
    assert sum(row.get("provider_status") == "SUCCESS" for row in rows) == 6
    topk_rows = [row for row in rows if row["arm"] == ArchitectureArm.CATALOG_TOPK.value]
    assert all(row["executable"] for row in topk_rows)


class _HTTPFailureFake:
    def __init__(self) -> None:
        self.last_metadata = DecisionResponseMetadata(
            http_status=401,
            http_error_code="invalid_api_key",
            http_error_type="authentication",
            http_error_param=None,
            request_id="req-safe-1",
            sanitized_error_message="invalid credential [REDACTED]",
        )

    async def complete(self, system_prompt: str, user_prompt: str) -> DecisionReply:
        raise DecisionClientError("provider returned HTTP 401")


def test_failed_rows_keep_only_safe_http_metadata_and_summary_counts() -> None:
    fake = _HTTPFailureFake()
    rows, summary = asyncio.run(
        run_real_pilot(
            fake,
            build_synthetic_catalog(),
            PilotConfig(repetitions=1, top_k=5, max_scenarios=1, attempt_id="attempt_2"),
        )
    )
    assert len(rows) == 3
    assert all(row["provider_status"] == "HTTP_ERROR" for row in rows)
    assert all(row["http_status"] == 401 for row in rows)
    assert all(row["http_error_code"] == "invalid_api_key" for row in rows)
    assert all(row["http_error_type"] == "authentication" for row in rows)
    assert all(row["request_id"] == "req-safe-1" for row in rows)
    assert all("super-secret" not in str(row) for row in rows)
    assert all("raw_prompt" not in row and "raw_completion" not in row for row in rows)
    assert summary["http_error"] == 3
    assert summary["http_status_counts"] == {"401": 3}
    assert summary["http_error_code_counts"] == {"invalid_api_key": 3}
