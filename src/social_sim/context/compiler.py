"""Compile only local facts into a bounded context; never call a model."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from datetime import datetime

from social_sim.world.observation import LocalObservation


class ContextCompiler:
    """Create deterministic compact JSON under a model-independent character budget.

    Unknown profile keys are ignored, not serialized. Optional collections must
    already be selected and small; exceeding their limits raises ValueError.
    Strings are truncated with an ellipsis, while exceeding the *total* budget
    raises ValueError rather than silently dropping required observation facts.
    """

    HARD_MAX_CHARS = 6000
    MAX_PROFILE_FIELDS = 4
    MAX_RELEVANT_MEMORIES = 3
    MAX_EVENTS = 3
    MAX_AVAILABLE_ACTIONS = 6
    MAX_PROFILE_STRING_CHARS = 96
    MAX_STATE_STRING_CHARS = 96
    MAX_MEMORY_STRING_CHARS = 240
    MAX_ACTION_STRING_CHARS = 48

    def __init__(self, max_chars: int = HARD_MAX_CHARS) -> None:
        if isinstance(max_chars, bool) or not isinstance(max_chars, int):
            raise TypeError("max_chars must be an integer")
        if not 0 < max_chars <= self.HARD_MAX_CHARS:
            raise ValueError(f"max_chars must be between 1 and {self.HARD_MAX_CHARS}")
        self.max_chars = max_chars

    def compile(
        self,
        profile: Mapping[str, object],
        observation: LocalObservation,
        working_memory: str | None = None,
        relevant_memories: Sequence[str] | None = None,
        available_actions: Sequence[str] | None = None,
        events: Sequence[str] | None = None,
    ) -> str:
        """Return compact JSON containing only explicitly allowed local facts."""
        if not isinstance(profile, Mapping):
            raise TypeError("profile must be a mapping")
        if not isinstance(observation, LocalObservation):
            raise TypeError("observation must be a LocalObservation")

        name = profile.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("profile.name must be a nonempty string")

        compact_profile: dict[str, str | int] = {
            "name": self._clip(name, self.MAX_PROFILE_STRING_CHARS)
        }
        for key in ("role", "goal"):
            value = profile.get(key)
            if value is not None:
                compact_profile[key] = self._clip(
                    self._require_string(value, f"profile.{key}"),
                    self.MAX_PROFILE_STRING_CHARS,
                )
        age = profile.get("age")
        if age is not None:
            if isinstance(age, bool) or not isinstance(age, int):
                raise TypeError("profile.age must be an integer")
            if not 0 <= age <= 150:
                raise ValueError("profile.age must be between 0 and 150")
            compact_profile["age"] = age
        assert len(compact_profile) <= self.MAX_PROFILE_FIELDS

        agent_id = observation.agent_id
        if isinstance(agent_id, bool) or not isinstance(agent_id, int):
            raise TypeError("observation.agent_id must be an integer")
        time = observation.time
        if isinstance(time, datetime):
            time = time.isoformat()
        compact_state = {
            "id": agent_id,
            "t": self._clip(self._require_string(time, "observation.time"), 64),
            "loc": self._clip(
                self._require_string(observation.location, "observation.location"),
                self.MAX_STATE_STRING_CHARS,
            ),
            "money": self._finite_number(observation.money, "observation.money"),
            "hunger": self._finite_number(observation.hunger, "observation.hunger"),
        }
        context: dict[str, object] = {"p": compact_profile, "s": compact_state}

        if working_memory is not None:
            context["wm"] = self._clip(
                self._require_string(working_memory, "working_memory"),
                self.MAX_MEMORY_STRING_CHARS,
            )
        self._add_bounded_list(
            context, "m", relevant_memories, self.MAX_RELEVANT_MEMORIES,
            self.MAX_MEMORY_STRING_CHARS,
        )
        self._add_bounded_list(
            context, "e", events, self.MAX_EVENTS, self.MAX_MEMORY_STRING_CHARS,
        )
        self._add_bounded_list(
            context, "a", available_actions, self.MAX_AVAILABLE_ACTIONS,
            self.MAX_ACTION_STRING_CHARS,
        )

        serialized = json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if len(serialized) > self.max_chars:
            raise ValueError(
                f"Compiled context exceeds max_chars: {len(serialized)} > {self.max_chars}"
            )
        return serialized

    @staticmethod
    def _require_string(value: object, field: str) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{field} must be a string")
        return value

    @staticmethod
    def _clip(value: str, limit: int) -> str:
        return value if len(value) <= limit else value[: limit - 1] + "…"

    @staticmethod
    def _finite_number(value: object, field: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{field} must be a number")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"{field} must be finite")
        return number

    @classmethod
    def _add_bounded_list(
        cls,
        context: dict[str, object],
        key: str,
        values: Sequence[str] | None,
        count_limit: int,
        string_limit: int,
    ) -> None:
        if values is None:
            return
        if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
            raise TypeError(f"{key} must be a sequence of strings")
        if len(values) > count_limit:
            raise ValueError(f"{key} exceeds maximum item count: {len(values)} > {count_limit}")
        if values:
            context[key] = [
                cls._clip(cls._require_string(value, f"{key}[{index}]"), string_limit)
                for index, value in enumerate(values)
            ]
