"""The small, deterministic source of truth for Phase 1 world facts."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Mapping


DEFAULT_LOCATIONS = ("home", "park", "restaurant")


@dataclass(frozen=True)
class PersonWorldState:
    agent_id: int
    location: str
    money: float
    hunger: float

    def __post_init__(self) -> None:
        if self.money < 0:
            raise ValueError("money must be non-negative")
        if not 0 <= self.hunger <= 1:
            raise ValueError("hunger must be between 0 and 1")


@dataclass(frozen=True, init=False)
class WorldState:
    time: datetime
    _people: tuple[PersonWorldState, ...] = field(repr=False)
    _locations: tuple[str, ...] = field(repr=False)

    def __init__(
        self,
        time: datetime,
        people: Mapping[int, PersonWorldState],
        locations: Iterable[str] = DEFAULT_LOCATIONS,
    ) -> None:
        if any(agent_id != person.agent_id for agent_id, person in people.items()):
            raise ValueError("people keys must match their agent_id values")
        location_ids = tuple(locations)
        if not location_ids or any(
            not isinstance(location_id, str) or not location_id.strip()
            for location_id in location_ids
        ):
            raise ValueError("locations must contain nonempty string IDs")
        if len(set(location_ids)) != len(location_ids):
            raise ValueError("locations must be unique")
        object.__setattr__(self, "time", time)
        object.__setattr__(
            self, "_people", tuple(person for _, person in sorted(people.items()))
        )
        object.__setattr__(self, "_locations", tuple(sorted(location_ids)))

    @property
    def people(self) -> dict[int, PersonWorldState]:
        """Return a copy; callers cannot change the world's stored people."""
        return {person.agent_id: person for person in self._people}

    @property
    def locations(self) -> tuple[str, ...]:
        """The world's sole source of valid destination IDs."""
        return self._locations

    def get_person(self, agent_id: int) -> PersonWorldState:
        for person in self._people:
            if person.agent_id == agent_id:
                return person
        raise ValueError(f"Unknown agent_id: {agent_id}")
