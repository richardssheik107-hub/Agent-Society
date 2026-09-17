"""Fixed, interleaved Phase 8A context-ablation schedule and episode execution."""

from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from social_sim.context import (
    C0StatePolicy,
    C1LastPolicy,
    C3Recent3Policy,
    CRRelevantPolicy,
    ContextCompiler,
    ContextPolicy,
)
from social_sim.decision.client import DecisionModelClient, OpenAICompatibleDecisionClient
from social_sim.decision.prompt import (
    MAX_CONTEXT_CHARS,
    MAX_PROMPT_CHARS,
    SYSTEM_INSTRUCTION,
    USER_INSTRUCTION,
    build_decision_prompt,
)

from .ablation_scenarios import SCENARIO_VARIANTS, ScenarioVariant, prepare_ablation_scenario
from .models import EpisodeResult, TerminationReason, world_snapshot
from .runner import EpisodeRunner, LunchBenchmarkScenario, lunch_initial_world


REPETITIONS_PER_CELL = 2
MAX_REAL_EPISODES = 32
MAX_REAL_PROVIDER_REQUESTS = 160
POLICY_TYPES = (C0StatePolicy, C1LastPolicy, C3Recent3Policy, CRRelevantPolicy)
POLICY_NAMES = tuple(policy_type.name for policy_type in POLICY_TYPES)
POLICY_FACTORIES: dict[str, type[ContextPolicy]] = {
    policy_type.name: policy_type for policy_type in POLICY_TYPES
}


@dataclass(frozen=True)
class ScheduleEntry:
    episode_index: int
    repetition: int
    scenario_variant: ScenarioVariant
    context_policy_name: str

    def to_dict(self) -> dict[str, object]:
        return {
            "episode_index": self.episode_index,
            "repetition": self.repetition,
            "scenario_variant": self.scenario_variant.value,
            "context_policy_name": self.context_policy_name,
        }


def build_interleaved_schedule() -> tuple[ScheduleEntry, ...]:
    """Two balanced rounds; never finish an entire policy before the next."""
    schedule: list[ScheduleEntry] = []
    for repetition in (1, 2):
        for scenario_index, variant in enumerate(SCENARIO_VARIANTS):
            rotation = POLICY_NAMES[scenario_index:] + POLICY_NAMES[:scenario_index]
            order = rotation if repetition == 1 else tuple(reversed(rotation))
            for policy_name in order:
                schedule.append(
                    ScheduleEntry(len(schedule) + 1, repetition, variant, policy_name)
                )
    assert len(schedule) == MAX_REAL_EPISODES
    return tuple(schedule)


def _source_sha256(value: object) -> str:
    path = Path(inspect.getfile(value))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_experiment_config(
    *,
    provider_alias: str,
    decision_client_type: str,
    schedule: Sequence[ScheduleEntry] | None = None,
) -> dict[str, object]:
    """Return a secret-free canonical config with a hash fixed before any run."""
    if not provider_alias or not decision_client_type:
        raise ValueError("provider_alias and decision_client_type are required")
    chosen_schedule = tuple(schedule or build_interleaved_schedule())
    if len(chosen_schedule) != MAX_REAL_EPISODES:
        raise ValueError("Phase 8A schedule must contain exactly 32 episodes")
    scenario = LunchBenchmarkScenario()
    canonical: dict[str, object] = {
        "experiment_type": "context_ablation",
        "scenario_family": "lunch",
        "goal": scenario.profile["goal"],
        "model_start_state": world_snapshot(lunch_initial_world()),
        "max_decisions": scenario.max_decisions,
        "available_actions": [action.value for action in scenario.available_actions],
        "target_candidates": list(scenario.target_candidates),
        "policies": list(POLICY_NAMES),
        "scenarios": [variant.value for variant in SCENARIO_VARIANTS],
        "preludes": {
            variant.value: {
                "events": [event["event_type"] + ":" + (
                    str(event["reason_code"]) if not event["success"]
                    else str(event["target"])
                ) for event in prepare_ablation_scenario(variant).prelude_events],
                "action_count": prepare_ablation_scenario(variant).prelude_action_count,
            }
            for variant in SCENARIO_VARIANTS
        },
        "repetitions_per_cell": REPETITIONS_PER_CELL,
        "schedule": [entry.to_dict() for entry in chosen_schedule],
        "prompt_template": {
            "system": SYSTEM_INSTRUCTION,
            "user": USER_INSTRUCTION,
        },
        "context_budget_chars": MAX_CONTEXT_CHARS,
        "prompt_budget_chars": MAX_PROMPT_CHARS,
        "provider_alias": provider_alias,
        "decision_client_type": decision_client_type,
        "request_contract": {
            "body_fields": ["model", "messages"],
            "minimal_request": True,
            "timeout_seconds": 60,
            "configured_transport_retries": 0,
            "application_retries": 0,
        },
        "source_sha256": {
            "context_policies": _source_sha256(C0StatePolicy),
            "context_compiler": _source_sha256(ContextCompiler),
            "scenario_preludes": _source_sha256(prepare_ablation_scenario),
            "prompt_template": _source_sha256(build_decision_prompt),
            "decision_client": _source_sha256(OpenAICompatibleDecisionClient),
        },
    }
    serialized = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return {
        **canonical,
        "experiment_config_hash": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
    }


