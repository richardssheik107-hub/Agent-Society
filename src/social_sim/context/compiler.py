"""Compile only local facts into a bounded context; never call a model."""

from __future__ import annotations

import json
import math
import re
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
    MAX_AVAILABLE_ACTIONS = 8
    MAX_AVAILABLE_TARGETS = 5
    MAX_LOCAL_ITEMS = 5
    MAX_PROFILE_STRING_CHARS = 96
    MAX_STATE_STRING_CHARS = 96
    MAX_MEMORY_STRING_CHARS = 240
    MAX_ACTION_STRING_CHARS = 48
    MAX_BEHAVIOR_HINTS = 3
    MAX_BEHAVIOR_HINT_CHARS = 96

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
        available_targets: Sequence[str] | None = None,
        daily_mode: bool = False,
        work_window: str | None = None,
        behavior_hints: Sequence[str] | None = None,
    ) -> str:
        """Return compact JSON containing only explicitly allowed local facts."""
        if not isinstance(profile, Mapping):
            raise TypeError("profile must be a mapping")
        if not isinstance(observation, LocalObservation):
            raise TypeError("observation must be a LocalObservation")
        if not isinstance(daily_mode, bool):
            raise TypeError("daily_mode must be a boolean")
        if not daily_mode and (work_window is not None or behavior_hints is not None):
            raise ValueError("daily context inputs require daily_mode=True")

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
        if daily_mode:
            for key in ("occupation", "personality", "home", "workplace"):
                value = profile.get(key)
                if value is not None:
                    compact_profile[key] = self._clip(
                        self._require_string(value, f"profile.{key}"),
                        self.MAX_PROFILE_STRING_CHARS,
                    )
        else:
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
        inventory = self._compact_inventory(observation.inventory)
        if inventory:
            compact_state["inv"] = inventory
        offers = self._compact_offers(observation.offers)
        if offers:
            compact_state["offers"] = offers
        if daily_mode:
            energy = observation.energy
            if energy is None:
                raise ValueError("daily observation must include energy")
            compact_state["energy"] = self._finite_number(energy, "observation.energy")
            if not 0 <= compact_state["energy"] <= 1:
                raise ValueError("observation.energy must be between 0 and 1")
            activity = observation.activity
            if activity is not None:
                compact_state["act"] = self._clip(
                    self._require_string(activity, "observation.activity"),
                    self.MAX_ACTION_STRING_CHARS,
                )
                end_time = observation.activity_end_time
                if end_time is None:
                    raise ValueError("active activity requires activity_end_time")
                compact_state["rem"] = self._remaining_minutes(time, end_time)
            else:
                compact_state["act"] = None
                compact_state["rem"] = 0
        context: dict[str, object] = {"p": compact_profile, "s": compact_state}

        if daily_mode:
            if work_window is not None:
                if not isinstance(work_window, str) or not re.fullmatch(
                    r"(?:[01][0-9]|2[0-3]):[0-5][0-9]-(?:[01][0-9]|2[0-3]):[0-5][0-9]",
                    work_window,
                ):
                    raise ValueError("work_window must be HH:MM-HH:MM")
                context["work"] = work_window
            self._add_bounded_list(
                context,
                "h",
                behavior_hints,
                self.MAX_BEHAVIOR_HINTS,
                self.MAX_BEHAVIOR_HINT_CHARS,
            )

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
        # An explicit event selection keeps the same prompt structure across
        # context policies, including the state-only e:[] condition.
        if events is not None:
            context.setdefault("e", [])
        self._add_bounded_list(
            context, "a", available_actions, self.MAX_AVAILABLE_ACTIONS,
            self.MAX_ACTION_STRING_CHARS,
        )
        self._add_bounded_list(
            context, "targets", available_targets, self.MAX_AVAILABLE_TARGETS,
            self.MAX_ACTION_STRING_CHARS,
        )

        serialized = json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if len(serialized) > self.max_chars:
            raise ValueError(
                f"Compiled context exceeds max_chars: {len(serialized)} > {self.max_chars}"
            )
        return serialized

    @staticmethod
    def _remaining_minutes(time: str, end_time: str) -> int:
        if not isinstance(end_time, str):
            raise TypeError("observation.activity_end_time must be an ISO string")
        try:
            current = datetime.fromisoformat(time)
            end = datetime.fromisoformat(end_time)
            seconds = (end - current).total_seconds()
        except (TypeError, ValueError) as error:
            raise ValueError("activity times must be comparable ISO datetimes") from error
        return math.ceil(max(0, seconds) / 60)

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
    def _compact_inventory(cls, inventory: Mapping[str, int]) -> dict[str, int]:
        if not isinstance(inventory, Mapping):
            raise TypeError("observation.inventory must be a mapping")
        if len(inventory) > cls.MAX_LOCAL_ITEMS:
            raise ValueError("observation.inventory exceeds maximum item count")
        compact: dict[str, int] = {}
        for item_id, quantity in sorted(inventory.items()):
            cls._validate_item_id(item_id, "observation.inventory")
            if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 0:
                raise ValueError("observation.inventory quantities must be non-negative integers")
            compact[item_id] = quantity
        return compact

    @classmethod
    def _compact_offers(
        cls, offers: Mapping[str, Mapping[str, float | bool]]
    ) -> dict[str, dict[str, float | bool]]:
        if not isinstance(offers, Mapping):
            raise TypeError("observation.offers must be a mapping")
        if len(offers) > cls.MAX_LOCAL_ITEMS:
            raise ValueError("observation.offers exceeds maximum item count")
        compact: dict[str, dict[str, float | bool]] = {}
        for item_id, offer in sorted(offers.items()):
            cls._validate_item_id(item_id, "observation.offers")
            if not isinstance(offer, Mapping):
                raise TypeError("observation.offers values must be mappings")
            price = cls._finite_number(offer.get("price"), "observation.offers.price")
            if price < 0:
                raise ValueError("observation.offers.price must be non-negative")
            available = offer.get("available")
            if not isinstance(available, bool):
                raise TypeError("observation.offers.available must be a boolean")
            compact[item_id] = {"p": price, "a": available}
        return compact

    @classmethod
    def _validate_item_id(cls, item_id: object, field: str) -> None:
        if not isinstance(item_id, str) or not item_id.strip():
            raise ValueError(f"{field} item IDs must be nonempty strings")
        if len(item_id) > cls.MAX_ACTION_STRING_CHARS:
            raise ValueError(f"{field} item ID exceeds maximum length")

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
