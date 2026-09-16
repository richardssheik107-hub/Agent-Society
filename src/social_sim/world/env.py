"""AgentSociety adapter exposing the Phase 1 world only for observation."""

from datetime import datetime

from agentsociety2.env import EnvBase, tool

from .observation import ObservationBuilder
from .state import WorldState


class RuleWorldEnv(EnvBase):
    """Read-only observations of the deterministic world state."""

    def __init__(self, world_state: WorldState) -> None:
        super().__init__()
        self.world_state = world_state
        self.observation_builder = ObservationBuilder(world_state)

    @classmethod
    def init_description(cls) -> str:
        return "RuleWorldEnv(world_state: WorldState): read-only person observations."

    @tool(readonly=True, kind="observe")
    def observe_person(self, agent_id: int) -> dict:
        """Return objective location, money and hunger for an agent; unknown IDs return an error."""
        try:
            return self.observation_builder.build(agent_id).to_dict()
        except ValueError:
            return {"agent_id": agent_id, "error": "unknown_agent_id"}

    async def step(self, tick: int, t: datetime) -> None:
        """Advance only EnvBase's clock; the Phase 1 WorldState stays fixed."""
        self.t = t
