"""Strict, deterministic conversion of a single model response to a proposal."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass

from social_sim.decision.models import ActionType, DecisionProposal


class DecisionParseError(ValueError):
    """The model response is not a valid two-field decision proposal."""


_SIMPLE_FENCE = re.compile(r"```(?:json)?[ \t]*\r?\n(.*?)\r?\n?```", re.DOTALL)
_ALLOWED_FIELDS = frozenset({"action", "target"})
_TARGETED_ACTIONS = frozenset({ActionType.MOVE, ActionType.BUY, ActionType.EAT})
_NULL_TARGET_REPAIR_ACTIONS = frozenset(
    {ActionType.SLEEP, ActionType.WORK, ActionType.LEISURE,
     ActionType.PERSONAL_CARE, ActionType.CHORES}
)
_MAX_SURROUNDING_TEXT_CHARS = 160
_FORMAT_FAILURES = frozenset(
    {
        "CODE_FENCED_JSON",
        "EXTRA_TEXT_AROUND_JSON",
        "MULTIPLE_JSON_OBJECTS",
        "MALFORMED_JSON",
    }
)
_PROVIDER_FAILURES = frozenset(
    {
        "EMPTY_CONTENT",
        "PROVIDER_REFUSAL",
        "TOOL_CALL_INSTEAD_OF_TEXT",
        "NO_CHOICES",
        "OUTPUT_BUDGET_EXHAUSTED",
        "PROVIDER_SCHEMA_MISMATCH",
    }
)


@dataclass(frozen=True)
class DecisionParseResult:
    """Safe, text-free diagnostics for one visible final model response.

    ``failure_type`` describes why strict parsing failed, even if a limited
    deterministic repair succeeded. Provider-envelope failures are assigned by
    the caller before this parser is reached.
    """

    strict_valid: bool
    recoverable_valid: bool
    failure_type: str | None
    proposal: DecisionProposal | None
    repair_applied: str | None
    visible_content_chars: int
    json_object_count: int
    failure_category: str | None


class _DuplicateFieldError(DecisionParseError):
    pass


def _unique_object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateFieldError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def _top_level_object_spans(raw: str) -> list[tuple[int, int]]:
    """Locate balanced top-level brace spans without treating quoted braces as syntax."""
    spans: list[tuple[int, int]] = []
    depth = 0
    start = 0
    quoted = False
    escaped = False
    for index, character in enumerate(raw):
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
            continue
        if character == '"':
            quoted = True
        elif character == "{":
            if depth == 0:
                start = index
            depth += 1
        elif character == "}" and depth:
            depth -= 1
            if depth == 0:
                spans.append((start, index + 1))
    return spans


def _complete_object_spans(raw: str) -> list[tuple[int, int]]:
    """Count syntactically complete objects, including ones with duplicate keys."""
    spans: list[tuple[int, int]] = []
    for start, end in _top_level_object_spans(raw):
        try:
            value = json.loads(raw[start:end])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            spans.append((start, end))
    return spans


def _schema_result(
    data: object,
    *,
    available_actions: Sequence[ActionType | str] | None,
    available_targets: Sequence[str] | None,
    allow_missing_null_target: bool,
) -> tuple[DecisionProposal | None, str | None, bool]:
    """Validate the two-field contract and optionally add a safe null target."""
    if not isinstance(data, dict):
        return None, "WRONG_FIELD_TYPE", False
    if data.keys() - _ALLOWED_FIELDS:
        return None, "EXTRA_FIELDS", False
    if "action" not in data:
        return None, "MISSING_ACTION", False
    raw_action = data["action"]
    if not isinstance(raw_action, str):
        return None, "WRONG_FIELD_TYPE", False
    try:
        action = ActionType(raw_action)
    except ValueError:
        return None, "INVALID_ACTION", False
    if available_actions is not None and action not in {
        ActionType(item) for item in available_actions
    }:
        return None, (
            "ACTION_NOT_AVAILABLE_FOR_PROFILE" if action in (
                ActionType.PERSONAL_CARE, ActionType.CHORES,
            ) else "INVALID_ACTION"
        ), False
    added_target = False
    if "target" not in data:
        if allow_missing_null_target and action in _NULL_TARGET_REPAIR_ACTIONS:
            target: object = None
            added_target = True
        else:
            return None, "MISSING_TARGET", False
    else:
        target = data["target"]
    if action in _TARGETED_ACTIONS:
        if target is None or target == "":
            return None, "INVALID_TARGET", False
        if not isinstance(target, str):
            return None, "WRONG_FIELD_TYPE", False
        if not target.strip():
            return None, "INVALID_TARGET", False
        if available_targets is not None and target not in available_targets:
            return None, "INVALID_TARGET", False
    elif target is not None:
        return (
            None,
            "INVALID_TARGET" if isinstance(target, str) else "WRONG_FIELD_TYPE",
            False,
        )
    return DecisionProposal(action, target), None, added_target


def _category(failure_type: str | None) -> str | None:
    if failure_type is None:
        return None
    if failure_type in _PROVIDER_FAILURES:
        return "PROVIDER_FAILURE"
    if failure_type in _FORMAT_FAILURES:
        return "FORMAT_FAILURE"
    return "SEMANTIC_FAILURE"


def deterministic_recover(
    raw: str | None,
    *,
    available_actions: Sequence[ActionType | str] | None = None,
    available_targets: Sequence[str] | None = None,
) -> DecisionParseResult:
    """Dual-evaluate strict JSON and bounded, deterministic format recovery.

    No action or target is inferred. The only schema completion is
    ``target:null`` for SLEEP, WORK, and LEISURE.
    """
    chars = len(raw) if isinstance(raw, str) else 0
    if raw is None or raw == "" or isinstance(raw, str) and not raw.strip():
        return DecisionParseResult(
            False, False, "EMPTY_CONTENT", None, None, chars, 0, "PROVIDER_FAILURE"
        )
    if not isinstance(raw, str):
        return DecisionParseResult(
            False,
            False,
            "PROVIDER_SCHEMA_MISMATCH",
            None,
            None,
            0,
            0,
            "PROVIDER_FAILURE",
        )

    complete_spans = _complete_object_spans(raw)
    object_count = len(complete_spans)
    if object_count > 1:
        return DecisionParseResult(
            False,
            False,
            "MULTIPLE_JSON_OBJECTS",
            None,
            None,
            chars,
            object_count,
            "FORMAT_FAILURE",
        )

    if object_count == 1:
        start, end = complete_spans[0]
        try:
            json.loads(raw[start:end], object_pairs_hook=_unique_object_pairs)
        except _DuplicateFieldError:
            return DecisionParseResult(
                False,
                False,
                "EXTRA_FIELDS",
                None,
                None,
                chars,
                object_count,
                "SEMANTIC_FAILURE",
            )

    try:
        strict_data = json.loads(raw, object_pairs_hook=_unique_object_pairs)
    except (_DuplicateFieldError, json.JSONDecodeError):
        strict_data = None
    else:
        proposal, failure, _ = _schema_result(
            strict_data,
            available_actions=available_actions,
            available_targets=available_targets,
            allow_missing_null_target=False,
        )
        if proposal is not None:
            return DecisionParseResult(True, True, None, proposal, None, chars, 1, None)
        # A valid JSON document with an invalid contract is never rescued by
        # extraction. Only the one explicitly allowed null-target addition is.
        if failure == "MISSING_TARGET":
            proposal, _, added = _schema_result(
                strict_data,
                available_actions=available_actions,
                available_targets=available_targets,
                allow_missing_null_target=True,
            )
            if proposal is not None and added:
                return DecisionParseResult(
                    False,
                    True,
                    "MISSING_TARGET",
                    proposal,
                    "ADD_NULL_TARGET",
                    chars,
                    1,
                    "SEMANTIC_FAILURE",
                )
        return DecisionParseResult(
            False,
            False,
            failure,
            None,
            None,
            chars,
            object_count,
            _category(failure),
        )

    if object_count != 1:
        return DecisionParseResult(
            False,
            False,
            "MALFORMED_JSON",
            None,
            None,
            chars,
            object_count,
            "FORMAT_FAILURE",
        )

    start, end = complete_spans[0]
    prefix, suffix = raw[:start], raw[end:]
    candidate = raw[start:end]
    repair: str | None = None
    failure_type: str | None = None
    fence = _SIMPLE_FENCE.fullmatch(raw.strip())
    if fence is not None and fence.group(1).strip() == candidate:
        repair = "STRIP_CODE_FENCE"
        failure_type = "CODE_FENCED_JSON"
    elif (
        len(prefix) <= _MAX_SURROUNDING_TEXT_CHARS
        and len(suffix) <= _MAX_SURROUNDING_TEXT_CHARS
        and not any(character in prefix + suffix for character in "{}<`>")
        and (prefix.strip() or suffix.strip())
    ):
        repair = "EXTRACT_SINGLE_JSON"
        failure_type = "EXTRA_TEXT_AROUND_JSON"
    else:
        return DecisionParseResult(
            False,
            False,
            "MALFORMED_JSON",
            None,
            None,
            chars,
            object_count,
            "FORMAT_FAILURE",
        )

    data = json.loads(candidate, object_pairs_hook=_unique_object_pairs)
    proposal, schema_failure, added = _schema_result(
        data,
        available_actions=available_actions,
        available_targets=available_targets,
        allow_missing_null_target=True,
    )
    if proposal is None:
        return DecisionParseResult(
            False,
            False,
            schema_failure,
            None,
            None,
            chars,
            object_count,
            _category(schema_failure),
        )
    if added:
        repair += "+ADD_NULL_TARGET"
    return DecisionParseResult(
        False,
        True,
        failure_type,
        proposal,
        repair,
        chars,
        object_count,
        _category(failure_type),
    )


class DecisionParser:
    """Parse JSON only; never guess an action or call a model for repairs."""

    def evaluate(
        self,
        raw: str | None,
        *,
        available_actions: Sequence[ActionType | str] | None = None,
        available_targets: Sequence[str] | None = None,
    ) -> DecisionParseResult:
        """Measure strict and recoverable validity without selecting a policy."""
        return deterministic_recover(
            raw,
            available_actions=available_actions,
            available_targets=available_targets,
        )

    def parse_strict(
        self,
        raw: str,
        *,
        available_actions: Sequence[ActionType | str] | None = None,
        available_targets: Sequence[str] | None = None,
    ) -> DecisionProposal:
        """Require a complete, two-field JSON object with no format repair."""
        result = self.evaluate(
            raw,
            available_actions=available_actions,
            available_targets=available_targets,
        )
        if not result.strict_valid or result.proposal is None:
            raise DecisionParseError(result.failure_type or "INVALID_MODEL_OUTPUT")
        return result.proposal

    def parse(self, raw: str) -> DecisionProposal:
        if not isinstance(raw, str):
            raise DecisionParseError("Decision output must be a string")
        payload = raw.strip()
        fence = _SIMPLE_FENCE.fullmatch(payload)
        if fence is not None:
            payload = fence.group(1).strip()
        try:
            data = json.loads(payload, object_pairs_hook=_unique_object_pairs)
        except (json.JSONDecodeError, DecisionParseError) as exc:
            raise DecisionParseError(f"Invalid decision JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise DecisionParseError("Decision JSON must be an object")
        extra = data.keys() - _ALLOWED_FIELDS
        if extra:
            raise DecisionParseError(f"Unexpected decision field(s): {sorted(extra)}")
        if "action" not in data:
            raise DecisionParseError("Decision JSON requires action")
        try:
            return DecisionProposal(action=data["action"], target=data.get("target"))
        except ValueError as exc:
            raise DecisionParseError(str(exc)) from exc
