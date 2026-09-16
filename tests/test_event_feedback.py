"""Append-only events are deterministic, compact, and agent-scoped."""

import pytest

from social_sim.decision import ActionType
from social_sim.events import DomainEvent, EventLog, EventType


def make_event(
    event_id: str,
    actor_id: int,
    event_type: EventType = EventType.MOVED,
) -> DomainEvent:
    return DomainEvent(
        event_id=event_id,
        actor_id=actor_id,
        event_type=event_type,
        action=ActionType.MOVE,
        target="restaurant",
        success=True,
        reason_code="ACCEPTED",
    )


def test_event_log_ids_are_monotonic_and_predictable() -> None:
    log = EventLog()
    assert log.next_event_id() == "event-000001"
    assert log.next_event_id() == "event-000002"
    log.append(make_event("event-000002", 1))
    assert log.next_event_id() == "event-000003"


def test_recent_for_agent_is_bounded_and_chronological() -> None:
    log = EventLog()
    for index in range(1, 6):
        log.append(make_event(log.next_event_id(), 1))
        log.append(make_event(log.next_event_id(), 2))
    assert [event.event_id for event in log.recent_for_agent(1)] == [
        "event-000005",
        "event-000007",
        "event-000009",
    ]
    assert len(log.all()) == 10
    assert log.recent_for_agent(1, limit=0) == ()


def test_event_log_rejects_duplicate_and_exposes_immutable_snapshot() -> None:
    log = EventLog()
    event = make_event(log.next_event_id(), 1)
    log.append(event)
    snapshot = log.all()
    with pytest.raises(ValueError, match="duplicate event_id"):
        log.append(event)
    assert snapshot == (event,)
    assert isinstance(snapshot, tuple)
    with pytest.raises(ValueError, match="limit"):
        log.recent_for_agent(1, limit=-1)


def test_domain_event_rejects_inconsistent_success_flag() -> None:
    with pytest.raises(ValueError, match="disagree"):
        DomainEvent(
            event_id="event-000001",
            actor_id=1,
            event_type=EventType.ACTION_REJECTED,
            action=ActionType.BUY,
            target="meal",
            success=True,
            reason_code="NOT_AT_SELLER",
        )

    with pytest.raises(ValueError, match="reason_code disagree"):
        DomainEvent(
            event_id="event-000001",
            actor_id=1,
            event_type=EventType.MOVED,
            action=ActionType.MOVE,
            target="restaurant",
            success=True,
            reason_code="NOT_AT_SELLER",
        )


def test_compact_feedback_omits_event_metadata() -> None:
    moved = make_event("event-000001", 1)
    rejected = DomainEvent(
        event_id="event-000002",
        actor_id=1,
        event_type=EventType.ACTION_REJECTED,
        action=ActionType.BUY,
        target="meal",
        success=False,
        reason_code="NOT_AT_SELLER",
    )
    assert moved.compact() == "MOVED:restaurant"
    assert rejected.compact() == "ACTION_REJECTED:NOT_AT_SELLER"
