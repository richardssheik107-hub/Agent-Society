"""Q4 scheduling, deterministic parsing, and capability-probe helpers."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

from social_sim.decision.models import ActionType, DecisionProposal
from social_sim.decision.parser import DecisionParseResult, deterministic_recover

from .context import build_resource_prompt, context_without_resources
from .models import ResourceLevel, ResourceScenario, ScheduleEntry
from .scorer import LEVELS, score_proposal, summarize_resource_rows


def build_schedule(
    scenarios: Iterable[ResourceScenario],
    *,
    repetitions: int = 2,
) -> tuple[ScheduleEntry, ...]:
    scenario_list = tuple(scenarios)
    if not scenario_list or repetitions <= 0:
        raise ValueError("schedule needs scenarios and positive repetitions")
    entries: list[ScheduleEntry] = []
    for repetition in range(1, repetitions + 1):
        for index, scenario in enumerate(scenario_list):
            offset = (index + repetition - 1) % len(LEVELS)
            order = LEVELS[offset:] + LEVELS[:offset]
            if repetition % 2 == 0:
                order = tuple(reversed(order))
            for level in order:
                entries.append(ScheduleEntry(
                    case_id=f"Q4-{len(entries) + 1:04d}",
                    scenario_id=scenario.scenario_id,
                    repetition=repetition,
                    level=level,
                ))
    return tuple(entries)


def parse_resource_proposal(
    raw_text: str,
    scenario: ResourceScenario,
) -> tuple[DecisionProposal | None, DecisionParseResult]:
    parsed = deterministic_recover(
        raw_text,
        available_actions=scenario.available_actions,
        available_targets=scenario.available_targets,
    )
    if not parsed.strict_valid or parsed.proposal is None:
        return None, parsed
    return parsed.proposal, parsed


def deterministic_choice(scenario: ResourceScenario, level: ResourceLevel) -> DecisionProposal:
    """A no-network choice source for pipeline validation, not behavior evidence."""
    action = scenario.acceptable_action_set[0]
    target = None
    if action is ActionType.MOVE:
        target = "office" if scenario.location == "home" else "home"
    elif action in (ActionType.BUY, ActionType.EAT):
        target = "meal"
    return DecisionProposal(action, target)


def build_offline_rows(scenarios: tuple[ResourceScenario, ...], *, repetitions: int = 2) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    by_id = {scenario.scenario_id: scenario for scenario in scenarios}
    for entry in build_schedule(scenarios, repetitions=repetitions):
        scenario = by_id[entry.scenario_id]
        projection = scenario.truth.project(entry.level)
        prompt = build_resource_prompt(scenario, projection)
        proposal = deterministic_choice(scenario, entry.level)
        row = {
            "case_id": entry.case_id,
            "scenario_id": scenario.scenario_id,
            "family": scenario.family,
            "repetition": entry.repetition,
            "level": entry.level.value,
            "provider_status": "SUCCESS",
            "strict_parse_valid": True,
            "resource_projection_valid": tuple(projection.values) == tuple(scenario.truth.values)[:len(projection.values)],
            "action": proposal.action.value,
            "target": proposal.target,
            "context_chars": len(prompt.context),
            "prompt_chars": prompt.prompt_chars,
            "input_tokens": None,
            "output_tokens": None,
            "reasoning_tokens": None,
            "latency_seconds": 0.0,
            "provider_model": "offline_fake",
            "fixed_context_hash": hashlib.sha256(context_without_resources(prompt.context).encode()).hexdigest(),
            **score_proposal(scenario, proposal.action, proposal.target),
        }
        rows.append(row)
    return rows


def capability_summary(rows: list[dict[str, object]]) -> dict[str, object]:
    return summarize_resource_rows(rows)
