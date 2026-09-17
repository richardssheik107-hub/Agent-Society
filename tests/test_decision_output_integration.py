"""A1.1b: production acceptance and diagnostics remain one-call and auditable."""

from __future__ import annotations

import asyncio

import pytest

from social_sim.daily.models import DailyTerminationReason
from social_sim.daily.runner import DailyEpisodeRunner
from social_sim.decision import CompactDecisionService, DecisionParseError, FakeDecisionClient
from social_sim.decision.client import DecisionReply, ProviderContractError, inspect_chat_completion
from social_sim.world.observation import LocalObservation


def _observation() -> LocalObservation:
    return LocalObservation(1, "2026-01-01T06:00:00+00:00", "home", 100.0, 0.3)


def _decide(raw: str, *, recovery: bool) -> tuple[CompactDecisionService, object]:
    client = FakeDecisionClient(raw)
    service = CompactDecisionService(
        client, allow_deterministic_output_recovery=recovery
    )
    result = asyncio.run(service.decide(
        {"name": "Neutral", "goal": "live through the day while handling your basic needs and obligations"},
        _observation(), available_actions=["WORK"],
    ))
    assert client.call_count == service.decision_call_count == 1
    return service, result


def test_default_preserves_legacy_fence_acceptance_without_claiming_recovery() -> None:
    service, result = _decide('```json\n{"action":"WORK","target":null}\n```', recovery=False)
    assert result.proposal.action.value == "WORK"
    assert result.strict_valid is False
    assert result.recoverable_valid is True
    assert result.repair_available == "STRIP_CODE_FENCE"
    assert result.repair_applied is None
    assert result.output_recovered is False
    assert result.legacy_non_strict_acceptance is True
    assert service.last_output_diagnostic["content_chars"] > 0
    assert "raw_text" not in service.last_output_diagnostic


def test_feature_flag_applies_only_bounded_recovery_once() -> None:
    _, result = _decide('I choose:\n{"action":"WORK"}', recovery=True)
    assert result.proposal.action.value == "WORK"
    assert result.strict_valid is False
    assert result.recoverable_valid is True
    assert result.failure_type == "EXTRA_TEXT_AROUND_JSON"
    assert result.repair_applied == "EXTRACT_SINGLE_JSON+ADD_NULL_TARGET"
    assert result.output_recovered is True
    assert result.legacy_non_strict_acceptance is False


def test_default_rejects_new_recovery_case_but_retains_safe_diagnostic() -> None:
    client = FakeDecisionClient('I choose:\n{"action":"WORK","target":null}')
    service = CompactDecisionService(
        client, allow_deterministic_output_recovery=False
    )
    with pytest.raises(DecisionParseError):
        asyncio.run(service.decide(
            {"name": "Neutral", "goal": "test"}, _observation(), available_actions=["WORK"],
        ))
    assert client.call_count == 1
    diagnostic = service.last_output_diagnostic
    assert diagnostic["failure_type"] == "EXTRA_TEXT_AROUND_JSON"
    assert diagnostic["repair_available"] == "EXTRACT_SINGLE_JSON"
    assert diagnostic["repair_applied"] is None
    assert "I choose" not in str(diagnostic)


def test_daily_invalid_output_has_specific_type_separate_from_provider_failure(tmp_path) -> None:
    class InvalidActionClient:
        provider_request_count = 0

        async def complete(self, system_prompt: str, user_prompt: str) -> DecisionReply:
            self.provider_request_count += 1
            return DecisionReply(
                '{"action":"WOR","target":null}', provider_request_count=1
            )

    client = InvalidActionClient()
    day = asyncio.run(DailyEpisodeRunner(
        client, output_dir=tmp_path, write_artifacts=False,
        allow_deterministic_output_recovery=True,
    ).run_episode(1))
    assert day.termination_reason is DailyTerminationReason.INVALID_MODEL_OUTPUT
    assert day.provider_request_count == client.provider_request_count == 1
    assert day.provider_failures == ()
    assert len(day.output_failures) == 1
    failure = day.output_failures[0]
    assert failure["failure_type"] == "INVALID_ACTION"
    assert failure["failure_category"] == "SEMANTIC_FAILURE"
    assert failure["strict_valid"] is False
    assert failure["recoverable_valid"] is False
    assert failure["content_chars"] == 30
    assert "WOR" not in str(failure)


def test_nonempty_length_finish_is_provider_budget_failure() -> None:
    with pytest.raises(ProviderContractError) as exc:
        inspect_chat_completion({
            "model": "fixture",
            "choices": [{
                "finish_reason": "length",
                "message": {"content": '{"action":"WORK","target":null}'},
            }],
        })
    assert exc.value.category == "OUTPUT_BUDGET_EXHAUSTED"
    assert exc.value.metadata.content_chars == 31