class ProviderInstabilityError(RuntimeError):
    """Three consecutive infrastructure-level failed requests; stop spending."""

    def __init__(self, episodes_completed: int) -> None:
        self.episodes_completed = episodes_completed
        super().__init__("PROVIDER_INSTABILITY")


class AblationExperimentRunner:
    """Reuse EpisodeRunner for each scheduled cell; no duplicated rule path."""

    def __init__(
        self,
        client: DecisionModelClient,
        *,
        output_dir: Path | str,
        experiment_config_hash: str,
        decision_policy_name: str,
        model_name: str | None,
        write_artifacts: bool = True,
    ) -> None:
        self.client = client
        self.output_dir = Path(output_dir)
        self.experiment_config_hash = experiment_config_hash
        self.decision_policy_name = decision_policy_name
        self.model_name = model_name
        self.write_artifacts = write_artifacts

    async def run(
        self,
        schedule: Sequence[ScheduleEntry],
        *,
        on_episode: Callable[[ScheduleEntry, EpisodeResult], None] | None = None,
    ) -> list[EpisodeResult]:
        results: list[EpisodeResult] = []
        consecutive_infrastructure_failures = 0
        expected_start_state = world_snapshot(lunch_initial_world())
        for entry in schedule:
            setup = prepare_ablation_scenario(entry.scenario_variant)
            if setup.model_start_state != expected_start_state:
                raise RuntimeError("Scenario model-start worlds are not equal")
            policy = POLICY_FACTORIES[entry.context_policy_name]()
            runner = EpisodeRunner(
                LunchBenchmarkScenario(), self.client,
                output_dir=self.output_dir,
                record_prompt=False,
                decision_policy_name=self.decision_policy_name,
                model_name=self.model_name,
                context_policy_name=policy.name,
                context_policy=policy,
                write_artifacts=self.write_artifacts,
            )
            result = await runner.run_episode(
                entry.episode_index,
                episode_id=f"ablation-{entry.episode_index:06d}",
                setup=setup,
                experiment_config_hash=self.experiment_config_hash,
            )
            results.append(result)
            if on_episode is not None:
                on_episode(entry, result)
            if result.termination_reason in (
                TerminationReason.PROVIDER_ERROR, TerminationReason.TIMEOUT
            ):
                consecutive_infrastructure_failures = (
                    1 if result.steps else consecutive_infrastructure_failures + 1
                )
            else:
                consecutive_infrastructure_failures = 0
            if consecutive_infrastructure_failures >= 3:
                raise ProviderInstabilityError(len(results))
            if sum(item.total_provider_requests for item in results) > MAX_REAL_PROVIDER_REQUESTS:
                raise RuntimeError("Provider request budget exceeded")
        return results
