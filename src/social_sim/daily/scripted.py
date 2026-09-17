"""No-network clients for validating the neutral-day harness, not study arms."""

from __future__ import annotations

import json
from datetime import datetime

from social_sim.decision.client import DecisionReply


class ScriptedNormalDayClient:
    """Use only the same compact context a provider would see."""

    def __init__(self) -> None:
        self.call_count = 0

    def start_episode(self) -> None:
        pass

    async def complete(self, system_prompt: str, user_prompt: str) -> DecisionReply:
        self.call_count += 1
        context = json.loads(user_prompt.split("Context:", 1)[1])
        state = context["s"]
        hour = datetime.fromisoformat(state["t"]).hour
        location = state["loc"]
        inventory = state.get("inv", {})
        if hour < 9:
            action, target = ("LEISURE", None) if location == "home" else ("MOVE", "home")
        elif hour < 12:
            action, target = ("WORK", None) if location == "office" else ("MOVE", "office")
        elif hour < 13:
            if location != "restaurant":
                action, target = "MOVE", "restaurant"
            elif inventory.get("meal", 0):
                action, target = "EAT", "meal"
            else:
                action, target = "BUY", "meal"
        elif hour < 17:
            action, target = ("WORK", None) if location == "office" else ("MOVE", "office")
        elif hour < 22:
            action, target = ("LEISURE", None) if location == "home" else ("MOVE", "home")
        else:
            action, target = ("SLEEP", None) if location == "home" else ("MOVE", "home")
        return DecisionReply(json.dumps({"action": action, "target": target}))


class PathologicalBuyAtHomeClient:
    """Always repeat one invalid proposal so the idle detector can be tested."""

    def __init__(self) -> None:
        self.call_count = 0

    def start_episode(self) -> None:
        pass

    async def complete(self, system_prompt: str, user_prompt: str) -> DecisionReply:
        self.call_count += 1
        return DecisionReply('{"action":"BUY","target":"meal"}')
