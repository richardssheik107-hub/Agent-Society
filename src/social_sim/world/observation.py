"""Select only an agent's local facts from the objective world."""

from dataclasses import dataclass

from .state import WorldState


@dataclass(frozen=True)
class LocalObservation:
    agent_id: int
    time: str
    location: str
    money: float
    hunger: float

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "time": self.time,
            "location": self.location,
            "money": self.money,
            "hunger": self.hunger,
        }


class ObservationBuilder:
    """Build a bounded local projection; unknown IDs fail explicitly."""

    def __init__(self, world_state: WorldState) -> None:
        self._world_state = world_state

    def build(self, agent_id: int) -> LocalObservation:
        person = self._world_state.get_person(agent_id)
        return LocalObservation(
            agent_id=person.agent_id,
            time=self._world_state.time.isoformat(),
            location=person.location,
            money=person.money,
            hunger=person.hunger,
        )
