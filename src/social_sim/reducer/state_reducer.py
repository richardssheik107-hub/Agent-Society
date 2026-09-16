"""The single Phase 3 boundary that turns declarative effects into a new world."""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from social_sim.effects import MoveEffect
from social_sim.world import WorldState


class StateConflictError(RuntimeError):
    """An effect no longer matches the state it was evaluated against."""

    reason_code = "STATE_CONFLICT"


class StateReducer:
    """Apply effects on a copy; never mutate the supplied WorldState."""

    def apply(self, world: WorldState, effects: Iterable[MoveEffect]) -> WorldState:
        people = world.people
        changed = False
        for effect in effects:
            if not isinstance(effect, MoveEffect):
                raise TypeError("Unsupported effect type")
            person = people.get(effect.agent_id)
            if person is None:
                raise StateConflictError("STATE_CONFLICT: effect actor not found")
            if person.location != effect.from_location:
                raise StateConflictError("STATE_CONFLICT: source location changed")
            if effect.to_location not in world.locations:
                raise StateConflictError("STATE_CONFLICT: destination is not in world")
            if effect.to_location == person.location:
                raise StateConflictError("STATE_CONFLICT: destination equals current location")
            people[effect.agent_id] = replace(person, location=effect.to_location)
            changed = True
        if not changed:
            return world
        return WorldState(time=world.time, people=people, locations=world.locations)
