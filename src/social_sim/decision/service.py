"""One compact decision call; a proposal is never applied to the world."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Mapping, Sequence

from social_sim.context import C3Recent3Policy, ContextCompiler, ContextPolicy
from social_sim.world.observation import LocalObservation

from .client import DecisionModelClient
from .models import ActionType, DecisionProposal
from .parser import DecisionParseError, DecisionParser
from .prompt import MAX_CONTEXT_CHARS, build_decision_prompt


@dataclass(frozen=True)
class DecisionResult:
    proposal: DecisionProposal
    context: str
    system_prompt: str
    user_prompt: str
    context_chars: int
    prompt_chars: int
    raw_output_chars: int
    latency_seconds: float
    input_tokens: int | None
    output_tokens: int | None
    reasoning_tokens: int | None
    provider_model: str | None
    provider_request_count: int


class CompactDecisionService:
    """Compile local facts, make exactly one model call, and parse its proposal."""

    def __init__(
        self,
        client: DecisionModelClient,
        compiler: ContextCompiler | None = None,
        parser: DecisionParser | None = None,
        context_policy: ContextPolicy | None = None,
    ) -> None:
        self.client = client
        self.compiler = compiler or ContextCompiler(max_chars=MAX_CONTEXT_CHARS)
        self.parser = parser or DecisionParser()
        # Legacy direct callers pass an already bounded recent-three list.
        # An explicitly injected policy instead receives the complete log and
        # performs its own selection (needed to rescue a buried rejection).
        self.accepts_full_event_history = context_policy is not None
        self.context_policy = context_policy or C3Recent3Policy()
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
        daily_mode: bool = False,
        work_window: str | None = None,
        behavior_hints: Sequence[str] | None = None,
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

        if isinstance(recent_events, (str, bytes)):
            raise TypeError("recent_events must be a sequence of compact strings")
        history = tuple(recent_events) if recent_events is not None else ()
        if not self.accepts_full_event_history and len(history) > ContextCompiler.MAX_EVENTS:
            raise ValueError("recent_events exceeds maximum item count")
        goal = profile.get("goal")
        selected_events = self.context_policy.select_events(
            history, observation, goal if isinstance(goal, str) else ""
        )

        context = self.compiler.compile(
            profile,
            observation,
            available_actions=[action.value for action in actions],
            available_targets=targets,
            events=selected_events,
            daily_mode=daily_mode,
            work_window=work_window,
            behavior_hints=behavior_hints,
        )
        prompt = build_decision_prompt(context, daily_mode=daily_mode)
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
            context=context,
            system_prompt=prompt.system,
            user_prompt=prompt.user,
            context_chars=prompt.context_chars,
            prompt_chars=prompt.prompt_chars,
            raw_output_chars=len(reply.raw_text),
            latency_seconds=latency,
            input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens,
            reasoning_tokens=reply.reasoning_tokens,
            provider_model=reply.provider_model,
            provider_request_count=reply.provider_request_count,
        )
