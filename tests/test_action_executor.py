"""The executor composes deterministic rules, reducer, and one event."""

from datetime import datetime, timezone

from social_sim.actions import ActionIntent
from social_sim.decision import ActionType
from social_sim.events import EventLog, EventType
from social_sim.execution import ActionExecutor
from social_sim.world import PersonWorldState, WorldState
from social_sim.world.state import OfferState


def make_world(*, location: str = "home", meal_count: int = 0) -> WorldState:
    return WorldState(
        time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        people={
            1: PersonWorldState(
                1, location, 100.0, 0.8, inventory={"meal": meal_count}
            )
        },
        venues={"restaurant": {"meal": OfferState("meal", 20.0, 10)}},
    )


def test_move_accepts_and_emits_moved_without_mutating_old_world() -> None:
    old_world = make_world()
    outcome = ActionExecutor().execute(
        old_world,
        ActionIntent(actor_id=1, action=ActionType.MOVE, target="restaurant"),
        event_id="event-000001",
    )
    assert outcome.allowed is True
    assert outcome.reason_code == "ACCEPTED"
    assert len(outcome.effects) == 1
    assert outcome.new_world is not old_world
    assert old_world.get_person(1).location == "home"
    assert outcome.new_world.get_person(1).location == "restaurant"
    assert [event.event_type for event in outcome.events] == [EventType.MOVED]
    assert outcome.events[0].success is True


class FailIfAppliedReducer:
    def apply(self, *_: object) -> WorldState:
        raise AssertionError("rejected execution must not call StateReducer")


def test_rejected_move_skips_reducer_and_returns_same_world() -> None:
    world = make_world()
    outcome = ActionExecutor(reducer=FailIfAppliedReducer()).execute(
        world,
        ActionIntent(actor_id=1, action=ActionType.MOVE, target="moon"),
        event_id="event-000001",
    )
    assert outcome.allowed is False
    assert outcome.reason_code == "UNKNOWN_DESTINATION"
    assert outcome.effects == ()
    assert outcome.new_world is world
    assert outcome.events[0].event_type is EventType.ACTION_REJECTED
    assert outcome.events[0].reason_code == "UNKNOWN_DESTINATION"


def test_buy_at_home_is_rejected_with_one_event_and_no_state_change() -> None:
    world = make_world()
    outcome = ActionExecutor(reducer=FailIfAppliedReducer()).execute(
        world,
        ActionIntent(actor_id=1, action=ActionType.BUY, target="meal"),
        event_id="event-000001",
    )
    assert outcome.allowed is False
    assert outcome.reason_code == "NOT_AT_SELLER"
    assert outcome.new_world is world
    assert outcome.events[0].event_type is EventType.ACTION_REJECTED
    assert outcome.events[0].action is ActionType.BUY
    assert outcome.events[0].reason_code == "NOT_AT_SELLER"


def test_buy_then_eat_emits_events_without_executor_log_mutation() -> None:
    world = make_world(location="restaurant")
    log = EventLog()
    executor = ActionExecutor()
    purchase = executor.execute(
        world,
        ActionIntent(actor_id=1, action=ActionType.BUY, target="meal"),
        event_id=log.next_event_id(),
    )
    assert log.all() == ()
    assert purchase.allowed is True
    assert purchase.new_world.get_person(1).money == 80.0
    assert purchase.new_world.get_person(1).inventory["meal"] == 1
    assert purchase.events[0].event_type is EventType.PURCHASED
    log.append(purchase.events[0])

    meal = executor.execute(
        purchase.new_world,
        ActionIntent(actor_id=1, action=ActionType.EAT, target="meal"),
        event_id=log.next_event_id(),
    )
    assert meal.allowed is True
    assert meal.new_world.get_person(1).inventory["meal"] == 0
    assert meal.new_world.get_person(1).hunger == 0.2
    assert meal.events[0].event_type is EventType.ATE
    log.append(meal.events[0])
    assert [event.event_type for event in log.all()] == [
        EventType.PURCHASED,
        EventType.ATE,
    ]
