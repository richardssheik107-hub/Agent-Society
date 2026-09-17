"""The single Phase 3 boundary that turns declarative effects into a new world."""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from social_sim.effects import EatEffect, MoveEffect, PurchaseEffect, StartActivityEffect
from social_sim.effects.models import MEAL_HUNGER_REDUCTION
from social_sim.world import WorldState


class StateConflictError(RuntimeError):
    """An effect no longer matches the state it was evaluated against."""

    reason_code = "STATE_CONFLICT"


class StateReducer:
    """Apply effects on a copy; never mutate the supplied WorldState."""

    def apply(
        self,
        world: WorldState,
        effects: Iterable[MoveEffect | PurchaseEffect | EatEffect | StartActivityEffect],
    ) -> WorldState:
        people = world.people
        venues = world.venues
        changed = False
        for effect in effects:
            if isinstance(effect, MoveEffect):
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
            elif isinstance(effect, PurchaseEffect):
                person = people.get(effect.agent_id)
                offer = venues.get(effect.location_id, {}).get(effect.item_id)
                if person is None or offer is None:
                    raise StateConflictError("STATE_CONFLICT: purchase actor or offer missing")
                inventory_before = person.inventory.get(effect.item_id, 0)
                if (
                    person.location != effect.location_id
                    or person.money != effect.expected_money_before
                    or offer.stock != effect.expected_stock_before
                    or offer.price != effect.unit_price
                    or inventory_before != effect.expected_inventory_before
                    or effect.quantity != 1
                    or offer.stock < effect.quantity
                    or person.money < effect.unit_price * effect.quantity
                ):
                    raise StateConflictError("STATE_CONFLICT: purchase precondition changed")
                inventory_after = dict(person.inventory)
                inventory_after[effect.item_id] = inventory_before + effect.quantity
                people[effect.agent_id] = replace(
                    person,
                    money=round(person.money - effect.unit_price * effect.quantity, 6),
                    inventory=inventory_after,
                )
                venues[effect.location_id][effect.item_id] = replace(
                    offer, stock=offer.stock - effect.quantity
                )
            elif isinstance(effect, EatEffect):
                person = people.get(effect.agent_id)
                if person is None:
                    raise StateConflictError("STATE_CONFLICT: eat actor missing")
                inventory_before = person.inventory.get(effect.item_id, 0)
                expected_after = round(max(0.0, person.hunger - MEAL_HUNGER_REDUCTION), 6)
                if (
                    inventory_before != effect.expected_inventory_before
                    or person.hunger != effect.expected_hunger_before
                    or effect.quantity != 1
                    or inventory_before < effect.quantity
                    or effect.new_hunger != expected_after
                ):
                    raise StateConflictError("STATE_CONFLICT: eat precondition changed")
                inventory_after = dict(person.inventory)
                inventory_after[effect.item_id] = inventory_before - effect.quantity
                people[effect.agent_id] = replace(
                    person, inventory=inventory_after, hunger=effect.new_hunger
                )
            elif isinstance(effect, StartActivityEffect):
                person = people.get(effect.agent_id)
                if person is None:
                    raise StateConflictError("STATE_CONFLICT: activity actor missing")
                if (
                    person.location != effect.expected_location
                    or world.time.isoformat() != effect.expected_time
                    or person.activity is not None
                    or person.activity_end_time is not None
                ):
                    raise StateConflictError("STATE_CONFLICT: activity precondition changed")
                people[effect.agent_id] = replace(
                    person,
                    activity=effect.action.value,
                    activity_end_time=effect.end_time,
                )
            else:
                raise TypeError("Unsupported effect type")
            changed = True
        if not changed:
            return world
        return WorldState(
            time=world.time, people=people, locations=world.locations, venues=venues
        )
