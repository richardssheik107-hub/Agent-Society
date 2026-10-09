"""M1.5 offline frozen-prompt audit; no provider/client or source-world access.

The old fixture module imports Q6.1's decision runner and therefore the real API
client. This module intentionally does not import it. Recipe *orchestration* is
replayed only in disposable :memory: worlds using the unchanged catalog, domain
commands, projection and prompt builder. No feasibility rule is reimplemented.
Exact frozen hashes and byte counts attest that this boundary preserves inputs.
Only whitelisted summaries escape; prompt text exists briefly in memory only.
"""
from __future__ import annotations

import hashlib
import json
import random
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from .action_projection import FEASIBLE, RAW, canonical_options, project_actions, projected_prompt
from .benchmark import seed_demo
from .context import decision_prompt, observe
from .engine import ContinuityWorld
from .models import TIMED_ACTIVITIES, ObjectDefinition, digest
from .validation import validate_world

FROZEN_PROTOCOL_HASH = "b66217fa18ce8740deec38334b157ff35f00455d8d2b431dd0b48531debffcc6"
SCENARIO_IDS = tuple(f"s{index:02d}" for index in range(1, 13))
FAMILIES = (
    "OWNERSHIP", "POST_MEAL_NEED", "MEDIA_PROGRESS", "ACTIVITY_LOCATION",
    "MEAL_PAYMENT", "MEAL_SUPPLY",
)
ACTIVITIES = tuple(sorted((*TIMED_ACTIVITIES, "MEAL", "WATCH", "PLAY", "TRAVEL")))
EXTRA_INSTRUCTION = (
    " Choose one activity/target pair from executable_options. "
    "These are rule-feasible options, not a preference ranking."
)
ALLOCATION_FIELDS = (
    "cell_id", "pair_id", "scenario_id", "family", "repeat", "condition", "order",
    "pair_order", "within_pair_order",
)
CONFOUNDERS = (
    "EXECUTABLE_CANDIDATE_INFORMATION", "EXPLICIT_PAIR_SELECTION_INSTRUCTION",
    "ADDITIONAL_CONTEXT_LENGTH", "LEXICOGRAPHIC_CANDIDATE_ORDER",
    "REPEATED_ACTIVITY_NAME_EXPOSURE", "HIGH_LEVEL_MEAL_MACRO_GRANULARITY",
)


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _common_prefix(left: str, right: str) -> int:
    for index, (a, b) in enumerate(zip(left, right, strict=False)):
        if a != b:
            return index
    return min(len(left), len(right))


