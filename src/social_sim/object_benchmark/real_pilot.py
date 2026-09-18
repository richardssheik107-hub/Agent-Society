"""Optional real-provider Object Set A/B/C pilot.

The runner stores parsed selections and safe numeric metadata, never raw prompts,
raw completions, credentials, or hidden reasoning text.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from social_sim.decision.client import DecisionModelClient

from .benchmark import ObjectChoiceEvaluator, build_choice_prompt, parse_object_choice, summarize_rows
from .catalog import ObjectCatalog, build_scenarios
from .models import ArchitectureArm


@dataclass(frozen=True)
class PilotConfig:
    repetitions: int = 2
    top_k: int = 10
    max_scenarios: int | None = None

    def __post_init__(self) -> None:
        if self.repetitions <= 0 or self.top_k <= 0:
            raise ValueError("repetitions/top_k must be positive")
        if self.max_scenarios is not None and self.max_scenarios <= 0:
            raise ValueError("max_scenarios must be positive")


def pilot_schedule(config: PilotConfig) -> list[tuple[int, object, ArchitectureArm]]:
    scenarios = build_scenarios()
    if config.max_scenarios is not None:
        scenarios = scenarios[: config.max_scenarios]
    arms = tuple(ArchitectureArm)
    schedule: list[tuple[int, object, ArchitectureArm]] = []
    for repetition in range(1, config.repetitions + 1):
        for index, scenario in enumerate(scenarios):
            offset = (index + repetition - 1) % len(arms)
            for step in range(len(arms)):
                schedule.append((repetition, scenario, arms[(offset + step) % len(arms)]))
    return schedule


async def run_real_pilot(
    client: DecisionModelClient,
    catalog: ObjectCatalog,
    config: PilotConfig | None = None,
) -> tuple[list[dict[str, object]], dict[str, dict[str, float | int]]]:
    cfg = config or PilotConfig()
    evaluator = ObjectChoiceEvaluator(catalog, top_k=cfg.top_k)
    rows: list[dict[str, object]] = []
    for case_number, (repetition, scenario, arm) in enumerate(pilot_schedule(cfg), 1):
        candidates = catalog.retrieve(scenario, k=cfg.top_k) if arm is not ArchitectureArm.LLM_ONLY else ()
        system, user = build_choice_prompt(scenario, arm, candidates)
        started = time.perf_counter()
        try:
            reply = await client.complete(system, user)
            elapsed = time.perf_counter() - started
            choice = parse_object_choice(reply.raw_text)
            row = evaluator.evaluate(scenario, arm, choice)
            row.update(
                case_number=case_number,
                repetition=repetition,
                provider_status="SUCCESS",
                latency_seconds=round(elapsed, 6),
                input_tokens=reply.input_tokens,
                output_tokens=reply.output_tokens,
                reasoning_tokens=reply.reasoning_tokens,
                provider_model=reply.provider_model,
                prompt_chars=len(system) + len(user),
                raw_output_chars=len(reply.raw_text),
            )
        except Exception as exc:  # provider/parse taxonomy is intentionally compact here
            row = {
                "case_number": case_number,
                "scenario_id": scenario.scenario_id,
                "domain": scenario.domain.value,
                "arm": arm.value,
                "repetition": repetition,
                "provider_status": type(exc).__name__,
                "latency_seconds": round(time.perf_counter() - started, 6),
            }
        rows.append(row)
    successful = [row for row in rows if row.get("provider_status") == "SUCCESS"]
    return rows, summarize_rows(successful) if successful else {}
