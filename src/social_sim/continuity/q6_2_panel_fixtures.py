"""Q6.2 isolated, reproducible fixed-state fixtures and paired allocation.

Recipes affect only a newly created world. Existing seed/catalog definitions and
deterministic domain commands generate every state; there are no production SQL
rewrites, custom feasibility rules, or model calls. Scenario labels stay in the
audit manifest and never become actor/resource/prompt fields.
"""
from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

from .action_projection import FEASIBLE, RAW, project_actions, projected_prompt
from .benchmark import seed_demo
from .context import decision_prompt, observe
from .engine import ContinuityWorld
from .models import ObjectDefinition, canonical_json, digest, integer
from .q6_1 import project_state
from .validation import validate_world

PROTOCOL_SCHEMA = "Q62_FIXED_STATE_PANEL_PROTOCOL_V1"
PROTOCOL_VERSION = "q62_fixed_state_panel_v1"
FIXTURE_SCHEMA = "Q62_FIXED_STATE_FIXTURES_V1"
SCENARIO_IDS = tuple(f"s{index:02d}" for index in range(1, 13))
FAMILIES = (
    "OWNERSHIP", "POST_MEAL_NEED", "MEDIA_PROGRESS", "ACTIVITY_LOCATION",
    "MEAL_PAYMENT", "MEAL_SUPPLY",
)
CONDITIONS = (RAW, FEASIBLE)
KNOWN_COMMITMENT_FAILURES = (
    "OUT_OF_STOCK", "INSUFFICIENT_FUNDS", "OBJECT_UNAVAILABLE", "ITEM_NOT_OWNED",
)
STOP_MAPPING = {
    "DECISION_ACCEPTED": "RECORD_AND_CONTINUE_NEXT_CELL",
    "RULE_REJECTED": "RECORD_AND_CONTINUE_NEXT_CELL",
    "COMMITMENT_FAILED": "CONTINUE_ONLY_KNOWN_REASON_AND_VALID_INVARIANTS_AND_LEDGER",
    **dict.fromkeys((
        "UNKNOWN_EXECUTION_FAILURE", "PROVIDER_TIMEOUT", "HTTP_ERROR", "TRANSPORT_ERROR",
        "PROVIDER_CONTRACT_ERROR", "INVALID_MODEL_OUTPUT", "OUTSIDE_CATALOG",
        "REQUEST_CANCELLED", "ARCHITECTURE_ERROR", "STATE_INVARIANT_FAILED",
        "EVIDENCE_INCOMPLETE", "REQUEST_BUDGET_EXHAUSTED", "EXECUTION_LIMIT_EXCEEDED",
        "ALREADY_RECORDED", "ALREADY_ATTEMPTED", "COMMITMENT_PRESENT",
    ), "STOP_SESSION"),
}
PROTOCOL_RELATIVE_PATH = Path("config/experimental/q6_2_fixed_state_panel_v1.json")


def load_protocol(root: str | Path | None = None) -> dict[str, Any]:
    """Load the checked-in, secret-free protocol; no environment/config lookup."""
    repository = Path(root) if root is not None else Path(__file__).resolve().parents[3]
    with (repository / PROTOCOL_RELATIVE_PATH).open(encoding="utf-8") as stream:
        protocol = json.load(stream)
    validate_protocol(protocol)
    return protocol