def summarize_prompt_pair(system_a: str, user_a: str,
                          system_b: str, user_b: str) -> dict[str, Any]:
    """Summarize exact A/B differences without exposing arbitrary prompt text.

    The expected structural contract is strict. Arbitrary JSON keys and option
    names cannot be smuggled into the exported summary. Targets stay private.
    """
    if not all(isinstance(value, str) for value in (system_a, user_a, system_b, user_b)):
        raise ValueError("PROMPT_TEXT_TYPE_MISMATCH")
    a, b = json.loads(user_a), json.loads(user_b)
    if (not isinstance(a, dict) or not isinstance(b, dict)
            or set(a) != {"destinations", "observation"}
            or set(b) != {"destinations", "observation", "executable_options"}):
        raise ValueError("FROZEN_USER_STRUCTURE_MISMATCH")
    if a != {key: b[key] for key in a}:
        raise ValueError("FROZEN_OBSERVATION_CHANGED")
    if system_b != system_a + EXTRA_INSTRUCTION:
        raise ValueError("FROZEN_SYSTEM_APPEND_MISMATCH")
    options = b["executable_options"]
    if (not isinstance(options, list) or not options
            or any(not isinstance(option, dict) or set(option) != {"activity", "target"}
                   or option["activity"] not in ACTIVITIES for option in options)):
        raise ValueError("FROZEN_CANDIDATE_STRUCTURE_MISMATCH")
    canonical = canonical_options(options)
    if options != canonical or len({digest(option) for option in options}) != len(options):
        raise ValueError("FROZEN_CANDIDATE_ORDER_MISMATCH")
    counts = Counter(option["activity"] for option in options)
    positions = {
        activity: [index + 1 for index, option in enumerate(options)
                   if option["activity"] == activity]
        for activity in ACTIVITIES
    }
    meal, travel = positions["MEAL"], positions["TRAVEL"]
    prompts = {RAW: (system_a, user_a), FEASIBLE: (system_b, user_b)}
    return {
        "system_difference": "EXACT_PREFIX_WITH_FROZEN_SELECTION_INSTRUCTION_APPEND",
        "system_equal": system_a == system_b,
        "system_a_exact_prefix_of_b": system_b.startswith(system_a),
        "extra_selection_instruction": "CHOOSE_ONE_PAIR_FROM_EXECUTABLE_OPTIONS",
        "not_preference_ranking_disclaimer": True,
        "system_added_chars": len(system_b) - len(system_a),
        "system_common_prefix_chars": _common_prefix(system_a, system_b),
        "system_hashes": {mode: _text_hash(pair[0]) for mode, pair in prompts.items()},
        "user_difference": "ONE_ADDED_EXECUTABLE_OPTIONS_KEY_SHARED_FACTS_EQUAL",
        "user_keys_a": ["destinations", "observation"],
        "user_keys_b": ["destinations", "executable_options", "observation"],
        "shared_observation_equal": True, "shared_destinations_equal": True,
        "user_equal": user_a == user_b,
        "user_a_exact_prefix_of_b": user_b.startswith(user_a),
        "user_common_prefix_chars": _common_prefix(user_a, user_b),
        "user_added_chars": len(user_b) - len(user_a),
        "user_hashes": {mode: _text_hash(pair[1]) for mode, pair in prompts.items()},
        "prompt_hashes": {mode: digest({"system": pair[0], "user": pair[1]})
                          for mode, pair in prompts.items()},
        "prompt_chars": {mode: sum(map(len, pair)) for mode, pair in prompts.items()},
        "prompt_bytes": {mode: sum(len(text.encode("utf-8")) for text in pair)
                         for mode, pair in prompts.items()},
        "candidate_count": len(options), "candidate_hash": digest(options),
        "candidate_activity_counts": {activity: counts[activity] for activity in ACTIVITIES},
        "candidate_activity_positions_one_based": positions,
        "candidate_order": "LEXICOGRAPHIC_ACTIVITY_THEN_TARGET_NONE_AS_EMPTY",
        "preference_ranking": False,
        "meal_before_all_travel": bool(meal and travel and max(meal) < min(travel)),
        "meal_and_travel_both_exposed": bool(meal and travel),
        "meal_macro_steps_in_b_candidates": "NOT_EXPLICITLY_EXPANDED",
        "meal_macro_execution_semantics": "EXISTING_TRAVEL_BUY_EAT_AS_NEEDED",
    }


def _require_accepted(result: Mapping[str, Any]) -> None:
    if not result.get("accepted") or result.get("replayed"):
        raise ValueError("OFFLINE_FIXTURE_COMMAND_REJECTED")


def _finish(world: ContinuityWorld, request: str, limit: int) -> None:
    count = 0
    while commitment := world.store.commitment(1):
        if (commitment["status"] != "ACTIVE" or commitment["remaining_min"] <= 0
                or count >= limit):
            raise ValueError("OFFLINE_FIXTURE_COMMITMENT_INVALID")
        until = world.minute + min(15, commitment["remaining_min"])
        _require_accepted(world.advance(f"{request}:t{until}", until))
        count += 1
    if world.store.get_commitment(request)["status"] != "COMPLETED":
        raise ValueError("OFFLINE_FIXTURE_NOT_COMPLETED")


