"""No-network A1.1b stress pipeline smoke with 36 scripted decisions."""

from __future__ import annotations

import asyncio

from social_sim.decision.client import DecisionReply, DecisionResponseMetadata, ProviderContractError
from social_sim.evaluation.decision_contract_stress import (
    STRESS_REQUESTS, run_decision_contract_stress, stress_schedule,
)


GOOD = '{"action":"WORK","target":null}'


class ScriptedClient:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, _system_prompt: str, _user_prompt: str) -> DecisionReply:
        self.calls += 1
        if self.calls == 5:
            return DecisionReply(f"```json\n{GOOD}\n```")
        if self.calls == 18:
            return DecisionReply(f"I choose:\n{GOOD}")
        if self.calls == 29:
            return DecisionReply('{"action":"WORK"}')
        return DecisionReply(GOOD)


class FailureProbeClient:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, _system_prompt: str, _user_prompt: str) -> DecisionReply:
        self.calls += 1
        if self.calls == 1:
            raise ProviderContractError("NO_CHOICES", DecisionResponseMetadata(choices_count=0))
        if self.calls == 2:
            return DecisionReply('{"action":"FLY","target":null}')
        return DecisionReply("{bad json")


async def main() -> None:
    client = ScriptedClient()
    schedule = stress_schedule()
    result = await run_decision_contract_stress(client, schedule=schedule)
    summary = result.summary()
    assert client.calls == STRESS_REQUESTS == 36
    assert summary["provider_success_count"] == 36
    assert summary["strict_valid_count"] == 33
    assert summary["recoverable_valid_count"] == 36
    assert summary["semantic_invalid_count"] == 0
    assert summary["format_failure_count"] == 2
    assert summary["repair_applied_counts"] == {
        "ADD_NULL_TARGET": 1,
        "EXTRACT_SINGLE_JSON": 1,
        "STRIP_CODE_FENCE": 1,
    }
    assert summary["engineering_gate_pass"] is True

    probe = FailureProbeClient()
    failure_result = await run_decision_contract_stress(probe, schedule=schedule[:3])
    assert probe.calls == 3
    assert [row.failure_type for row in failure_result.requests] == [
        "NO_CHOICES", "INVALID_ACTION", "MALFORMED_JSON",
    ]
    assert [row.failure_category for row in failure_result.requests] == [
        "PROVIDER_FAILURE", "SEMANTIC_FAILURE", "FORMAT_FAILURE",
    ]
    assert failure_result.summary()["engineering_gate_pass"] is False
    print("DECISION_CONTRACT_OFFLINE_SMOKE_PASS")
    print("SCRIPTED_REQUESTS=36")
    print("STRICT_VALID=33")
    print("RECOVERABLE_VALID=36")
    print("PROVIDER_SEMANTIC_FORMAT_CLASSIFICATION=PASS")


if __name__ == "__main__":
    asyncio.run(main())
