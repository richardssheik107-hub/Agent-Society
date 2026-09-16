"""Local-small-model-friendly, zero-LLM environment routing.

Observation is deterministic. Future action dispatch must remain deterministic too.
"""

import json
from typing import Any

from agentsociety2.env.router_base import RouterBase

from social_sim.world.env import RuleWorldEnv


class DeterministicRouter(RouterBase):
    """Route the Phase 1B read-only protocol without model calls."""

    _DESCRIPTION = (
        "A minimal deterministic social world. Agents can observe their local "
        "state; environment routing and state access use deterministic Python."
    )

    def __init__(self, env_modules: list[RuleWorldEnv]) -> None:
        if len(env_modules) != 1 or not isinstance(env_modules[0], RuleWorldEnv):
            raise ValueError("Phase 1B requires exactly one RuleWorldEnv")
        super().__init__(env_modules=env_modules)
        self._world_env = env_modules[0]

    async def ask(
        self,
        ctx: dict,
        instruction: str,
        readonly: bool = False,
        template_mode: bool = False,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> tuple[dict, str]:
        """Handle only observation and empty statistics; reject all actions."""
        result_ctx = dict(ctx)
        self._add_current_time_to_ctx(result_ctx)
        agent_id: Any = next(
            (result_ctx[key] for key in ("agent_id", "id", "person_id") if key in result_ctx),
            None,
        )
        trace_token = self._set_trace_context(trace_id, parent_span_id, agent_id)
        self.set_trace_context(trace_id, parent_span_id)
        try:
            if instruction == "<observe>":
                if agent_id is None:
                    raise ValueError("<observe> requires agent_id, id, or person_id in ctx")
                observation = self._world_env.observe_person(int(agent_id))
                return result_ctx, json.dumps(
                    observation, ensure_ascii=False, separators=(",", ":")
                )
            if instruction == "<statistics>":
                return result_ctx, "{}"
            return result_ctx, "Environment action routing is not implemented in Phase 1."
        finally:
            self.clear_trace_context()
            self._reset_trace_context(trace_token)

    async def get_world_description(self) -> str:
        """A fixed orientation that never invokes the base LLM description path."""
        return self._DESCRIPTION
