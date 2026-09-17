"""Phase 8A prelude variants share a model-start world, not a history."""

import json

import pytest

from social_sim.evaluation.ablation_scenarios import (
    SCENARIO_VARIANTS,
    ScenarioVariant,
    prepare_ablation_scenario,
)


def _compact_events(variant: ScenarioVariant) -> list[str]:
    setup = prepare_ablation_scenario(variant)
    return [event.compact() for event in setup.event_log.all()]


def test_all_variants_have_identical_model_start_world() -> None:
    setups = [prepare_ablation_scenario(variant) for variant in SCENARIO_VARIANTS]
    baseline = setups[0].model_start_state
    assert all(setup.model_start_state == baseline for setup in setups)
    alice = baseline["people"]["1"]
    assert alice == {"location": "home", "money": 100.0, "hunger": 0.8, "inventory": {}}
    assert baseline["venues"]["restaurant"]["meal"] == {"price": 20.0, "stock": 10}
    assert [setup.prelude_action_count for setup in setups] == [0, 1, 5, 4]
    assert [setup.prelude_rejection_count for setup in setups] == [0, 1, 1, 0]


def test_s1_has_only_last_not_at_seller_rejection() -> None:
    assert _compact_events(ScenarioVariant.S0_BASELINE) == []
    assert _compact_events(ScenarioVariant.S1_LAST_REJECTION) == [
        "ACTION_REJECTED:NOT_AT_SELLER"
    ]


def test_s2_buries_rejection_behind_four_move_events() -> None:
    setup = prepare_ablation_scenario(ScenarioVariant.S2_BURIED_REJECTION)
    history = [event.compact() for event in setup.event_log.all()]
    assert history == [
        "ACTION_REJECTED:NOT_AT_SELLER",
        "MOVED:park", "MOVED:home", "MOVED:park", "MOVED:home",
    ]
    assert "ACTION_REJECTED:NOT_AT_SELLER" not in history[-3:]
    assert history[-1] == "MOVED:home"
    assert setup.prelude_events[0]["action"] == "BUY"
    assert setup.prelude_events[0]["reason_code"] == "NOT_AT_SELLER"
    assert [event["event_type"] for event in setup.prelude_events[1:]] == ["MOVED"] * 4


def test_s3_contains_only_move_noise() -> None:
    assert _compact_events(ScenarioVariant.S3_NOISE_ONLY) == [
        "MOVED:park", "MOVED:home", "MOVED:park", "MOVED:home",
    ]


def test_each_setup_has_fresh_world_and_event_log() -> None:
    first = prepare_ablation_scenario(ScenarioVariant.S2_BURIED_REJECTION)
    second = prepare_ablation_scenario(ScenarioVariant.S2_BURIED_REJECTION)
    assert first.world is not second.world
    assert first.event_log is not second.event_log
    assert first.model_start_state == second.model_start_state
    assert first.prelude_events == second.prelude_events
    assert first.event_log.next_event_id() == second.event_log.next_event_id()


def test_metadata_is_structured_and_separate_from_model_trajectory() -> None:
    setup = prepare_ablation_scenario("S1_LAST_REJECTION")
    metadata = setup.metadata()
    assert metadata["scenario_variant"] == "S1_LAST_REJECTION"
    assert metadata["prelude_action_count"] == 1
    assert metadata["prelude_rejection_count"] == 1
    assert metadata["prelude_rejection_present"] is True
    assert metadata["model_start_state"] == setup.model_start_state
    assert metadata["prelude_events"][0]["event_type"] == "ACTION_REJECTED"
    json.dumps(metadata, allow_nan=False)


def test_unknown_variant_is_rejected() -> None:
    with pytest.raises(ValueError):
        prepare_ablation_scenario("S4_UNKNOWN")
