"""One compact decision call; a proposal is never applied to the world."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Mapping, Sequence

from social_sim.context import ContextCompiler
from social_sim.world.observation import LocalObservation

from .client import DecisionModelClient
from .models import ActionType, DecisionProposal
from .parser import DecisionParseError, DecisionParser
from .prompt import MAX_CONTEXT_CHARS, build_decision_prompt


@dataclass(frozen=True)
class DecisionResult:
    proposal: DecisionProposal
    context_chars: int
    prompt_chars: int
    raw_output_chars: int
    latency_seconds: float
    input_tokens: int | None
    output_tokens: int | None


class CompactDecisionService:
    """Compile local facts, make exactly one model call, and parse its proposal."""

    def __init__(
        self,
        client: DecisionModelClient,
        compiler: ContextCompiler | None = None,
        parser: DecisionParser | None = None,
    ) -> None:
        self.client = client
        self.compiler = compiler or ContextCompiler(max_chars=MAX_CONTEXT_CHARS)
        self.parser = parser or DecisionParser()
        self.decision_call_count = 0

    async def decide(
        self,
        profile: Mapping[str, object],
        observation: LocalObservation,
        *,
        available_actions: Sequence[ActionType | str] = (
            ActionType.WAIT,
            ActionType.REST,
            ActionType.MOVE,
        ),
        available_targets: Sequence[str] = (),
        recent_events: Sequence[str] | None = None,
    ) -> DecisionResult:
        actions = tuple(ActionType(action) for action in available_actions)
        if not actions or len(set(actions)) != len(actions):
            raise ValueError("available_actions must be nonempty and unique")
        if isinstance(available_targets, (str, bytes)):
            raise TypeError("available_targets must be a sequence of target IDs")
        targets = tuple(available_targets)
        if any(
            not isinstance(target, str)
            or not target.strip()
            or len(target) > ContextCompiler.MAX_ACTION_STRING_CHARS
            for target in targets
        ):
            raise ValueError("available_targets must contain short nonempty IDs")
        if len(set(targets)) != len(targets):
            raise ValueError("available_targets must be unique")

        context = self.compiler.compile(
            profile,
            observation,
            available_actions=[action.value for action in actions],
            available_targets=targets,
            events=recent_events,
        )
        prompt = build_decision_prompt(context)
        self.decision_call_count += 1
        start = time.perf_counter()
        reply = await self.client.complete(prompt.system, prompt.user)
        latency = time.perf_counter() - start
        proposal = self.parser.parse(reply.raw_text)
        if proposal.action not in actions:
            raise DecisionParseError("Proposed action is not currently available")
        if proposal.action in (ActionType.MOVE, ActionType.BUY, ActionType.EAT):
            if proposal.target not in targets:
                raise DecisionParseError(
                    f"{proposal.action.value} target is not currently available"
                )
        return DecisionResult(
            proposal=proposal,
            context_chars=prompt.context_chars,
            prompt_chars=prompt.prompt_chars,
            raw_output_chars=len(reply.raw_text),
            latency_seconds=latency,
            input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens,
        )
