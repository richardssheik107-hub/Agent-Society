"""Summarize the once-only pilot from saved episodes without any model calls."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from types import SimpleNamespace

from behavior_prior_corpus_real_pilot import OUTPUT_ROOT, PROTECTED, audit_secrets, sha256, summarize
from social_sim.behavior_prior.benchmark import CONDITIONS, condition_episode_metrics, schedule
from social_sim.behavior_prior.index import BehaviorPriorIndex, load_nested_worker_corpora
from social_sim.daily.calibrated import config_hash
from social_sim.decision.config import DecisionProviderConfig

EXPERIMENT_ID = "real_20260917T085445574770Z"


def _core(snapshot: dict[str, object], *, coarse_needs: bool = True) -> tuple[object, ...]:
    person = snapshot["people"]["1"]
    return (person["location"], person.get("activity"), person["money"],
            tuple(sorted(person["inventory"].items())),
            round(person["hunger"], 1) if coarse_needs else person["hunger"],
            round(person["energy"], 1) if coarse_needs else person["energy"])


def row_from_saved(daily: dict[str, object], wrapper: dict[str, object],
                   cell: dict[str, object]) -> dict[str, object]:
    """Recover the original metric function's inputs from persisted observations."""
    trajectory = wrapper["trajectory"]
    ticks = daily["ticks"]
    steps = trajectory["steps"]
    full = daily["full_day_behavior_metrics"] or {}
    partial = daily["partial_window_metrics"] or {}
    activity_counts = daily.get("activity_counts") or partial.get("partial_activity_counts") or {}
    attempts = sorted(
        [(step["simulation_time"], step["state_before"]) for step in steps]
        + [(failure["simulation_time"], next(
            (tick["world_before"] for tick in ticks if tick["simulation_time"] == failure["simulation_time"]),
            None)) for failure in (*daily["provider_failures"], *daily["output_failures"])],
        key=lambda entry: entry[0],
    )
    minutes = [datetime.fromisoformat(time).toordinal() * 1440
               + datetime.fromisoformat(time).hour * 60 + datetime.fromisoformat(time).minute
               for time, _ in attempts]
    burst = sum(minutes[index] - minutes[index - 2] <= 30 for index in range(2, len(minutes)))
    cores = [_core(snapshot) for _, snapshot in attempts if snapshot is not None]
    same_state = sum(cores[index] == cores[index - 1] for index in range(1, len(cores)))
    durations = Counter(tick["active_activity"] for tick in ticks)
    active_minutes = 15 * sum(tick["active_activity"] is not None or tick["action_accepted"] is True
                              for tick in ticks)
    activity = {
        "decisions_per_sim_hour": len(attempts) / (len(ticks) / 4) if ticks else None,
        "decision_burst_count": burst, "same_state_decision_count": same_state,
        "active_minutes": active_minutes,
        "state_transition_count": sum(
            (tick["action_accepted"] is True and
             _core(tick["world_before"], coarse_needs=False) !=
             _core(tick["world_after_decision"], coarse_needs=False))
            + len(tick["completed_activities"]) for tick in ticks
        ),
        "sleep_minutes": 15 * durations["SLEEP"], "work_minutes": 15 * durations["WORK"],
        "meal_count": activity_counts.get("EAT", 0),
        "leisure_minutes": 15 * durations["LEISURE"], "move_count": activity_counts.get("MOVE", 0),
        "personal_care_minutes": 15 * durations["PERSONAL_CARE"],
        "chores_minutes": 15 * durations["CHORES"],
    }
    idle = {
        "idle_minutes": full.get("idle_minutes", partial.get("partial_idle_minutes")),
        "idle_ratio": full.get("idle_ratio", partial.get("partial_idle_ratio")),
        "max_idle_streak_minutes": full.get("max_idle_streak_minutes"),
        "unresolved_need_minutes": full.get("unresolved_need_minutes"),
        "repeated_invalid_count": full.get("repeated_invalid_count", 0),
    }
    result = SimpleNamespace(
        episode_id=daily["episode_id"], behavior_profile_name=daily["behavior_profile_name"],
        behavior_profile_hash=daily["behavior_profile_hash"], day_completed=daily["day_completed"],
        termination_reason=SimpleNamespace(value=daily["termination_reason"]),
        provider_failures=daily["provider_failures"], observed_minutes=daily["observed_minutes"],
        decision_count=daily["decision_count"], provider_request_count=daily["provider_request_count"],
        activity_metrics=activity, idle_metrics=idle, unique_activity_types=daily.get("unique_activity_types"),
        activity_counts=activity_counts, ticks=[SimpleNamespace(**tick) for tick in ticks],
        output_failures=daily["output_failures"], failure_taxonomy=daily.get("failure_taxonomy", []),
        prior_audit=tuple(wrapper["prior_audit"]),
        trajectory=SimpleNamespace(
            steps=[SimpleNamespace(**step) for step in steps],
            accepted_actions=trajectory["accepted_actions"], rejected_actions=trajectory["rejected_actions"],
            total_input_tokens=trajectory["total_input_tokens"],
            total_output_tokens=trajectory["total_output_tokens"],
            total_reasoning_tokens=trajectory["total_reasoning_tokens"],
            total_latency_seconds=trajectory["total_latency_seconds"],
        ),
    )
    condition = next(condition for condition in CONDITIONS if condition.name == cell["condition"])
    row = condition_episode_metrics(result, segment=cell["segment"], condition=condition)
    if not daily["day_completed"]:
        # These are partial-window observations; never label them full-segment behavior.
        for field in ("idle_minutes", "idle_ratio", "max_idle_streak", "active_minutes",
                      "unique_activity_types", "unresolved_need_minutes", "obligation_neglect_minutes",
                      "sleep_minutes", "work_minutes", "leisure_minutes", "personal_care_minutes",
                      "chores_minutes", "same_state_decision_count", "decision_burst_count"):
            row[field] = None
    return row


