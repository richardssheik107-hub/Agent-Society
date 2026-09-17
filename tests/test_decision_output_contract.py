"""Offline fixtures for strict validity and bounded deterministic recovery."""

from __future__ import annotations

import pytest

from social_sim.decision.client import ProviderContractError, inspect_chat_completion
from social_sim.decision.models import ActionType, DecisionProposal
from social_sim.decision.parser import (
    DecisionParseError,
    DecisionParser,
    deterministic_recover,
)


DAILY_ACTIONS = (
    ActionType.MOVE,
    ActionType.BUY,
    ActionType.EAT,
    ActionType.SLEEP,
    ActionType.WORK,
    ActionType.LEISURE,
)
TARGETS = ("home", "office", "restaurant", "meal")


@pytest.mark.parametrize(
    "raw,strict,recoverable,failure,repair,count",
    [
        ('{"action":"WORK","target":null}', True, True, None, None, 1),
        (' \n{"action":"WORK","target":null}\t', True, True, None, None, 1),
        (
            '```json\n{"action":"WORK","target":null}\n```',
            False,
            True,
            "CODE_FENCED_JSON",
            "STRIP_CODE_FENCE",
            1,
        ),
        (
            'I choose:\n{"action":"MOVE","target":"office"}',
            False,
            True,
            "EXTRA_TEXT_AROUND_JSON",
            "EXTRACT_SINGLE_JSON",
            1,
        ),
        (
            '{"action":"WORK","target":null}\nThis is my choice.',
            False,
            True,
            "EXTRA_TEXT_AROUND_JSON",
            "EXTRACT_SINGLE_JSON",
            1,
        ),
        (
            'Decision: {"action":"WORK","target":null} End.',
            False,
            True,
            "EXTRA_TEXT_AROUND_JSON",
            "EXTRACT_SINGLE_JSON",
            1,
        ),
        (
            '{"action":"WORK"}',
            False,
            True,
            "MISSING_TARGET",
            "ADD_NULL_TARGET",
            1,
        ),
        (
            '```json\n{"action":"WORK"}\n```',
            False,
            True,
            "CODE_FENCED_JSON",
            "STRIP_CODE_FENCE+ADD_NULL_TARGET",
            1,
        ),
        (
            'I choose {"action":"SLEEP"}.',
            False,
            True,
            "EXTRA_TEXT_AROUND_JSON",
            "EXTRACT_SINGLE_JSON+ADD_NULL_TARGET",
            1,
        ),
        (
            '{"action":"WORK","target":null} {"action":"SLEEP","target":null}',
            False,
            False,
            "MULTIPLE_JSON_OBJECTS",
            None,
            2,
        ),
        (
            '{"action":"WORK","target":null',
            False,
            False,
            "MALFORMED_JSON",
            None,
            0,
        ),
        (
            '{"action":"WORK","target":null,}',
            False,
            False,
            "MALFORMED_JSON",
            None,
            0,
        ),
        ('{"target":null}', False, False, "MISSING_ACTION", None, 1),
        ('{"action":"FLY","target":null}', False, False, "INVALID_ACTION", None, 1),
        ('{"action":"MOVE"}', False, False, "MISSING_TARGET", None, 1),
        ('{"action":"MOVE","target":null}', False, False, "INVALID_TARGET", None, 1),
        (
            '{"action":"MOVE","target":"resturant"}',
            False,
            False,
            "INVALID_TARGET",
            None,
            1,
        ),
        (
            '{"action":"WORK","target":"office"}',
            False,
            False,
            "INVALID_TARGET",
            None,
            1,
        ),
        (
            '{"action":"WORK","target":null,"reason":"I want to"}',
            False,
            False,
            "EXTRA_FIELDS",
            None,
            1,
        ),
        ('{"action":5,"target":null}', False, False, "WRONG_FIELD_TYPE", None, 1),
        ('{"action":"MOVE","target":5}', False, False, "WRONG_FIELD_TYPE", None, 1),
        (
            '{"action":"WORK","action":"SLEEP","target":null}',
            False,
            False,
            "EXTRA_FIELDS",
            None,
            1,
        ),
        ('{"action":"WAIT","target":null}', False, False, "INVALID_ACTION", None, 1),
        (
            '{"action":"WORK","target":null} {invalid}',
            False,
            False,
            "MALFORMED_JSON",
            None,
            1,
        ),
        ('["WORK"]', False, False, "WRONG_FIELD_TYPE", None, 0),
    ],
)
def test_dual_parser_fixtures(
    raw: str,
    strict: bool,
    recoverable: bool,
    failure: str | None,
    repair: str | None,
    count: int,
) -> None:
    result = DecisionParser().evaluate(
        raw, available_actions=DAILY_ACTIONS, available_targets=TARGETS
    )
    assert result.strict_valid is strict
    assert result.recoverable_valid is recoverable
    assert result.failure_type == failure
    assert result.repair_applied == repair
    assert result.json_object_count == count
    assert result.visible_content_chars == len(raw)
    assert (result.proposal is not None) is recoverable


