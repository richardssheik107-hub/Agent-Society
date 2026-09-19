"""Compact catalog address space for the Q5 rule-graph benchmark."""

from __future__ import annotations

from .models import RetrievalResult, TypeSpec


class VirtualObjectCatalog:
    """Address N canonical object ids without allocating N Python objects."""

    def __init__(self, object_count: int, type_specs: tuple[TypeSpec, ...]) -> None:
        if object_count <= 0:
            raise ValueError("object_count must be positive")
        if not type_specs:
            raise ValueError("type_specs must be nonempty")
        self.object_count = object_count
        self.type_specs = type_specs
        self.type_count = len(type_specs)
        self._by_id = {spec.type_id: spec for spec in type_specs}
        self._types_by_capability: dict[str, tuple[int, ...]] = {}
        capabilities = sorted({cap for spec in type_specs for cap in spec.capabilities})
        for capability in capabilities:
            self._types_by_capability[capability] = tuple(
                spec.type_id for spec in type_specs if capability in spec.capabilities
            )

    @property
    def capability_type_entries(self) -> int:
        return sum(len(ids) for ids in self._types_by_capability.values())

    def type_id_for(self, object_id: int) -> int:
        self._validate_object_id(object_id)
        return object_id % self.type_count

    def type_for(self, object_id: int) -> TypeSpec:
        return self._by_id[self.type_id_for(object_id)]

    def has_capability(self, object_id: int, capability: str) -> bool:
        return capability in self.type_for(object_id).capabilities

    def count_for_type(self, type_id: int) -> int:
        if type_id not in self._by_id:
            raise ValueError("unknown type_id")
        if type_id >= self.object_count:
            return 0
        return ((self.object_count - 1 - type_id) // self.type_count) + 1

    def object_id_for_type_ordinal(self, type_id: int, ordinal: int) -> int:
        count = self.count_for_type(type_id)
        if ordinal < 0 or ordinal >= count:
            raise ValueError("type ordinal out of range")
        return type_id + ordinal * self.type_count

    def retrieve(self, capability: str, *, k: int = 50, seed: int = 0) -> RetrievalResult:
        if k <= 0:
            raise ValueError("k must be positive")
        type_ids = self._types_by_capability.get(capability)
        if not type_ids:
            return RetrievalResult((), 0, 0)
        eligible = tuple(type_id for type_id in type_ids if self.count_for_type(type_id) > 0)
        if not eligible:
            return RetrievalResult((), 0, 0)

        result: list[int] = []
        seen: set[int] = set()
        touches = 0
        attempt = 0
        max_attempts = k * 4
        while len(result) < k and attempt < max_attempts:
            type_id = eligible[(seed + attempt) % len(eligible)]
            count = self.count_for_type(type_id)
            ordinal = (seed * 104729 + attempt * 8191 + type_id * 97) % count
            object_id = self.object_id_for_type_ordinal(type_id, ordinal)
            touches += 1
            if object_id not in seen:
                seen.add(object_id)
                result.append(object_id)
            attempt += 1
        return RetrievalResult(tuple(result), touches, 0)

    def _validate_object_id(self, object_id: int) -> None:
        if isinstance(object_id, bool) or not isinstance(object_id, int):
            raise TypeError("object_id must be an integer")
        if object_id < 0 or object_id >= self.object_count:
            raise ValueError("object_id out of range")