def validate_protocol(protocol: dict[str, Any]) -> None:
    """Reject changed panel dimensions/contracts rather than silently truncate."""
    if not isinstance(protocol, dict):
        raise ValueError("INVALID_PANEL_PROTOCOL")
    if (protocol.get("schema") != PROTOCOL_SCHEMA
            or protocol.get("protocol_version") != PROTOCOL_VERSION):
        raise ValueError("UNSUPPORTED_PANEL_PROTOCOL")
    integer(protocol.get("seed"), "seed", high=2**63 - 1)
    expected = {"repeats": 2, "planned_scenarios": 12, "planned_cells": 48,
                "planned_pairs": 24, "transport_retries": 0}
    for field, value in expected.items():
        if type(protocol.get(field)) is not int or protocol.get(field) != value:
            raise ValueError("INVALID_PANEL_DIMENSIONS")
    if protocol.get("conditions") != list(CONDITIONS):
        raise ValueError("INVALID_PANEL_CONDITIONS")
    budgets = protocol.get("budgets")
    if (not isinstance(budgets, dict) or budgets != {"per_cell": 1, "session": 48}
            or any(type(value) is not int for value in budgets.values())):
        raise ValueError("INVALID_PANEL_BUDGET")
    for key in ("json_repair", "fallback_action", "thinking_disabled_explicitly"):
        if protocol.get(key) is not False:
            raise ValueError("CHANGED_PANEL_REQUEST_CONTRACT")
    if (protocol.get("minimal_request") is not True
            or protocol.get("provider_contract") != "Q6_1_MINIMAL_CHAT_COMPLETIONS"):
        raise ValueError("CHANGED_PANEL_REQUEST_CONTRACT")
    if protocol.get("schedule") != "SHUFFLED_ADJACENT_PAIRS_REVERSED_REPEAT":
        raise ValueError("INVALID_PANEL_SCHEDULE")
    integer(protocol.get("max_activity_micro_steps"), "max_activity_micro_steps", 24, 1000)
    integer(protocol.get("max_prompt_chars"), "max_prompt_chars", 1, 100_000)
    timeout = protocol.get("timeout_seconds")
    if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
            or not 0 < timeout <= 60):
        raise ValueError("INVALID_PANEL_TIMEOUT")
    if protocol.get("known_commitment_failures") != list(KNOWN_COMMITMENT_FAILURES):
        raise ValueError("CHANGED_PANEL_COMMITMENT_FAILURES")
    if protocol.get("stop_mapping") != STOP_MAPPING:
        raise ValueError("CHANGED_PANEL_STOP_MAPPING")
    scenarios = protocol.get("scenarios")
    if (not isinstance(scenarios, list) or len(scenarios) != 12
            or not all(isinstance(scenario, dict) for scenario in scenarios)):
        raise ValueError("INVALID_PANEL_SCENARIOS")
    if tuple(scenario.get("scenario_id") for scenario in scenarios) != SCENARIO_IDS:
        raise ValueError("INVALID_PANEL_SCENARIO_IDS")
    if tuple(scenario.get("family") for scenario in scenarios) != tuple(
            family for family in FAMILIES for _ in range(2)):
        raise ValueError("INVALID_PANEL_FAMILIES")
    for scenario in scenarios:
        _validate_recipe(scenario.get("recipe"))


def _validate_recipe(recipe: object) -> None:
    if not isinstance(recipe, dict) or set(recipe) != {"actor", "stock", "steps"}:
        raise ValueError("INVALID_PANEL_RECIPE")
    actor, stock, steps = recipe["actor"], recipe["stock"], recipe["steps"]
    if not isinstance(actor, dict) or set(actor) - {"money_cents", "hunger_milli"}:
        raise ValueError("INVALID_PANEL_GENESIS_ACTOR")
    if "money_cents" in actor:
        integer(actor["money_cents"], "money_cents")
    if "hunger_milli" in actor:
        integer(actor["hunger_milli"], "hunger_milli", high=1000)
    if not isinstance(stock, dict) or set(stock) - {"food_meal"}:
        raise ValueError("INVALID_PANEL_GENESIS_STOCK")
    for value in stock.values():
        integer(value, "stock")
    if not isinstance(steps, list):
        raise ValueError("INVALID_PANEL_RECIPE_STEPS")
    for step in steps:
        if not isinstance(step, dict):
            raise ValueError("INVALID_PANEL_RECIPE_STEP")
        op = step.get("op")
        if op == "BUY":
            if set(step) != {"op", "target"} or step["target"] != "game_a":
                raise ValueError("INVALID_PANEL_RECIPE_BUY")
        elif op == "ACTIVITY":
            if set(step) != {"op", "activity", "target"} or (
                step["activity"], step["target"]
            ) not in {("TRAVEL", "restaurant"), ("TRAVEL", "office"),
                      ("MEAL", "food_meal")}:
                raise ValueError("INVALID_PANEL_RECIPE_ACTIVITY")
        elif op == "PARTIAL_WATCH":
            if (set(step) != {"op", "target", "minutes"}
                    or step["target"] != "series_a"):
                raise ValueError("INVALID_PANEL_RECIPE_PARTIAL")
            integer(step["minutes"], "partial_minutes", 1, 29)
        elif op == "WATCH_ALL":
            if set(step) != {"op", "target"} or step["target"] != "series_a":
                raise ValueError("INVALID_PANEL_RECIPE_WATCH_ALL")
        else:
            raise ValueError("INVALID_PANEL_RECIPE_OPERATION")