def _build_isolated(world: ContinuityWorld, recipe: Mapping[str, Any], limit: int) -> None:
    # This is genesis/recipe plumbing, never a new state or feasibility rule.
    with ContinuityWorld(":memory:") as template:
        seed_demo(template)
        state = template.store.snapshot()
    actor = {**state["actors"][0], **recipe["actor"]}
    objects = []
    for value in state["objects"]:
        definition = ObjectDefinition.from_dict({
            key: field for key, field in value.items() if key not in {"stock", "available"}
        })
        objects.append((definition, recipe["stock"].get(definition.object_id, value["stock"])))
    world.seed([actor], objects)
    for index, step in enumerate(recipe["steps"], start=1):
        request = f"fixture:{index:02d}"
        if step["op"] == "BUY":
            _require_accepted(world.act(request, 1, "BUY", step["target"]))
        elif step["op"] == "ACTIVITY":
            _require_accepted(world.start(request, 1, step["activity"], step["target"]))
            _finish(world, request, limit)
        elif step["op"] == "PARTIAL_WATCH":
            _require_accepted(world.start(request, 1, "WATCH", step["target"]))
            _require_accepted(world.advance(request + ":partial", world.minute + step["minutes"]))
            _require_accepted(world.control(request + ":pause", 1, "PAUSE"))
            _require_accepted(world.control(request + ":cancel", 1, "CANCEL"))
        elif step["op"] == "WATCH_ALL":
            for episode in range(1, world.store.object(step["target"])["episodes"] + 1):
                watch_id = f"{request}:watch{episode:03d}"
                _require_accepted(world.start(watch_id, 1, "WATCH", step["target"]))
                _finish(world, watch_id, limit)
        else:
            raise ValueError("OFFLINE_FIXTURE_OPERATION_UNKNOWN")
    validate_world(world)
    if world.store.commitment(1) is not None:
        raise ValueError("OFFLINE_FIXTURE_BLOCKING_COMMITMENT")


def _rebuild_scenario(specification: Mapping[str, Any], protocol: Mapping[str, Any]) -> dict:
    with ContinuityWorld(":memory:") as world:
        _build_isolated(world, specification["recipe"], protocol["max_activity_micro_steps"])
        before = digest(world.store.snapshot())
        prompts = [projected_prompt(world, mode=mode, max_chars=protocol["max_prompt_chars"])
                   for mode in (RAW, FEASIBLE)]
        if prompts[0] != decision_prompt(world, 1):
            raise ValueError("ORIGINAL_RAW_PROMPT_CHANGED")
        projection = project_actions(world)
        observation = observe(world, 1)
        observation_hash = digest(observation)
        resources = [{key: item[key] for key in
                      ("id", "qty", "price_cents", "available", "in_stock", "minutes")}
                     for item in observation["objects"]]
        summary = summarize_prompt_pair(*prompts[0], *prompts[1])
        if before != digest(world.store.snapshot()):
            raise ValueError("OFFLINE_PROMPT_BUILD_MUTATED_FIXTURE")
    if (summary["candidate_hash"] != projection["candidate_digest"]
            or summary["candidate_count"] != projection["candidate_count"]):
        raise ValueError("OFFLINE_PROJECTION_PROMPT_MISMATCH")
    return {"scenario_id": specification["scenario_id"], "family": specification["family"],
            "state_hash": before, "observation_hash": observation_hash,
            "initial_resource_facts": resources, **summary}


def _expected_allocations(protocol: Mapping[str, Any]) -> list[dict[str, Any]]:
    groups = [(specification, repeat) for specification in protocol["scenarios"]
              for repeat in (1, 2)]
    random.Random(protocol["seed"]).shuffle(groups)
    cells = []
    for pair_order, (scenario, repeat) in enumerate(groups, start=1):
        modes = (RAW, FEASIBLE) if repeat == 1 else (FEASIBLE, RAW)
        for within, condition in enumerate(modes, start=1):
            order = len(cells) + 1
            cells.append({"cell_id": f"c{order:03d}", "pair_id": f"p{pair_order:03d}",
                          "scenario_id": scenario["scenario_id"], "family": scenario["family"],
                          "repeat": repeat, "condition": condition, "order": order,
                          "pair_order": pair_order, "within_pair_order": within})
    return cells


