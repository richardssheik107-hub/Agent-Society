"""Resume only the seven unattempted cells of the interrupted A2-Fast pilot."""

from __future__ import annotations

import asyncio
import json

from behavior_prior_corpus_real_pilot import (
    OUTPUT_ROOT, PROTECTED, START_MARKER, TIMEOUT_SECONDS, audit_secrets, sha256,
)
from social_sim.behavior_prior.benchmark import CONDITIONS, schedule
from social_sim.behavior_prior.index import BehaviorPriorIndex, load_nested_worker_corpora
from social_sim.daily.calibrated import CalibratedSegmentBenchmark, config_hash
from social_sim.daily.profiles import load_experiment_profiles
from social_sim.daily.validation import validate_daily_trajectory
from social_sim.decision import OpenAICompatibleDecisionClient
from social_sim.decision.config import CODING_PLAN, DecisionProviderConfig

EXPERIMENT_ID = "real_20260917T085445574770Z"
FIRST_NEW_EPISODE = 14


async def main() -> None:
    output = OUTPUT_ROOT / EXPERIMENT_ID
    marker = json.loads(START_MARKER.read_text(encoding="utf-8"))
    config = json.loads((output / "experiment_config.json").read_text(encoding="utf-8"))
    fixed_schedule = json.loads((output / "schedule.json").read_text(encoding="utf-8"))
    assert marker["experiment_id"] == EXPERIMENT_ID
    assert fixed_schedule == schedule() == config["schedule"]
    config_without_hash = dict(config)
    assert config_hash({k: v for k, v in config_without_hash.items() if k != "experiment_config_hash"}) == config["experiment_config_hash"]
    assert config["request_timeout_seconds"] == TIMEOUT_SECONDS == 60
    assert config["transport_retries"] == 0
    assert config["max_decisions_per_segment"] == 8
    assert not (output / "dataset_manifest.json").exists()

    saved = (output / "trajectories.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(saved) == FIRST_NEW_EPISODE - 1
    for number, line in enumerate(saved, 1):
        wrapper = json.loads(line)
        cell = fixed_schedule[number - 1]
        assert wrapper["trajectory"]["episode_id"] == f"neutral-day-{number:06d}"
        assert wrapper["condition"] == cell["condition"]
        assert wrapper["experiment_config_hash"] == config["experiment_config_hash"]
        assert (output / "episodes/daily_episodes" / f"episode_{number:06d}.json").exists()
    for number in range(FIRST_NEW_EPISODE, 21):
        assert not (output / "episodes/daily_episodes" / f"episode_{number:06d}.json").exists()

    corpora, corpus_info = load_nested_worker_corpora()
    indices = {name: BehaviorPriorIndex.build(days) for name, days in corpora.items()}
    assert config["corpus_sample_hashes"] == corpus_info["sample_id_hashes"]
    assert config["retrieval_index_hashes"] == {name: index.index_hash for name, index in indices.items()}
    profile = load_experiment_profiles()[2]
    assert (config["simulator_profile"], config["simulator_profile_hash"]) == (profile.name, profile.profile_hash)
    protected_before = {str(path.relative_to(OUTPUT_ROOT.parents[2])): sha256(path) for path in PROTECTED}
    assert protected_before == {
        "src/social_sim/daily/time.py": "9ac6b13ade1eeb3c9e7345950ed4891453eaf01aadd9f5fe72d959bc36fcf320",
        "config/experimental/neutral_day_calibrated_v1.yaml": "58f293122bc48b274e1c4cfee3d8b198877bb3508fbd1b72c5bdc61e620ba14f",
    }
    provider_config = DecisionProviderConfig.from_env()
    assert provider_config.model == config["provider_alias"] == "ark-code-latest"
    assert provider_config.base_url_category == CODING_PLAN
    provider = OpenAICompatibleDecisionClient(
        base_url=provider_config.api_base, api_key=provider_config.api_key,
        model=provider_config.model, timeout_seconds=TIMEOUT_SECONDS, minimal_request=True,
    )
    conditions = {condition.name: condition for condition in CONDITIONS}
    try:
        for cell in fixed_schedule[FIRST_NEW_EPISODE - 1:]:
            number = cell["episode"]
            condition = conditions[cell["condition"]]
            print(f"START CELL={number}/20 {condition.name} {cell['segment']}", flush=True)
            result = await CalibratedSegmentBenchmark(
                provider, output / "episodes", provider_config.model,
                prior_index=indices.get(condition.corpus), prior_limit=condition.prior_limit,
            ).run(number, cell["segment"], profile)
            validate_daily_trajectory(result)
            assert result.decision_count <= 8 and result.provider_request_count <= result.decision_count
            assert all(step.provider_request_count == 1 and step.prompt is None for step in result.trajectory.steps)
            assert not result.prior_audit if condition.prior_limit == 0 else all(
                len(record["activities"]) <= condition.prior_limit for record in result.prior_audit
            )
            with (output / "trajectories.jsonl").open("a", encoding="utf-8") as file:
                file.write(json.dumps({
                    "condition": condition.name, "corpus": condition.corpus or "B0",
                    "prior_limit": condition.prior_limit,
                    "behavior_profile_name": profile.name, "behavior_profile_hash": profile.profile_hash,
                    "experiment_config_hash": config["experiment_config_hash"],
                    "prior_audit": [dict(record) for record in result.prior_audit],
                    "trajectory": result.trajectory.to_dict(),
                }, ensure_ascii=False) + "\n")
            audit_secrets(output, provider_config.api_key)
            assert {str(path.relative_to(OUTPUT_ROOT.parents[2])): sha256(path) for path in PROTECTED} == protected_before
            print(f"DONE CELL={number}/20 {condition.name} {cell['segment']} "
                  f"{result.termination_reason.value} requests={result.provider_request_count}", flush=True)
            if result.termination_reason.value == "ARCHITECTURE_ERROR":
                raise RuntimeError("ARCHITECTURE_VIOLATION")
    finally:
        await provider.aclose()


if __name__ == "__main__":
    asyncio.run(main())
