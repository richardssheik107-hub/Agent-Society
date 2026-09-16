"""Objective continuity and event consistency checks."""

from dataclasses import replace

import pytest

from social_sim.evaluation.validation import validate_trajectory
from test_trajectory_models import _step


def _rejection_step():
    first = _step()
    before = first.state_after
    return replace(
        first,
        step_index=2,
        state_before=before,
        state_after=before,
        proposal={"action": "BUY", "target": "meal"},
        intent={"actor_id": 1, "action": "BUY", "target": "meal", "params": {"quantity": 1}},
        rule_allowed=False,
        rule_reason_code="OUT_OF_STOCK",
        effects=(),
        event={"event_id": "event-2", "event_type": "ACTION_REJECTED", "actor_id": 1,
               "action": "BUY", "target": "meal", "success": False,
               "reason_code": "OUT_OF_STOCK"},
    )


def test_valid_rejected_step_preserves_world_continuity() -> None:
    assert validate_trajectory((_step(), _rejection_step()))


def test_step_indices_and_world_continuity_are_checked() -> None:
    first = _step()
    second = _rejection_step()
    with pytest.raises(ValueError, match="contiguous"):
        validate_trajectory((first, replace(second, step_index=3)))
    with pytest.raises(ValueError, match="world continuity"):
        validate_trajectory((first, replace(second, state_before=first.state_before)))


def test_rejected_action_must_leave_world_unchanged() -> None:
    rejected = _rejection_step()
    with pytest.raises(ValueError, match="unchanged"):
        validate_trajectory((_step(), replace(rejected, state_after=_step().state_before)))
    with pytest.raises(ValueError, match="cannot have effects"):
        validate_trajectory((_step(), replace(rejected, effects=_step().effects)))


def test_accepted_action_requires_effect_and_matching_event() -> None:
    first = _step()
    with pytest.raises(ValueError, match="must have an effect"):
        validate_trajectory((replace(first, effects=()),))
    mismatched_event = {**first.event, "event_type": "PURCHASED"}
    with pytest.raises(ValueError, match="wrong event type"):
        validate_trajectory((replace(first, event=mismatched_event),))


def test_rejected_action_requires_action_rejected_event() -> None:
    rejected = _rejection_step()
    with pytest.raises(ValueError, match="ACTION_REJECTED"):
        validate_trajectory((_step(), replace(rejected, event={**rejected.event, "event_type": "MOVED"})))
