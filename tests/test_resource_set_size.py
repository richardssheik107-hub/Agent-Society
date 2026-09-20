from __future__ import annotations

import asyncio
import hashlib
import json

from social_sim.decision.client import DecisionReply
from social_sim.resource_benchmark import (
    ALL_RESOURCE_FIELDS,
    R16_FIELDS,
    R32_FIELDS,
    R64_FIELDS,
    R8_FIELDS,
    ResourceLevel,
    ResourceTruth,
    build_offline_rows,
    build_resource_prompt,
    build_schedule,
    build_scenarios,
    context_without_resources,
    summarize_resource_rows,
)
from social_sim.resource_benchmark.real_pilot import run_real_pilot


def test_resource_levels_are_exactly_nested() -> None:
    assert len(R8_FIELDS) == 8
    assert len(R16_FIELDS) == 16
    assert len(R32_FIELDS) == 32
    assert len(R64_FIELDS) == 64
    assert len(ALL_RESOURCE_FIELDS) == 64
    assert tuple(R16_FIELDS[:8]) == R8_FIELDS
    assert tuple(R32_FIELDS[:16]) == R16_FIELDS
    assert tuple(R64_FIELDS[:32]) == R32_FIELDS


def test_projection_is_immutable_and_does_not_mutate_truth() -> None:
    truth = ResourceTruth({name: index / 100 for index, name in enumerate(ALL_RESOURCE_FIELDS)})
    before = dict(truth.values)
    projection = truth.project(ResourceLevel.R16)
    assert tuple(projection.values) == R16_FIELDS
    assert dict(truth.values) == before
    try:
        projection.values["hunger"] = 0.0  # type: ignore[index]
    except TypeError:
        pass
    else:
        raise AssertionError("projection must be immutable")


def test_resource_manifest_has_24_deterministic_states() -> None:
    first = build_scenarios()
    second = build_scenarios()
    assert first == second
    assert len(first) == 24
    assert len({scenario.scenario_id for scenario in first}) == 24


def test_truth_is_complete_for_every_scenario() -> None:
    for scenario in build_scenarios():
        assert set(scenario.truth.values) == set(ALL_RESOURCE_FIELDS)
        assert all(0.0 <= value <= 1.0 for value in scenario.truth.values.values())


def test_acceptable_actions_and_critical_resources_never_enter_prompt() -> None:
    scenario = build_scenarios()[0]
    prompt = build_resource_prompt(scenario, scenario.truth.project(ResourceLevel.R8))
    assert scenario.scenario_id not in prompt.context
    assert scenario.family not in prompt.context
    assert "acceptable_action_set" not in prompt.context
    assert "critical_resources" not in prompt.context
    assert context_without_resources(prompt.context).find("hunger") == -1


def test_hidden_higher_resources_do_not_leak_outside_r_block() -> None:
    scenario = next(item for item in build_scenarios() if item.scenario_id == "personal_care_3")
    prompt = build_resource_prompt(scenario, scenario.truth.project(ResourceLevel.R8))
    fixed = context_without_resources(prompt.context)
    assert "shower_due" not in fixed
    assert "kitchen_cleaning_need" not in fixed
    assert "shower_due" in json.dumps(dict(scenario.truth.values))


def test_non_resource_context_is_identical_across_levels() -> None:
    scenario = build_scenarios()[6]
    fixed = {
        context_without_resources(build_resource_prompt(scenario, scenario.truth.project(level)).context)
        for level in ResourceLevel
    }
    assert len(fixed) == 1


def test_schedule_has_192_unique_cells_and_counterbalanced_levels() -> None:
    scenarios = build_scenarios()
    schedule = build_schedule(scenarios, repetitions=2)
    assert len(schedule) == 192
    assert len({entry.case_id for entry in schedule}) == 192
    cells = {(entry.scenario_id, entry.repetition, entry.level) for entry in schedule}
    assert len(cells) == 192
    for scenario in scenarios:
        for repetition in (1, 2):
            levels = [entry.level for entry in schedule if entry.scenario_id == scenario.scenario_id and entry.repetition == repetition]
            assert set(levels) == set(ResourceLevel)


def test_offline_rows_are_network_free_and_deterministic() -> None:
    scenarios = build_scenarios()
    rows = build_offline_rows(scenarios, repetitions=2)
    assert len(rows) == 192
    assert all(row["provider_status"] == "SUCCESS" for row in rows)
    assert all(row["resource_projection_valid"] for row in rows)
    assert all("raw_prompt" not in row and "raw_completion" not in row for row in rows)
    assert summarize_resource_rows(rows)["scheduled"] == 192


def test_scorer_is_deterministic_for_rule_and_alignment() -> None:
    from social_sim.resource_benchmark.scorer import score_proposal

    scenario = next(item for item in build_scenarios() if item.scenario_id == "work_1")
    first = score_proposal(scenario, "WORK", None)
    second = score_proposal(scenario, "WORK", None)
    assert first == second
    assert first["resource_alignment"] == 1
    assert first["rule_executable"] == 1


class _FakeResourceClient:
    def __init__(self) -> None:
        self.provider_request_count = 0

    async def complete(self, system_prompt: str, user_prompt: str) -> DecisionReply:
        self.provider_request_count += 1
        return DecisionReply('{"action":"WAIT","target":null}', 10, 4, 0, "offline-fake", 1)


def test_real_pilot_fake_client_writes_one_safe_row_per_cell(tmp_path) -> None:
    scenarios = build_scenarios()[:1]
    schedule = build_schedule(scenarios, repetitions=1)
    rows, summary = asyncio.run(run_real_pilot(
        _FakeResourceClient(), scenarios, schedule, progress_path=tmp_path / "progress.jsonl"
    ))
    assert len(rows) == 4
    assert summary["scheduled"] == 4
    assert summary["success"] == 4
    assert len((tmp_path / "progress.jsonl").read_text().splitlines()) == 4
    assert all("raw_prompt" not in row and "raw_completion" not in row for row in rows)


def test_truth_hash_is_stable_for_artifact_audit() -> None:
    scenario = build_scenarios()[0]
    payload = json.dumps(dict(scenario.truth.values), sort_keys=True, separators=(",", ":"))
    assert hashlib.sha256(payload.encode()).hexdigest() == hashlib.sha256(payload.encode()).hexdigest()