def test_strict_parser_rejects_recoverable_code_fence() -> None:
    parser = DecisionParser()
    raw = '```json\n{"action":"WORK","target":null}\n```'
    assert parser.evaluate(raw).recoverable_valid
    with pytest.raises(DecisionParseError, match="CODE_FENCED_JSON"):
        parser.parse_strict(raw)
    assert parser.parse_strict('{"action":"WORK","target":null}') == (
        DecisionProposal(ActionType.WORK)
    )


def test_legacy_parser_remains_compatible() -> None:
    parser = DecisionParser()
    assert parser.parse('```json\n{"action":"WORK"}\n```') == (
        DecisionProposal(ActionType.WORK)
    )


@pytest.mark.parametrize("raw", [None, "", "   \n"])
def test_empty_content_is_provider_failure(raw: str | None) -> None:
    result = deterministic_recover(raw)
    assert result.failure_type == "EMPTY_CONTENT"
    assert result.failure_category == "PROVIDER_FAILURE"
    assert not result.recoverable_valid


def test_nonstring_content_is_provider_schema_mismatch() -> None:
    result = deterministic_recover(["not", "final", "text"])  # type: ignore[arg-type]
    assert result.failure_type == "PROVIDER_SCHEMA_MISMATCH"
    assert result.failure_category == "PROVIDER_FAILURE"


@pytest.mark.parametrize(
    "raw,category",
    [
        ('```json\n{"action":"WORK","target":null}\n```', "FORMAT_FAILURE"),
        ('{"action":"FLY","target":null}', "SEMANTIC_FAILURE"),
        ('{"action":"MOVE","target":"resturant"}', "SEMANTIC_FAILURE"),
        (
            '{"action":"WORK","target":null} {"action":"SLEEP","target":null}',
            "FORMAT_FAILURE",
        ),
    ],
)
def test_failure_categories_are_distinct(raw: str, category: str) -> None:
    result = deterministic_recover(
        raw, available_actions=DAILY_ACTIONS, available_targets=TARGETS
    )
    assert result.failure_category == category


def test_no_arbitrary_choice_when_multiple_objects() -> None:
    result = deterministic_recover(
        'Ignore this: {"action":"INVALID","target":null}; '
        '{"action":"WORK","target":null}'
    )
    assert result.failure_type == "MULTIPLE_JSON_OBJECTS"
    assert result.proposal is None


@pytest.mark.parametrize(
    "raw,expected_failure",
    [
        ("I want to work", "MALFORMED_JSON"),
        ('{"action":"do_work","target":null}', "INVALID_ACTION"),
        ('{"action":"REST","target":null}', "INVALID_ACTION"),
        (
            '{"action":"SLEEP","target":null} {"action":"WORK","target":null}',
            "MULTIPLE_JSON_OBJECTS",
        ),
        ('{"action":"MOVE","target":"resturant"}', "INVALID_TARGET"),
        (
            'Here is a decision:\n```json\n{"action":"WORK","target":null}\n```',
            "MALFORMED_JSON",
        ),
        ('{"action":"WORK","target":null}' + "x" * 161, "MALFORMED_JSON"),
        ('{"action":"WAIT"}', "INVALID_ACTION"),
        ('{"action":"REST"}', "INVALID_ACTION"),
    ],
)
def test_no_semantic_guessing_or_unbounded_extraction(
    raw: str, expected_failure: str
) -> None:
    result = deterministic_recover(
        raw, available_actions=DAILY_ACTIONS, available_targets=TARGETS
    )
    assert not result.recoverable_valid
    assert result.failure_type == expected_failure


@pytest.mark.parametrize("action", ["WAIT", "REST"])
def test_null_target_repair_is_not_extended_to_legacy_actions(action: str) -> None:
    result = deterministic_recover('{"action":"' + action + '"}')
    assert result.failure_type == "MISSING_TARGET"
    assert not result.recoverable_valid


def test_nested_object_does_not_count_as_multiple_top_level_objects() -> None:
    result = deterministic_recover('{"action":"MOVE","target":{"id":"office"}}')
    assert result.json_object_count == 1
    assert result.failure_type == "WRONG_FIELD_TYPE"


@pytest.mark.parametrize(
    "payload,category",
    [
        ({"choices": []}, "NO_CHOICES"),
        ({"choices": [{}]}, "PROVIDER_SCHEMA_MISMATCH"),
        (
            {"choices": [{"finish_reason": "length", "message": {"content": None}}]},
            "OUTPUT_BUDGET_EXHAUSTED",
        ),
        (
            {"choices": [{"message": {"content": None, "refusal": "No"}}]},
            "PROVIDER_REFUSAL",
        ),
        (
            {"choices": [{"message": {"content": None, "tool_calls": [{}]}}]},
            "TOOL_CALL_INSTEAD_OF_TEXT",
        ),
        (
            {"choices": [{"message": {"content": None}}]},
            "EMPTY_FINAL_CONTENT",
        ),
    ],
)
def test_provider_failures_remain_outside_parser(payload: dict, category: str) -> None:
    with pytest.raises(ProviderContractError) as error:
        inspect_chat_completion(payload)
    assert error.value.category == category