def _accepted(result: dict) -> None:
    if not result.get("accepted") or result.get("replayed"):
        raise RuntimeError("FIXTURE_COMMAND_NOT_ACCEPTED")


def _finish(world: ContinuityWorld, request_id: str, *, limit: int) -> None:
    count = 0
    while commitment := world.store.commitment(1):
        if commitment["status"] != "ACTIVE" or commitment["remaining_min"] <= 0:
            raise RuntimeError("FIXTURE_BLOCKING_COMMITMENT")
        if count >= limit:
            raise RuntimeError("FIXTURE_ADVANCE_LIMIT")
        until = world.minute + min(15, commitment["remaining_min"])
        _accepted(world.advance(f"{request_id}:t{until}", until))
        count += 1
    if world.store.get_commitment(request_id)["status"] != "COMPLETED":
        raise RuntimeError("FIXTURE_COMMITMENT_NOT_COMPLETED")


def _seed_isolated(world: ContinuityWorld, recipe: dict) -> None:
    """Reuse the existing catalog through seed_demo, then seed a fresh genesis.

    The genesis overrides are explicit in the checked-in recipe and validated by
    world.seed. They are not edits to an existing world or invented ownership /
    media links. Stock and cash therefore have a truthful WORLD_CREATED ledger.
    """
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


def build_world(path: str | Path, scenario_id: str,
                protocol: dict[str, Any] | None = None) -> ContinuityWorld:
    """Create one isolated legal snapshot; caller owns/ closes the returned world.

    Existing paths are rejected, never reset. A failed construction is preserved
    on disk and closed; the caller must pick a new destination for another run.
    """
    protocol = load_protocol() if protocol is None else protocol
    validate_protocol(protocol)
    if scenario_id not in SCENARIO_IDS:
        raise ValueError("UNKNOWN_PANEL_SCENARIO")
    if str(path) != ":memory:" and Path(path).exists():
        raise FileExistsError(path)
    scenario = next(value for value in protocol["scenarios"]
                    if value["scenario_id"] == scenario_id)
    recipe = scenario["recipe"]
    world = ContinuityWorld(path)
    try:
        _seed_isolated(world, recipe)
        for index, step in enumerate(recipe["steps"], start=1):
            request = f"fixture:{index:02d}"
            if step["op"] == "BUY":
                _accepted(world.act(request, 1, "BUY", step["target"]))
            elif step["op"] == "ACTIVITY":
                _accepted(world.start(request, 1, step["activity"], step["target"]))
                _finish(world, request, limit=protocol["max_activity_micro_steps"])
            elif step["op"] == "PARTIAL_WATCH":
                _accepted(world.start(request, 1, "WATCH", step["target"]))
                _accepted(world.advance(request + ":partial", world.minute + step["minutes"]))
                _accepted(world.control(request + ":pause", 1, "PAUSE"))
                _accepted(world.control(request + ":cancel", 1, "CANCEL"))
            else:  # WATCH_ALL is the only other validated operation.
                episodes = world.store.object(step["target"])["episodes"]
                for episode in range(1, episodes + 1):
                    watch_id = f"{request}:watch{episode:03d}"
                    _accepted(world.start(watch_id, 1, "WATCH", step["target"]))
                    _finish(world, watch_id, limit=protocol["max_activity_micro_steps"])
        validate_world(world)
        if world.store.commitment(1) is not None:
            raise RuntimeError("FIXTURE_BLOCKING_COMMITMENT")
        if not project_actions(world)["executable_options"]:
            raise ValueError("NO_EXECUTABLE_OPTIONS")
        for mode in CONDITIONS:
            projected_prompt(world, mode=mode, max_chars=protocol["max_prompt_chars"])
        return world
    except BaseException:
        world.close()
        raise


