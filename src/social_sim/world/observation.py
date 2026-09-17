"""Select only an agent's local facts from the objective world."""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from .state import WorldState


@dataclass(frozen=True)
class LocalObservation:
    agent_id: int
    time: str
    location: str
    money: float
    hunger: float
    inventory: Mapping[str, int] = field(default_factory=dict)
    offers: Mapping[str, Mapping[str, float | bool]] = field(default_factory=dict)
    energy: float | None = None
    activity: str | None = None
    activity_end_time: str | None = None

    def __post_init__(self) -> None:
        # A local observation is a snapshot, not a live view of the world.
        object.__setattr__(self, "inventory", MappingProxyType(dict(self.inventory)))
        object.__setattr__(
            self,
            "offers",
            MappingProxyType({
                item_id: MappingProxyType(dict(offer))
                for item_id, offer in self.offers.items()
            }),
        )

    def __reduce__(self) -> tuple:
        """Keep local snapshots serializable across runtime process boundaries."""
        return (
            type(self),
            (
                self.agent_id, self.time, self.location, self.money, self.hunger,
                dict(self.inventory),
                {item_id: dict(offer) for item_id, offer in self.offers.items()},
                self.energy, self.activity, self.activity_end_time,
            ),
        )

    def to_dict(self) -> dict:
        result = {
            "agent_id": self.agent_id,
            "time": self.time,
            "location": self.location,
            "money": self.money,
            "hunger": self.hunger,
        }
        if self.inventory:
            result["inventory"] = dict(self.inventory)
        if self.offers:
            result["offers"] = {
                item_id: dict(offer) for item_id, offer in self.offers.items()
            }
        if self.energy is not None:
            result["energy"] = self.energy
            result["activity"] = self.activity
            result["activity_end_time"] = self.activity_end_time
        return result


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
            inventory=person.inventory,
            energy=person.energy,
            activity=person.activity,
            activity_end_time=person.activity_end_time,
            offers={
                item_id: {"price": offer.price, "available": offer.stock > 0}
                for item_id, offer in self._world_state.offers_at(person.location).items()
            },
        )
