"""Bounded toy priors used only to exercise the behavior-support interface.

These are hand-written harness inputs, not a behavior corpus or empirical norms.
No external retrieval, model call, or time-script is performed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from social_sim.world.observation import LocalObservation


TOY_UNCALIBRATED_PRIORS = "TOY_UNCALIBRATED_PRIORS"


class SupportCondition(str, Enum):
    B0_NONE = "B0_NONE"
    B1_TINY = "B1_TINY"
    B3_SMALL = "B3_SMALL"


@dataclass(frozen=True)
class BehaviorSupportPolicy:
    """Select at most three short, generic priors from a fixed local collection."""

    condition: SupportCondition = SupportCondition.B0_NONE

    def __post_init__(self) -> None:
        object.__setattr__(self, "condition", SupportCondition(self.condition))

    @property
    def source_label(self) -> str:
        return TOY_UNCALIBRATED_PRIORS

    @property
    def max_hints(self) -> int:
        return {
            SupportCondition.B0_NONE: 0,
            SupportCondition.B1_TINY: 1,
            SupportCondition.B3_SMALL: 3,
        }[self.condition]

    def select_hints(
        self, observation: LocalObservation, *, work_due: bool = False
    ) -> tuple[str, ...]:
        if not isinstance(observation, LocalObservation):
            raise TypeError("observation must be a LocalObservation")
        if not isinstance(work_due, bool):
            raise TypeError("work_due must be a boolean")
        if self.max_hints == 0:
            return ()

        # Priority changes with local needs. The hints contain no location rule,
        # specific clock time, ordered daily script, or claimed corpus statistic.
        ranked: list[str] = []
        if observation.hunger >= 0.7:
            ranked.append("Meals can address hunger.")
        energy = getattr(observation, "energy", None)
        if energy is not None and energy <= 0.3:
            ranked.append("Rest can address low energy.")
        if work_due:
            ranked.append("People often attend to work obligations.")
        ranked.extend((
            "People balance basic needs and obligations.",
            "Discretionary activity can fill free time.",
            "Rest is an ordinary part of daily life.",
        ))
        return tuple(ranked[: self.max_hints])
