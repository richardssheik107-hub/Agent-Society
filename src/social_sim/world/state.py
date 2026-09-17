"""Small immutable snapshots of objective people and venue facts."""

from dataclasses import dataclass, field
from datetime import datetime
import math
from types import MappingProxyType
from typing import Iterable, Mapping


DEFAULT_LOCATIONS = ("home", "park", "restaurant")


@dataclass(frozen=True)
class PersonWorldState:
    agent_id: int
    location: str
    money: float
    hunger: float
    inventory: Mapping[str, int] = field(default_factory=dict)
    # ``None`` keeps pre-daily worlds and their serialized observations stable.
    # Daily worlds opt in with a concrete value in [0, 1].
    energy: float | None = None
    activity: str | None = None
    activity_end_time: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.money, bool) or not isinstance(self.money, (int, float)) or not math.isfinite(self.money) or self.money < 0:
            raise ValueError("money must be finite and non-negative")
        if isinstance(self.hunger, bool) or not isinstance(self.hunger, (int, float)) or not math.isfinite(self.hunger) or not 0 <= self.hunger <= 1:
            raise ValueError("hunger must be between 0 and 1")
        if self.energy is not None and (
            isinstance(self.energy, bool)
            or not isinstance(self.energy, (int, float))
            or not math.isfinite(self.energy)
            or not 0 <= self.energy <= 1
        ):
            raise ValueError("energy must be between 0 and 1 when supplied")
        if self.activity is not None and self.activity not in ("SLEEP", "WORK", "LEISURE"):
            raise ValueError("activity must be SLEEP, WORK, LEISURE or None")
        if (self.activity is None) != (self.activity_end_time is None):
            raise ValueError("activity and activity_end_time must be set together")
        if self.activity_end_time is not None:
            if not isinstance(self.activity_end_time, str):
                raise ValueError("activity_end_time must be an ISO datetime string")
            try:
                datetime.fromisoformat(self.activity_end_time)
            except ValueError as exc:
                raise ValueError("activity_end_time must be an ISO datetime string") from exc
        if not isinstance(self.inventory, Mapping):
            raise TypeError("inventory must be a mapping")
        inventory = dict(self.inventory)
        for item_id, quantity in inventory.items():
            if not isinstance(item_id, str) or not item_id.strip():
                raise ValueError("inventory item IDs must be nonempty strings")
            if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 0:
                raise ValueError("inventory quantities must be non-negative integers")
        object.__setattr__(self, "inventory", MappingProxyType(inventory))

    def __reduce__(self) -> tuple:
        """Serialize the immutable snapshot without serializing mappingproxy."""
        return (
            type(self),
            (
                self.agent_id, self.location, self.money, self.hunger,
                dict(self.inventory), self.energy, self.activity, self.activity_end_time,
            ),
        )


@dataclass(frozen=True)
class OfferState:
    """One venue's objective price and remaining stock for an item."""

    item_id: str
    price: float
    stock: int

    def __post_init__(self) -> None:
        if not isinstance(self.item_id, str) or not self.item_id.strip():
            raise ValueError("item_id must be a nonempty string")
        if isinstance(self.price, bool) or not isinstance(self.price, (int, float)) or not math.isfinite(self.price) or self.price < 0:
            raise ValueError("price must be finite and non-negative")
        if isinstance(self.stock, bool) or not isinstance(self.stock, int) or self.stock < 0:
            raise ValueError("stock must be a non-negative integer")


@dataclass(frozen=True, init=False)
class WorldState:
    time: datetime
    _people: tuple[PersonWorldState, ...] = field(repr=False)
    _locations: tuple[str, ...] = field(repr=False)
    _venues: tuple[tuple[str, tuple[OfferState, ...]], ...] = field(repr=False)

    def __init__(
        self,
        time: datetime,
        people: Mapping[int, PersonWorldState],
        locations: Iterable[str] = DEFAULT_LOCATIONS,
        venues: Mapping[str, Mapping[str, OfferState]] | None = None,
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
        if venues is None:
            venues = {}
        if not isinstance(venues, Mapping):
            raise TypeError("venues must be a mapping")
        venue_items: list[tuple[str, tuple[OfferState, ...]]] = []
        for location_id, offers in sorted(venues.items()):
            if location_id not in location_ids:
                raise ValueError(f"venue location is not in world: {location_id!r}")
            if not isinstance(offers, Mapping):
                raise TypeError("venue offers must be a mapping")
            for item_id, offer in offers.items():
                if not isinstance(item_id, str) or not item_id.strip():
                    raise ValueError("offer item IDs must be nonempty strings")
                if not isinstance(offer, OfferState):
                    raise TypeError("venue offers must contain OfferState values")
                if item_id != offer.item_id:
                    raise ValueError("offer key must match item_id")
            venue_items.append((location_id, tuple(offer for _, offer in sorted(offers.items()))))
        object.__setattr__(self, "time", time)
        object.__setattr__(
            self, "_people", tuple(person for _, person in sorted(people.items()))
        )
        object.__setattr__(self, "_locations", tuple(sorted(location_ids)))
        object.__setattr__(self, "_venues", tuple(venue_items))

    @property
    def people(self) -> dict[int, PersonWorldState]:
        """Return a copy; callers cannot change the world's stored people."""
        return {person.agent_id: person for person in self._people}

    @property
    def locations(self) -> tuple[str, ...]:
        """The world's sole source of valid destination IDs."""
        return self._locations

    @property
    def venues(self) -> dict[str, dict[str, OfferState]]:
        """Return independent nested dictionaries; offers themselves are frozen."""
        return {
            location_id: {offer.item_id: offer for offer in offers}
            for location_id, offers in self._venues
        }

    def offers_at(self, location_id: str) -> dict[str, OfferState]:
        """Return only one venue's offers, never the whole world inventory."""
        for venue_id, offers in self._venues:
            if venue_id == location_id:
                return {offer.item_id: offer for offer in offers}
        return {}

    def get_offer(self, location_id: str, item_id: str) -> OfferState | None:
        return self.offers_at(location_id).get(item_id)

    def has_item(self, item_id: str) -> bool:
        return any(offer.item_id == item_id for _, offers in self._venues for offer in offers)

    def get_person(self, agent_id: int) -> PersonWorldState:
        for person in self._people:
            if person.agent_id == agent_id:
                return person
        raise ValueError(f"Unknown agent_id: {agent_id}")
