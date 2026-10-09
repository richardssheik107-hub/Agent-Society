"""Synthetic state-based engineering driver; no network and no daily schedule."""
from __future__ import annotations

from social_sim.continuity.benchmark import seed_demo
from social_sim.continuity.engine import ContinuityWorld
from social_sim.continuity.models import ObjectDefinition, canonical_json
from social_sim.decision.client import DecisionReply

FIXTURE_SOURCE = "M5_SYNTHETIC_ENGINEERING_FIXTURE_REUSING_Q6_DEMO_V1"
POLICY_SOURCE = "SYNTHETIC_STATE_BASED_COVERAGE_POLICY_V1"


def seed_world(world, config) -> None:
    """Fresh genesis reuses existing synthetic cash/catalog/stock and parameters.

    world.seed is idempotent for exactly this fixture and never reinitializes a
    resumed world. Coverage targets below are test-driver instructions only.
    """
    with ContinuityWorld(":memory:") as template:
        seed_demo(template)
        state = template.store.snapshot()
    objects = [(ObjectDefinition.from_dict({k: v for k, v in obj.items()
                                           if k not in {"stock", "available"}}), obj["stock"])
               for obj in state["objects"]]
    world.seed(state["actors"], objects)


class FakeLongRunPolicy:
    """Choose from current legal state, with explicit synthetic coverage goals.

    Needs, money, location, ownership and persisted media/use counters determine
    each proposal. No mutable random generator or turn index is required, so
    reopening with the same world yields the same next deterministic intent.
    These priorities are synthetic engineering thresholds, not human norms.
    """
    provider_request_count = 0
    provider_count = 0
    mode = "offline"
    source = POLICY_SOURCE

    def __init__(self, world, config, actor_id: int = 1):
        self.world, self.config, self.actor_id = world, config, actor_id
        self.call_count = 0
        self.last_metadata = None

    def choose(self) -> dict:
        world, aid = self.world, self.actor_id
        actor = world.store.actor(aid)
        if world.store.commitment(aid):
            raise ValueError("FAKE_POLICY_REQUIRES_NO_ACTIVE_COMMITMENT")
        game, series = world.store.link(aid, "game_a"), world.store.link(aid, "series_a")
        money, hunger, energy = (actor[k] for k in ("money_cents", "hunger_milli", "energy_milli"))
        proposals = []
        if hunger >= 700:
            proposals.extend([("MEAL", "food_meal"), ("MEAL", "food_bread")])
        if energy <= 240:
            proposals.append(("SLEEP", None) if actor["location"] == "home" else ("TRAVEL", "home"))
        if world.acquire_enabled and not game["quantity"] and money >= 3000:
            proposals.append(("ACQUIRE", "game_a"))
        if game["quantity"] and game["play_minutes"] < 45:
            proposals.append(("PLAY", "game_a"))
        if actor["work_minutes"] == 0 or money < 290_000:
            proposals.append(("WORK", None) if actor["location"] == "office" else ("TRAVEL", "office"))
        if sum(series["offsets"].values()) < 30 + world.minute // 20:
            proposals.append(("WATCH", "series_a"))
        if game["quantity"] and game["play_minutes"] < 45 + world.minute // 30:
            proposals.append(("PLAY", "game_a"))
        # Leisure occurs when current needs and task counters permit it; it is
        # neither a clock jump nor a replacement for a rejected model proposal.
        proposals.extend([("LEISURE", None), ("MEAL", "food_bread"),
                          ("SLEEP", None) if actor["location"] == "home" else ("TRAVEL", "home")])
        for activity, target in proposals:
            check = world.preview_activity(aid, activity, target)
            if check["start_allowed"] and (activity != "MEAL" or check["executable_now"]):
                return {"activity": activity, "target": target}
        raise ValueError("SYNTHETIC_POLICY_NO_LEGAL_OPTION")

    async def complete(self, system_prompt: str, user_prompt: str) -> DecisionReply:
        self.call_count += 1
        return DecisionReply(canonical_json(self.choose()), provider_model=POLICY_SOURCE)


# Compatibility name for callers that describe the driver as an adaptive fake.
AdaptiveFakePolicy = FakeLongRunPolicy
