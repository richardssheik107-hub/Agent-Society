"""Offline safety and accounting tests for the world-free A1.1b stress pilot."""

from __future__ import annotations

import asyncio
import json

from social_sim.decision.client import (
    DecisionReply, DecisionResponseMetadata, FakeDecisionClient, ProviderContractError,
)
from social_sim.evaluation.decision_contract_stress import (
    STRESS_CASES, STRESS_REQUESTS, prepare_stress_prompt,
    run_decision_contract_stress, sanitize_visible_output, stress_schedule,
)


GOOD = '{"action":"WORK","target":null}'


def test_fixed_cases_schedule_and_real_prompt_pipeline() -> None:
    assert len(STRESS_CASES) == 12
    schedule = stress_schedule()
    assert len(schedule) == STRESS_REQUESTS == 36
    assert [item.case_id for item in schedule[:12]] == [case.case_id for case in STRESS_CASES]
    assert len({item.case_id for item in schedule}) == 12
    assert all(left.case_id != right.case_id for left, right in zip(schedule, schedule[1:]))
    assert all(sum(item.case_id == case.case_id for item in schedule) == 3 for case in STRESS_CASES)

    for case in STRESS_CASES:
        context, prompt = prepare_stress_prompt(case)
        compiled = json.loads(context)
        assert compiled["p"]["goal"] == "live through the day while handling your basic needs and obligations"
        assert compiled["a"] == ["MOVE", "BUY", "EAT", "SLEEP", "WORK", "LEISURE"]
        assert compiled["targets"] == ["home", "office", "restaurant", "park", "meal"]
        assert compiled["work"] == "09:00-17:00"
        assert compiled["s"]["loc"] == case.location
        assert prompt.context_chars == len(context)
        assert prompt.prompt_chars < 3000
        assert "Return JSON only" in prompt.system
        if case.feedback:
            assert compiled["e"] == [case.feedback]
        else:
            assert compiled["e"] == []
    d5 = next(case for case in STRESS_CASES if case.case_id.startswith("D5"))
    assert json.loads(prepare_stress_prompt(d5)[0])["s"]["inv"] == {"meal": 0}


def test_offline_36_single_attempts_gate_and_recovery_recommendation() -> None:
    class ScriptedClient:
        def __init__(self) -> None:
            self.calls = 0
            self.prompts = []

        async def complete(self, system_prompt, user_prompt):
            self.calls += 1
            self.prompts.append((system_prompt, user_prompt))
            raw = f"```json\n{GOOD}\n```" if self.calls in (8, 21) else GOOD
            return DecisionReply(raw, provider_request_count=1)

    client = ScriptedClient()
    seen = []
    result = asyncio.run(run_decision_contract_stress(client, on_result=seen.append))
    summary = result.summary()
    assert client.calls == len(client.prompts) == 36
    assert len(seen) == len(result.requests) == 36
    assert [row.request_index for row in result.requests] == list(range(1, 37))
    assert summary["provider_success_count"] == 36
    assert summary["strict_valid_count"] == 34
    assert summary["recoverable_valid_count"] == 36
    assert summary["format_failure_count"] == 2
    assert summary["semantic_invalid_count"] == 0
    assert summary["repair_applied_counts"] == {"STRIP_CODE_FENCE": 2}
    assert summary["engineering_gate_pass"] is True
    assert summary["recovery_recommended_for_full_day"] is True
    assert summary["input_tokens"] is None
    assert summary["output_tokens"] is None
    assert summary["reasoning_tokens"] is None
    assert all(item["requests"] == 3 for item in summary["case_metrics"].values())


def test_provider_failure_separate_from_unrecoverable_semantics_and_format() -> None:
    class ScriptedClient:
        def __init__(self) -> None:
            self.calls = 0
            self.last_metadata = None

        async def complete(self, _system_prompt, _user_prompt):
            self.calls += 1
            if self.calls == 1:
                raise ProviderContractError("NO_CHOICES", DecisionResponseMetadata(
                    http_status=200, choices_count=0, provider_model="backend-one",
                    input_tokens=10, output_tokens=0, reasoning_tokens=0,
                ))
            if self.calls == 2:
                return DecisionReply('{"action":"FLY","target":null}')
            if self.calls == 3:
                return DecisionReply("one object? no")
            return DecisionReply(GOOD)

    client = ScriptedClient()
    result = asyncio.run(run_decision_contract_stress(client, schedule=stress_schedule()[:4]))
    assert client.calls == 4
    assert [row.failure_type for row in result.requests] == [
        "NO_CHOICES", "INVALID_ACTION", "MALFORMED_JSON", None,
    ]
    assert [row.failure_category for row in result.requests] == [
        "PROVIDER_FAILURE", "SEMANTIC_FAILURE", "FORMAT_FAILURE", None,
    ]
    summary = result.summary()
    assert summary["provider_failure_count"] == 1
    assert summary["semantic_invalid_count"] == 1
    assert summary["format_failure_count"] == 1
    assert summary["engineering_gate_pass"] is False
    assert result.requests[0].input_tokens == 10


def test_missing_null_target_is_recoverable_not_semantic_invalid() -> None:
    result = asyncio.run(run_decision_contract_stress(
        FakeDecisionClient('{"action":"WORK"}'), schedule=stress_schedule()[:2],
    ))
    assert all(row.failure_type == "MISSING_TARGET" for row in result.requests)
    assert all(row.recoverable_valid for row in result.requests)
    assert all(row.repair_applied == "ADD_NULL_TARGET" for row in result.requests)
    assert result.summary()["semantic_invalid_count"] == 0


def test_visible_excerpt_is_bounded_and_secret_or_reasoning_safe() -> None:
    secret = "ark-secret-value-123456789012"
    raw = "x" * 480 + secret + " <think>hidden private rationale</think>"
    excerpt = sanitize_visible_output(raw, secrets=(secret,))
    assert excerpt is not None and len(excerpt) <= 500
    assert secret not in excerpt
    assert "hidden private rationale" not in excerpt
    assert "<think" not in excerpt
    assert "reasoning_content" not in (sanitize_visible_output("reasoning_content: hidden words") or "")
    assert "Authorization" not in (sanitize_visible_output("Authorization: private words") or "")
    assert sanitize_visible_output(None) is None
