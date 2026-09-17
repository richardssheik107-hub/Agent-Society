"""Constructed Phase 8A data isolates prelude from model behavior metrics."""

from types import SimpleNamespace

import pytest

from social_sim.evaluation.ablation_metrics import aggregate_ablation_metrics


CONFIG_HASH = "a" * 64
HOME = {"people": {"1": {"location": "home", "money": 100.0, "hunger": 0.8, "inventory": {}}}}
RESTAURANT = {"people": {"1": {"location": "restaurant", "money": 100.0, "hunger": 0.8, "inventory": {}}}}
PARK = {"people": {"1": {"location": "park", "money": 100.0, "hunger": 0.8, "inventory": {}}}}


def make_step(
    action: str,
    target: str,
    *,
    accepted: bool,
    reason: str,
    before=HOME,
    after=HOME,
    provider_model: str | None = "glm-5.3",
    input_tokens: int = 100,
    context_chars: int = 200,
) -> SimpleNamespace:
    return SimpleNamespace(
        proposal={"action": action, "target": target},
        intent={"action": action, "target": target},
        rule_allowed=accepted,
        rule_reason_code=reason,
        state_before=before,
        state_after=after,
        event={"event_type": "MOVED" if accepted else "ACTION_REJECTED"},
        context_chars=context_chars,
        prompt_chars=context_chars + 250,
        input_tokens=input_tokens,
        output_tokens=20,
        reasoning_tokens=15,
        decision_latency_seconds=2.0,
        provider_request_count=1,
        provider_model=provider_model,
        prompt=None,
    )


def make_episode(
    policy: str,
    variant: str,
    steps: tuple[SimpleNamespace, ...],
    *,
    success: bool = True,
    prelude_rejections: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        context_policy_name=policy,
        scenario_variant=variant,
        steps=steps,
        success=success,
        termination_reason="GOAL_REACHED" if success else "MAX_DECISIONS",
        decision_count=len(steps),
        accepted_actions=sum(step.rule_allowed for step in steps),
        rejected_actions=sum(not step.rule_allowed for step in steps),
        invalid_outputs=0,
        provider_errors=0,
        total_provider_requests=len(steps),
        prelude_rejection_count=prelude_rejections,
        prelude_rejection_present=prelude_rejections > 0,
        experiment_config_hash=CONFIG_HASH,
    )


def test_prelude_rejection_is_excluded_and_repeat_metrics_are_objective() -> None:
    repeated = make_episode(
        "C0_state", "S1_LAST_REJECTION",
        (
            make_step("BUY", "meal", accepted=False, reason="NOT_AT_SELLER"),
            make_step("BUY", "meal", accepted=False, reason="NOT_AT_SELLER"),
            make_step("MOVE", "restaurant", accepted=True, reason="ACCEPTED", after=RESTAURANT),
        ),
        prelude_rejections=1,
    )
    recovered = make_episode(
        "C1_last", "S1_LAST_REJECTION",
        (make_step("MOVE", "restaurant", accepted=True, reason="ACCEPTED", after=RESTAURANT),),
        prelude_rejections=1,
    )
    summary = aggregate_ablation_metrics(
        [repeated, recovered],
        policies=("C0_state", "C1_last"),
        scenarios=("S1_LAST_REJECTION", "S2_BURIED_REJECTION"),
    )
    c0 = summary.policy_metrics["C0_state"]
    c1 = summary.policy_metrics["C1_last"]
    assert c0.model_rejection_count == 2
    assert c0.prelude_rejection_count == 1
    assert c0.rejection_rate == pytest.approx(2 / 3)
    assert c0.first_rejection_repeat_count == 1
    assert c0.first_rejection_repeat_rate == 1
    assert c0.recovery_after_rejection_rate == 0
    assert c0.same_rejected_action_repeat_count == 1
    assert c0.first_decision_action_counts == {"BUY": 1}
    assert c0.action_counts == {"BUY": 2, "MOVE": 1}
    assert c0.context_cost_chars == 600
    assert c0.input_token_cost == 300
    assert c0.success_per_1k_input_tokens == pytest.approx(1 / 0.3)
    assert c1.model_rejection_count == 0
    assert c1.prelude_rejection_count == 1
    assert c1.first_rejection_repeat_rate == 0
    assert c1.recovery_after_rejection_rate == 1
    assert summary.policy_scenario_metrics["C1_last"]["S2_BURIED_REJECTION"].episodes == 0


