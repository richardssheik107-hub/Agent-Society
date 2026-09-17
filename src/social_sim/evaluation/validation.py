"""Pure-Python trajectory invariants; no model-based evaluator."""

from __future__ import annotations

from collections.abc import Sequence

from .models import EpisodeResult, StepTrajectory


_ACCEPTED_EVENTS = {
    "MOVE": "MOVED", "BUY": "PURCHASED", "EAT": "ATE",
    "SLEEP": "SLEEP_STARTED", "WORK": "WORK_STARTED",
    "LEISURE": "LEISURE_STARTED",
}


def validate_trajectory(trajectory: EpisodeResult | Sequence[StepTrajectory]) -> bool:
    """Raise ValueError on inconsistent step/world/event history, otherwise return True."""
    if isinstance(trajectory, EpisodeResult):
        steps = trajectory.steps
        episode_id = trajectory.episode_id
        daily = trajectory.scenario_name == "neutral_day"
    elif isinstance(trajectory, Sequence) and not isinstance(trajectory, (str, bytes)):
        steps = tuple(trajectory)
        episode_id = steps[0].episode_id if steps else None
        daily = False
    else:
        raise TypeError("trajectory must be EpisodeResult or a step sequence")

    previous: StepTrajectory | None = None
    event_ids: set[str] = set()
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, StepTrajectory):
            raise TypeError("trajectory contains a non-StepTrajectory value")
        if step.episode_id != episode_id:
            raise ValueError("steps must belong to the same episode")
        if step.step_index != index:
            raise ValueError("step indices must be contiguous and start at 1")
        if previous is not None and step.state_before != previous.state_after and not daily:
            raise ValueError("world continuity violated between adjacent steps")

        proposal_action = step.proposal.get("action")
        intent_action = step.intent.get("action")
        event_action = step.event.get("action")
        if proposal_action != intent_action or intent_action != event_action:
            raise ValueError("proposal, intent, and event actions disagree")
        if step.intent.get("actor_id") != step.event.get("actor_id"):
            raise ValueError("intent and event actor IDs disagree")
        if step.proposal.get("target") != step.intent.get("target"):
            raise ValueError("proposal and intent targets disagree")
        if step.intent.get("target") != step.event.get("target"):
            raise ValueError("intent and event targets disagree")
        if step.event.get("reason_code") != step.rule_reason_code:
            raise ValueError("rule and event reason codes disagree")
        if step.event.get("success") is not step.rule_allowed:
            raise ValueError("rule and event success disagree")

        event_id = step.event.get("event_id")
        if event_id is not None:
            if not isinstance(event_id, str) or not event_id or event_id in event_ids:
                raise ValueError("event IDs must be unique nonempty strings")
            event_ids.add(event_id)

        if step.rule_allowed:
            if proposal_action not in _ACCEPTED_EVENTS:
                raise ValueError("accepted action is not part of the supported action set")
            if not step.effects:
                raise ValueError("accepted action must have an effect")
            if step.event.get("event_type") != _ACCEPTED_EVENTS[proposal_action]:
                raise ValueError("accepted action has the wrong event type")
            if step.rule_reason_code != "ACCEPTED":
                raise ValueError("accepted action must use ACCEPTED reason code")
        else:
            if step.state_before != step.state_after:
                raise ValueError("rejected action must leave world state unchanged")
            if step.effects:
                raise ValueError("rejected action cannot have effects")
            if step.event.get("event_type") != "ACTION_REJECTED":
                raise ValueError("rejected action must emit ACTION_REJECTED")
            if step.rule_reason_code == "ACCEPTED":
                raise ValueError("rejected action cannot use ACCEPTED reason code")
        previous = step

    if isinstance(trajectory, EpisodeResult):
        if trajectory.model_start_state is not None:
            start = steps[0].state_before if steps else trajectory.final_state
            if start != trajectory.model_start_state:
                raise ValueError("first model step does not match model_start_state")
        if trajectory.accepted_actions != sum(step.rule_allowed for step in steps):
            raise ValueError("episode accepted_actions does not match steps")
        if trajectory.rejected_actions != sum(not step.rule_allowed for step in steps):
            raise ValueError("episode rejected_actions does not match steps")
        if trajectory.decision_count < sum(step.decision_call_count for step in steps):
            raise ValueError("episode decision_count is smaller than recorded decisions")
        if trajectory.total_provider_requests < sum(step.provider_request_count for step in steps):
            raise ValueError("episode provider requests are smaller than recorded requests")
        if tuple(step.event for step in steps) != trajectory.events:
            raise ValueError("episode events do not match step events")
        if steps and trajectory.final_state != steps[-1].state_after and not daily:
            raise ValueError("episode final state does not match last step")
    return True
