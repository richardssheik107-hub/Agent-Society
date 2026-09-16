"""The compact context must stay deterministic, local, and bounded."""

import json

import pytest

from social_sim.context import ContextCompiler
from social_sim.world.observation import LocalObservation


@pytest.fixture
def observation() -> LocalObservation:
    return LocalObservation(
        agent_id=1,
        time="2026-01-01T00:00:00",
        location="home",
        money=100.0,
        hunger=0.8,
    )


def test_compile_is_deterministic(observation: LocalObservation) -> None:
    compiler = ContextCompiler()
    profile = {"name": "Alice", "goal": "rest"}
    assert compiler.compile(profile, observation) == compiler.compile(profile, observation)


def test_compact_context_contains_required_facts(observation: LocalObservation) -> None:
    context = json.loads(ContextCompiler().compile({"name": "Alice"}, observation))
    assert context["p"]["name"] == "Alice"
    assert context["s"]["id"] == 1
    assert context["s"]["loc"] == "home"
    assert context["s"]["money"] == 100.0
    assert context["s"]["hunger"] == 0.8


def test_full_world_state_is_not_serialized(observation: LocalObservation) -> None:
    result = ContextCompiler().compile(
        {"name": "Alice", "world_state": {"people": {2: "PRIVATE_BOB"}}},
        observation,
    )
    assert "world_state" not in result
    assert "PRIVATE_BOB" not in result
    assert "people" not in result


def test_rule_set_is_not_serialized(observation: LocalObservation) -> None:
    result = ContextCompiler().compile(
        {"name": "Alice", "RuleSet": "PRIVATE_RULES", "tools": "FULL_TOOL_SCHEMA"},
        observation,
    )
    assert "RuleSet" not in result
    assert "PRIVATE_RULES" not in result
    assert "FULL_TOOL_SCHEMA" not in result


def test_minimal_context_is_well_under_budget(observation: LocalObservation) -> None:
    compiler = ContextCompiler(max_chars=1500)
    result = compiler.compile({"name": "Alice"}, observation)
    assert len(result) < 1500
    assert len(result) <= compiler.max_chars


def test_long_strings_are_explicitly_truncated(observation: LocalObservation) -> None:
    result = json.loads(
        ContextCompiler().compile(
            {"name": "A" * 1000},
            observation,
            working_memory="M" * 1000,
        )
    )
    assert len(result["p"]["name"]) == ContextCompiler.MAX_PROFILE_STRING_CHARS
    assert result["p"]["name"].endswith("…")
    assert len(result["wm"]) == ContextCompiler.MAX_MEMORY_STRING_CHARS
    assert result["wm"].endswith("…")


def test_total_budget_overflow_is_rejected(observation: LocalObservation) -> None:
    with pytest.raises(ValueError, match="exceeds max_chars"):
        ContextCompiler(max_chars=20).compile({"name": "Alice"}, observation)


def test_collection_count_limits_are_enforced(observation: LocalObservation) -> None:
    compiler = ContextCompiler()
    with pytest.raises(ValueError, match="maximum item count"):
        compiler.compile(
            {"name": "Alice"}, observation,
            relevant_memories=["m"] * (compiler.MAX_RELEVANT_MEMORIES + 1),
        )
    with pytest.raises(ValueError, match="maximum item count"):
        compiler.compile(
            {"name": "Alice"}, observation,
            events=["e"] * (compiler.MAX_EVENTS + 1),
        )
    with pytest.raises(ValueError, match="maximum item count"):
        compiler.compile(
            {"name": "Alice"}, observation,
            available_actions=["A"] * (compiler.MAX_AVAILABLE_ACTIONS + 1),
        )


def test_optional_lists_remain_compact(observation: LocalObservation) -> None:
    result = json.loads(
        ContextCompiler().compile(
            {"name": "Alice", "age": 20, "role": "resident"}, observation,
            relevant_memories=["recent event"],
            events=["heard a bell"],
            available_actions=["REST"],
        )
    )
    assert result["m"] == ["recent event"]
    assert result["e"] == ["heard a bell"]
    assert result["a"] == ["REST"]
    assert set(result["p"]) == {"name", "age", "role"}


def test_unbounded_profile_number_is_rejected(observation: LocalObservation) -> None:
    with pytest.raises(ValueError, match="profile.age"):
        ContextCompiler().compile({"name": "Alice", "age": 10**100}, observation)