def main() -> None:
    output = OUTPUT_ROOT / EXPERIMENT_ID
    config = json.loads((output / "experiment_config.json").read_text(encoding="utf-8"))
    assert schedule() == config["schedule"]
    assert config_hash({key: value for key, value in config.items()
                        if key != "experiment_config_hash"}) == config["experiment_config_hash"]
    wrappers = [json.loads(line) for line in (output / "trajectories.jsonl").read_text(encoding="utf-8").splitlines()]
    if len(wrappers) != 20:
        raise RuntimeError(f"NEED_20_SAVED_CELLS_GOT_{len(wrappers)}")
    rows = []
    for number, (cell, wrapper) in enumerate(zip(config["schedule"], wrappers), 1):
        assert cell["episode"] == number
        assert wrapper["trajectory"]["episode_id"] == f"neutral-day-{number:06d}"
        assert wrapper["condition"] == cell["condition"]
        assert wrapper["experiment_config_hash"] == config["experiment_config_hash"]
        daily = json.loads((output / "episodes/daily_episodes" / f"episode_{number:06d}.json").read_text(encoding="utf-8"))
        assert daily["episode_id"] == wrapper["trajectory"]["episode_id"]
        row = row_from_saved(daily, wrapper, cell)
        row["experiment_config_hash"] = config["experiment_config_hash"]
        rows.append(row)
    corpora, corpus_info = load_nested_worker_corpora()
    indices = {name: BehaviorPriorIndex.build(days) for name, days in corpora.items()}
    assert config["retrieval_index_hashes"] == {name: index.index_hash for name, index in indices.items()}
    assert config["corpus_sample_hashes"] == corpus_info["sample_id_hashes"]
    protected = {str(path.relative_to(OUTPUT_ROOT.parents[2])): sha256(path) for path in PROTECTED}
    summarize(output, rows, config, corpus_info, indices, protected, None)
    audit_secrets(output, DecisionProviderConfig.from_env().api_key)
    print(f"SUMMARIZED=20 COMPLETE={sum(row['segment_completion'] for row in rows)} OUTPUT={output}")


if __name__ == "__main__":
    main()