def test_actual_backend_change_is_reported_without_pooled_claim() -> None:
    a = make_episode(
        "C0_state", "S0_BASELINE",
        (make_step("MOVE", "restaurant", accepted=True, reason="ACCEPTED", after=RESTAURANT),),
    )
    b = make_episode(
        "C1_last", "S0_BASELINE",
        (make_step("MOVE", "restaurant", accepted=True, reason="ACCEPTED", after=RESTAURANT,
                   provider_model="glm-5.4"),),
    )
    summary = aggregate_ablation_metrics([a, b])
    assert summary.provider_model_counts == {"glm-5.3": 1, "glm-5.4": 1}
    assert summary.model_backend_stable is False
    assert summary.total_provider_requests == 2
    assert summary.unattributed_provider_requests == 0
    assert set(summary.backend_metrics) == {"glm-5.3", "glm-5.4"}
    assert summary.backend_metrics["glm-5.3"].episodes == 1


def test_single_observed_backend_with_timeout_is_stable_but_partly_unknown() -> None:
    episode = make_episode(
        "C0_state", "S0_BASELINE",
        (make_step("MOVE", "restaurant", accepted=True, reason="ACCEPTED", after=RESTAURANT),),
        success=False,
    )
    episode.termination_reason = "TIMEOUT"
    episode.decision_count = 2
    episode.total_provider_requests = 2
    summary = aggregate_ablation_metrics([episode])
    assert summary.provider_model_counts == {"glm-5.3": 1}
    assert summary.model_backend_stable is True
    assert summary.unattributed_provider_requests == 1
    assert summary.policy_metrics["C0_state"].timeout_count == 1
    assert summary.policy_metrics["C0_state"].infra_failure_count == 1


def test_backend_switch_inside_one_episode_attributes_each_step_not_success() -> None:
    mixed = make_episode(
        "C0_state", "S1_LAST_REJECTION",
        (
            make_step("BUY", "meal", accepted=False, reason="NOT_AT_SELLER",
                      provider_model="glm-5.3", context_chars=200, input_tokens=100),
            make_step("MOVE", "restaurant", accepted=True, reason="ACCEPTED",
                      after=RESTAURANT, provider_model="glm-5.4", context_chars=300,
                      input_tokens=120),
        ),
        prelude_rejections=1,
    )
    summary = aggregate_ablation_metrics([mixed])
    assert summary.provider_model_counts == {"glm-5.3": 1, "glm-5.4": 1}
    assert summary.backend_metrics["MIXED_BACKEND"].episodes == 1
    assert summary.backend_episode_success_attributable["MIXED_BACKEND"] is False
    a = summary.provider_model_policy_scenario_steps["glm-5.3"]["C0_state"]["S1_LAST_REJECTION"]
    b = summary.provider_model_policy_scenario_steps["glm-5.4"]["C0_state"]["S1_LAST_REJECTION"]
    assert (a.steps, a.provider_requests, a.rejected_actions, a.total_context_chars, a.total_input_tokens) == (
        1, 1, 1, 200, 100,
    )
    assert (b.steps, b.provider_requests, b.rejected_actions, b.total_context_chars, b.total_input_tokens) == (
        1, 1, 0, 300, 120,
    )
    assert "success" not in a.to_dict()
    assert "completion_rate" not in b.to_dict()


def test_nonadjacent_rejection_repeat_resets_after_world_change() -> None:
    episode = make_episode(
        "C0_state", "S0_BASELINE",
        (
            make_step("BUY", "meal", accepted=False, reason="NOT_AT_SELLER"),
            make_step("EAT", "meal", accepted=False, reason="ITEM_NOT_OWNED"),
            make_step("BUY", "meal", accepted=False, reason="NOT_AT_SELLER"),
            make_step("MOVE", "park", accepted=True, reason="ACCEPTED", after=PARK),
            make_step("BUY", "meal", accepted=False, reason="NOT_AT_SELLER",
                      before=PARK, after=PARK),
        ),
    )
    summary = aggregate_ablation_metrics([episode])
    assert summary.policy_metrics["C0_state"].same_rejected_action_repeat_count == 1


def test_timeout_and_provider_error_rates_are_distinct() -> None:
    timeout = make_episode("C0_state", "S0_BASELINE", (), success=False)
    timeout.termination_reason = "TIMEOUT"
    timeout.provider_errors = 1  # Legacy clients may count timeout as provider error.
    provider_error = make_episode("C0_state", "S0_BASELINE", (), success=False)
    provider_error.termination_reason = "PROVIDER_ERROR"
    provider_error.provider_errors = 1
    summary = aggregate_ablation_metrics([timeout, provider_error])
    item = summary.policy_metrics["C0_state"]
    assert item.provider_error_count == 1
    assert item.provider_error_rate == 0.5
    assert item.timeout_count == 1
    assert item.timeout_rate == 0.5
    assert item.infra_failure_count == 2
    assert item.infra_failure_rate == 1.0


def test_empty_metrics_have_no_division_by_zero() -> None:
    summary = aggregate_ablation_metrics(
        [], policies=("C0_state",), scenarios=("S0_BASELINE",)
    )
    item = summary.policy_metrics["C0_state"]
    assert item.episodes == 0
    assert item.completion_rate == 0
    assert item.success_per_1k_input_tokens is None
    assert summary.model_backend_stable is None
