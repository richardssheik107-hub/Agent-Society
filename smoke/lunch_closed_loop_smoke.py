"""Network-free MOVE -> BUY -> EAT acceptance of the complete feedback loop."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from social_sim.closed_loop import ClosedLoopStep, LunchScenarioRunner
from social_sim.decision import CompactDecisionService
from social_sim.decision.client import DecisionReply
from social_sim.events import EventLog, EventType
from social_sim.world import OfferState, PersonWorldState, WorldState


class ScriptedDecisionClient:
    """Three fixed completions for deterministic acceptance, not production policy."""

    def __init__(self) -> None:
        self._replies = (
            '{"action":"MOVE","target":"restaurant"}',
            '{"action":"BUY","target":"meal"}',
            '{"action":"EAT","target":"meal"}',
        )
        self.call_count = 0

    async def complete(self, system_prompt: str, user_prompt: str) -> DecisionReply:
        raw_text = self._replies[self.call_count]
        self.call_count += 1
        return DecisionReply(raw_text)


async def main() -> None:
    world0 = WorldState(
        time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        people={1: PersonWorldState(1, "home", 100.0, 0.8)},
        venues={"restaurant": {"meal": OfferState("meal", 20.0, 10)}},
    )
    assert world0.get_person(1).inventory.get("meal", 0) == 0
    assert world0.get_offer("restaurant", "meal").stock == 10
    print("LUNCH_WORLD_INIT_OK")

    client = ScriptedDecisionClient()
    service = CompactDecisionService(client)
    event_log = EventLog()
    runner = LunchScenarioRunner(ClosedLoopStep(service, event_log), max_decisions=5)
    result = await runner.run(world0, 1, {"name": "Alice"})
    assert len(result.steps) == 3
    world1, world2, world3 = (step.world_after for step in result.steps)
    assert (world0.get_person(1).location, world0.get_person(1).money, world0.get_person(1).hunger) == (
        "home", 100.0, 0.8
    )
    assert (world1.get_person(1).location, world1.get_person(1).money, world1.get_person(1).hunger) == (
        "restaurant", 100.0, 0.8
    )
    assert world1.get_offer("restaurant", "meal").stock == 10
    assert (world2.get_person(1).location, world2.get_person(1).money, world2.get_person(1).hunger) == (
        "restaurant", 80.0, 0.8
    )
    assert world2.get_person(1).inventory["meal"] == 1
    assert world2.get_offer("restaurant", "meal").stock == 9
    assert (world3.get_person(1).location, world3.get_person(1).money, world3.get_person(1).hunger) == (
        "restaurant", 80.0, 0.2
    )
    assert world3.get_person(1).inventory["meal"] == 0
    assert world3.get_offer("restaurant", "meal").stock == 9

    expected_actions = ("MOVE", "BUY", "EAT")
    expected_targets = ("restaurant", "meal", "meal")
    expected_events = (EventType.MOVED, EventType.PURCHASED, EventType.ATE)
    for index, step in enumerate(result.steps):
        assert step.proposal.action.value == expected_actions[index]
        assert step.proposal.target == expected_targets[index]
        assert step.outcome.allowed
        assert step.outcome.reason_code == "ACCEPTED"
        assert step.outcome.events[0].event_type is expected_events[index]
        assert step.context_chars < 1000
        assert step.prompt_chars < 1500
        print(f"STEP_{index + 1}:")
        print(f"PROPOSAL={step.proposal.action.value}:{step.proposal.target}")
        print(f"RULE={step.outcome.reason_code}")
        print(f"EVENT={step.outcome.events[0].event_type.value}")
        if index == 0:
            print(f"LOCATION={world1.get_person(1).location}")
        elif index == 1:
            print(f"MONEY={world2.get_person(1).money}")
            print(f"MEAL_INVENTORY={world2.get_person(1).inventory['meal']}")
            print(f"RESTAURANT_STOCK={world2.get_offer('restaurant', 'meal').stock}")
        else:
            print(f"HUNGER={world3.get_person(1).hunger}")
            print(f"MEAL_INVENTORY={world3.get_person(1).inventory['meal']}")

    final = result.final_observation
    assert final.location == "restaurant"
    assert final.money == 80.0
    assert final.hunger == 0.2
    assert final.inventory["meal"] == 0
    print("FINAL_OBSERVATION_OK")
    assert [event.event_type for event in result.events] == list(expected_events)
    assert len(event_log.all()) == 3
    print("EVENT_COUNT=3")
    assert client.call_count == service.decision_call_count == 3
    print("DECISION_CALLS=3")
    print("CONTEXT_CHARS=" + ",".join(str(step.context_chars) for step in result.steps))
    print("ENV_LLM_CALLS=0")
    print("RULE_LLM_CALLS=0")
    print("REDUCER_LLM_CALLS=0")
    print("EVENT_LLM_CALLS=0")
    print("WORLD_LOOP_CLOSED")
    print("LUNCH_CLOSED_LOOP_OK")


if __name__ == "__main__":
    asyncio.run(main())
