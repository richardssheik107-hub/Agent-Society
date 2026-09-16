"""In-memory append-only event log with predictable IDs."""

from __future__ import annotations

from social_sim.events.models import DomainEvent


class EventLog:
    def __init__(self) -> None:
        self._events: list[DomainEvent] = []
        self._event_ids: set[str] = set()
        self._last_id_number = 0

    def next_event_id(self) -> str:
        """Reserve the next deterministic ID, independent of wall-clock time."""

        self._last_id_number += 1
        return f"event-{self._last_id_number:06d}"

    def append(self, event: DomainEvent) -> None:
        if not isinstance(event, DomainEvent):
            raise TypeError("event must be a DomainEvent")
        if event.event_id in self._event_ids:
            raise ValueError(f"duplicate event_id: {event.event_id}")
        self._events.append(event)
        self._event_ids.add(event.event_id)
        if event.event_id.startswith("event-") and event.event_id[6:].isdigit():
            self._last_id_number = max(
                self._last_id_number, int(event.event_id[6:])
            )

    def recent_for_agent(
        self, agent_id: int, limit: int = 3
    ) -> tuple[DomainEvent, ...]:
        if not isinstance(agent_id, int) or isinstance(agent_id, bool):
            raise ValueError("agent_id must be an integer")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
            raise ValueError("limit must be a nonnegative integer")
        if limit == 0:
            return ()
        return tuple(event for event in self._events if event.actor_id == agent_id)[
            -limit:
        ]

    def all(self) -> tuple[DomainEvent, ...]:
        return tuple(self._events)