def world_fingerprint(world: ContinuityWorld, protocol: dict[str, Any]) -> dict[str, Any]:
    """Safe audit fields of the exact initial snapshot, without prompt text."""
    validate_world(world)
    with world.store.read_snapshot():
        state = world.store.snapshot()
        observation = observe(world, 1)
        projection = project_actions(world)
        if not projection["executable_options"]:
            raise ValueError("NO_EXECUTABLE_OPTIONS")
        prompt_hashes, prompt_chars, prompt_bytes = {}, {}, {}
        for mode in CONDITIONS:
            system, user = projected_prompt(
                world, mode=mode, max_chars=protocol["max_prompt_chars"])
            if mode == RAW and (system, user) != decision_prompt(world, 1):
                raise RuntimeError("RAW_PROMPT_CHANGED")
            prompt_hashes[mode] = digest({"system": system, "user": user})
            prompt_chars[mode] = len(system) + len(user)
            prompt_bytes[mode] = len(system.encode("utf-8")) + len(user.encode("utf-8"))
        return {
            "state_hash": digest(state),
            "initial_projected_state": project_state(world),
            "observation_hash": digest(observation),
            "observation_chars": len(canonical_json(observation)),
            "object_candidates": observation["objects"],
            "candidate_hash": projection["candidate_digest"],
            "candidate_count": projection["candidate_count"],
            "executable_options": projection["executable_options"],
            "prompt_hashes": prompt_hashes,
            "prompt_chars": prompt_chars,
            "prompt_bytes": prompt_bytes,
            "state_minute": world.minute,
            "state_version": observation["actor"]["version"],
            "fixture_event_count": len(world.store.events()),
            "invariants": "PASS",
        }


def freeze_scenarios(protocol: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Resolve the twelve recipes and freeze canonical semantic hashes in memory."""
    protocol = load_protocol() if protocol is None else protocol
    validate_protocol(protocol)
    scenarios = []
    for specification in protocol["scenarios"]:
        with build_world(":memory:", specification["scenario_id"], protocol) as world:
            row = world_fingerprint(world, protocol)
        # Deep copy prevents subsequent manifest manipulation changing the recipe.
        metadata = json.loads(canonical_json(specification))
        scenarios.append({"schema": FIXTURE_SCHEMA, **metadata, **row})
    if len({row["state_hash"] for row in scenarios}) != 12:
        raise ValueError("PANEL_SCENARIOS_NOT_DISTINCT")
    return scenarios


def allocate_cells(protocol: dict[str, Any], scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministically shuffle 24 adjacent pairs; repeat 1=AB, repeat 2=BA."""
    validate_protocol(protocol)
    if (len(scenarios) != 12
            or tuple(row["scenario_id"] for row in scenarios) != SCENARIO_IDS):
        raise ValueError("INVALID_FROZEN_PANEL_SCENARIOS")
    groups = [(scenario, repeat) for scenario in scenarios for repeat in (1, 2)]
    random.Random(protocol["seed"]).shuffle(groups)
    cells = []
    for pair_order, (scenario, repeat) in enumerate(groups, start=1):
        modes = CONDITIONS if repeat == 1 else tuple(reversed(CONDITIONS))
        pair_id = f"p{pair_order:03d}"
        for within_pair_order, mode in enumerate(modes, start=1):
            order = len(cells) + 1
            cells.append({
                "cell_id": f"c{order:03d}", "pair_id": pair_id,
                "scenario_id": scenario["scenario_id"], "family": scenario["family"],
                "repeat": repeat, "condition": mode, "order": order,
                "pair_order": pair_order, "within_pair_order": within_pair_order,
            })
    if (len(cells) != 48 or len({cell["pair_id"] for cell in cells}) != 24
            or Counter(cell["condition"] for cell in cells) != {RAW: 24, FEASIBLE: 24}):
        raise AssertionError("INVALID_PANEL_ALLOCATION")
    return cells
