"""The small, deterministic source of truth for Phase 1 world facts."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping


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

    def __init__(self, time: datetime, people: Mapping[int, PersonWorldState]) -> None:
        if any(agent_id != person.agent_id for agent_id, person in people.items()):
            raise ValueError("people keys must match their agent_id values")
        object.__setattr__(self, "time", time)
        object.__setattr__(
            self, "_people", tuple(person for _, person in sorted(people.items()))
        )

    @property
    def people(self) -> dict[int, PersonWorldState]:
        """Return a copy; callers cannot change the world's stored people."""
        return {person.agent_id: person for person in self._people}

    def get_person(self, agent_id: int) -> PersonWorldState:
        for person in self._people:
            if person.agent_id == agent_id:
                return person
        raise ValueError(f"Unknown agent_id: {agent_id}")