def audit_prompt_intervention(protocol: Mapping[str, Any],
                              frozen_scenarios: Sequence[Mapping[str, Any]],
                              allocated_cells: Sequence[Mapping[str, Any]],
                              sanitized_cells: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Attest frozen inputs and produce 12-scenario/48-cell safe summaries.

    Inputs are already read/whitelisted by the caller. This function reads no
    paths, credentials, raw provider output, or source database. A mismatch is a
    hard error, not a guessed reconstruction. Token observations remain nullable.
    """
    if digest(protocol) != FROZEN_PROTOCOL_HASH:
        raise ValueError("OUTCOME_FROZEN_PROTOCOL_HASH_MISMATCH")
    if len(frozen_scenarios) != 12 or len(allocated_cells) != 48 or len(sanitized_cells) != 48:
        raise ValueError("OUTCOME_PROMPT_PANEL_DIMENSION_MISMATCH")
    frozen = {row["scenario_id"]: row for row in frozen_scenarios}
    observed = {row["cell_id"]: row for row in sanitized_cells}
    if set(frozen) != set(SCENARIO_IDS) or len(observed) != 48:
        raise ValueError("OUTCOME_PROMPT_IDENTITIES_MISMATCH")
    expected = _expected_allocations(protocol)
    allocations = [{key: row.get(key) for key in ALLOCATION_FIELDS} for row in allocated_cells]
    if allocations != expected:
        raise ValueError("OUTCOME_FROZEN_ALLOCATION_MISMATCH")
    scenarios = []
    for specification in protocol["scenarios"]:
        rebuilt = _rebuild_scenario(specification, protocol)
        reference = frozen[specification["scenario_id"]]
        for key in ("family", "state_hash", "observation_hash", "candidate_hash",
                    "candidate_count", "prompt_hashes", "prompt_chars", "prompt_bytes"):
            if rebuilt[key] != reference.get(key):
                raise ValueError("OUTCOME_FROZEN_SCENARIO_PROMPT_MISMATCH")
        scenarios.append({**rebuilt, "frozen_manifest_attestation": "PASS"})
    by_scenario = {row["scenario_id"]: row for row in scenarios}
    cells = []
    actions = {mode: Counter() for mode in (RAW, FEASIBLE)}
    tokens = {mode: [] for mode in (RAW, FEASIBLE)}
    for allocation in expected:
        row = observed.get(allocation["cell_id"])
        if row is None or any(row.get(key) != value for key, value in allocation.items()):
            raise ValueError("OUTCOME_CELL_ALLOCATION_MISMATCH")
        scenario, mode = by_scenario[allocation["scenario_id"]], allocation["condition"]
        if (row.get("prompt_hash") != scenario["prompt_hashes"][mode]
                or row.get("prompt_chars") != scenario["prompt_chars"][mode]
                or row.get("candidate_count") != scenario["candidate_count"]
                or row.get("candidate_hash") != scenario["candidate_hash"]):
            raise ValueError("OUTCOME_CELL_FROZEN_PROMPT_MISMATCH")
        token = row.get("input_tokens")
        if token is not None and (type(token) is not int or token < 0):
            raise ValueError("OUTCOME_INPUT_TOKEN_TYPE_MISMATCH")
        tokens[mode].append(token)
        activity = row.get("proposal_activity")
        if activity is not None:
            if activity not in ACTIVITIES:
                raise ValueError("OUTCOME_ACTIVITY_NOT_WHITELISTED")
            actions[mode][activity] += 1
        cells.append({**allocation, "prompt_hash": scenario["prompt_hashes"][mode],
                      "prompt_chars": scenario["prompt_chars"][mode],
                      "prompt_bytes": scenario["prompt_bytes"][mode],
                      "candidate_count": scenario["candidate_count"],
                      "candidate_activity_counts": scenario["candidate_activity_counts"],
                      "frozen_cell_attestation": "PASS", "input_tokens": token})
    exposure = Counter()
    for row in scenarios:
        exposure.update(row["candidate_activity_counts"])
    both = [row for row in scenarios if row["meal_and_travel_both_exposed"]]
    return {
        "schema": "Q62_OUTCOME_PROMPT_INTERVENTION_AUDIT_V1",
        "evaluation_type": "EXPLORATORY_POST_HOC", "audit_status": "PASS",
        "protocol_canonical_hash": FROZEN_PROTOCOL_HASH,
        "source_frozen_prompt_attestation": "PASS", "scenario_count": 12, "cell_count": 48,
        "scenarios": scenarios, "cells": cells,
        "candidate_exposure_unique_scenarios": dict(exposure),
        "candidate_exposure_b_allocations": {key: value * 2 for key, value in exposure.items()},
        "meal_before_travel_scenarios": sum(row["meal_before_all_travel"] for row in both),
        "meal_travel_comparable_scenarios": len(both),
        "input_token_observations": {
            mode: {"known_subtotal": sum(value for value in values if value is not None),
                   "known": sum(value is not None for value in values),
                   "missing": sum(value is None for value in values), "eligible": len(values)}
            for mode, values in tokens.items()
        },
        "observed_activity_distribution": {mode: dict(counts) for mode, counts in actions.items()},
        "potential_confounds": list(CONFOUNDERS), "causal_mechanism_isolated": False,
        "hidden_model_reasoning_observed": False, "new_real_provider_requests": 0,
        "original_prompts_modified": False, "full_prompt_or_completion_exported": False,
    }
