"""One deliberately plain persona for the neutral-day baseline."""

from __future__ import annotations

from dataclasses import dataclass


NEUTRAL_DAY_GOAL = "live through the day while handling your basic needs and obligations"


@dataclass(frozen=True)
class NeutralPersona:
    name: str = "Alice"
    role: str = "adult"
    occupation: str = "office_worker"
    personality: str = "neutral"
    home: str = "home"
    workplace: str = "office"
    goal: str = NEUTRAL_DAY_GOAL

    def __post_init__(self) -> None:
        for field_name in (
            "name", "role", "occupation", "personality", "home", "workplace", "goal"
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a nonempty string")

    def profile(self) -> dict[str, str]:
        """Return a fresh profile; the context compiler allow-lists its fields."""
        return {
            "name": self.name,
            "role": self.role,
            "occupation": self.occupation,
            "personality": self.personality,
            "home": self.home,
            "workplace": self.workplace,
            "goal": self.goal,
        }
