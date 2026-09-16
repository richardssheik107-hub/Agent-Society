"""Strict, deterministic conversion of a single model response to a proposal."""

from __future__ import annotations

import json
import re

from social_sim.decision.models import DecisionProposal


class DecisionParseError(ValueError):
    """The model response is not a valid two-field decision proposal."""


_SIMPLE_FENCE = re.compile(r"```(?:json)?[ \t]*\r?\n(.*?)\r?\n?```", re.DOTALL)
_ALLOWED_FIELDS = frozenset({"action", "target"})


def _unique_object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DecisionParseError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


class DecisionParser:
    """Parse JSON only; never guess an action or call a model for repairs."""

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
