"""Structured snapshots and safe trajectory serialization."""

from datetime import datetime, timezone
import json

import pytest

from social_sim.actions import proposal_to_intent
from social_sim.decision import ActionType, DecisionProposal
from social_sim.effects.models import MoveEffect
from social_sim.evaluation.models import (
    StepTrajectory,
    TRAJECTORY_SCHEMA_VERSION,
    effect_snapshot,
    intent_snapshot,
    observation_snapshot,
    proposal_snapshot,
    world_snapshot,
)
from social_sim.world import ObservationBuilder, OfferState, PersonWorldState, WorldState


def _world() -> WorldState:
    return WorldState(
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        {1: PersonWorldState(1, "home", 100.0, 0.8, {})},
        venues={"restaurant": {"meal": OfferState("meal", 20.0, 10)}},
    )


def _step() -> StepTrajectory:
    before = world_snapshot(_world())
    after = json.loads(json.dumps(before))
    after["people"]["1"]["location"] = "restaurant"
    proposal = DecisionProposal(ActionType.MOVE, "restaurant")
    return StepTrajectory(
        episode_id="lunch-000001",
        step_index=1,
        state_before=before,
        observation=observation_snapshot(ObservationBuilder(_world()).build(1)),
        context='{"s":{"loc":"home"}}',
        proposal=proposal_snapshot(proposal),
        intent=intent_snapshot(proposal_to_intent(1, proposal)),
        rule_allowed=True,
        rule_reason_code="ACCEPTED",
        effects=(effect_snapshot(MoveEffect(1, "home", "restaurant")),),
        event={"event_id": "event-1", "event_type": "MOVED", "actor_id": 1,
               "action": "MOVE", "target": "restaurant", "success": True,
               "reason_code": "ACCEPTED"},
        state_after=after,
        decision_call_count=1,
        provider_request_count=1,
        context_chars=20,
        prompt_chars=120,
        decision_latency_seconds=0.25,
        input_tokens=10,
        output_tokens=5,
        reasoning_tokens=2,
        visible_content_chars=39,
        provider_model="fixture",
    )


def test_world_and_observation_are_distinct_json_snapshots() -> None:
    world = _world()
    objective = world_snapshot(world)
    observed = observation_snapshot(ObservationBuilder(world).build(1))
    assert objective["people"]["1"]["location"] == "home"
    assert objective["venues"]["restaurant"]["meal"]["stock"] == 10
    assert "venues" not in observed
    assert observed["offers"] == {}
    json.dumps(objective, allow_nan=False)
    json.dumps(observed, allow_nan=False)


def test_step_is_json_friendly_and_detached_from_input() -> None:
    step = _step()
    payload = step.to_dict()
    assert TRAJECTORY_SCHEMA_VERSION == "0.1"
    assert payload["effects"][0] == {
        "type": "MOVE", "agent_id": 1, "from": "home", "to": "restaurant"
    }
    assert "prompt" not in payload
    assert "reasoning_content" not in json.dumps(payload)
    payload["state_before"]["people"]["1"]["location"] = "park"
    assert step.state_before["people"]["1"]["location"] == "home"


def test_secret_text_is_redacted_and_hidden_reasoning_key_rejected() -> None:
    step = _step()
    secret = "sk-12345678901234567890"
    changed = dict(step.state_before)
    changed["note"] = f"Bearer {secret}"
    updated = StepTrajectory(**{**step.__dict__, "state_before": changed})
    assert secret not in json.dumps(updated.to_dict())
    with pytest.raises(ValueError, match="sensitive field"):
        StepTrajectory(**{**step.__dict__, "proposal": {"action": "MOVE", "reasoning_content": "private"}})
