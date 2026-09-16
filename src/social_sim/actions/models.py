"""Internal action intent, deliberately separate from the LLM-facing proposal."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from social_sim.decision.models import ActionType, DecisionProposal


@dataclass(frozen=True)
class ActionIntent:
    """An actor's requested action; only rules can decide whether it succeeds."""

    actor_id: int
    action: ActionType
    target: str | None = None
    params: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.actor_id, int) or isinstance(self.actor_id, bool):
            raise ValueError("actor_id must be an integer")
        if isinstance(self.action, str):
            try:
                object.__setattr__(self, "action", ActionType(self.action))
            except ValueError as exc:
                raise ValueError(f"Unknown action: {self.action!r}") from exc
        elif not isinstance(self.action, ActionType):
            raise ValueError(f"Unknown action: {self.action!r}")
        if self.target is not None and not isinstance(self.target, str):
            raise ValueError("target must be a string or None")
        if not isinstance(self.params, Mapping):
            raise ValueError("params must be a mapping")
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))


def proposal_to_intent(actor_id: int, proposal: DecisionProposal) -> ActionIntent:
    """Attach Python-owned actor identity without asking the model for it."""

    if not isinstance(proposal, DecisionProposal):
        raise TypeError("proposal must be a DecisionProposal")
    return ActionIntent(
        actor_id=actor_id,
        action=proposal.action,
        target=proposal.target,
    )
