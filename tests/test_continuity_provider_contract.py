"""真实客户端接口的离线失败契约；不发送 HTTP 请求。"""
import asyncio
from types import SimpleNamespace

import httpx

from social_sim.continuity import ContinuityWorld
from social_sim.continuity.benchmark import seed_demo
from social_sim.continuity.decision import ActivityDecisionRunner
from social_sim.decision.client import DecisionResponseMetadata, ProviderContractError


class Fake:
    def __init__(self, error=None):
        self.error = error
        self.calls = 0

    async def complete(self, system, user):
        self.calls += 1
        if self.error:
            raise self.error
        return SimpleNamespace(raw_text='{"activity":"WATCH","target":"series_a"}')


def test_httpx_timeout_is_not_generic_provider_error(tmp_path):
    with ContinuityWorld(tmp_path / "w.db") as world:
        seed_demo(world)
        fake = Fake(httpx.ReadTimeout("must not log raw diagnostic"))
        runner = ActivityDecisionRunner(world, fake)
        row = asyncio.run(runner.decide("timeout"))
        assert row["status"] == "PROVIDER_TIMEOUT"
        assert row["input_tokens"] is None
        assert world.minute == 0
        assert fake.calls == 1


def test_wire_contract_error_retains_only_safe_metadata(tmp_path):
    with ContinuityWorld(tmp_path / "w.db") as world:
        seed_demo(world)
        error = ProviderContractError("OUTPUT_BUDGET_EXHAUSTED",
            DecisionResponseMetadata(http_status=200, input_tokens=123,
                                     output_tokens=128, provider_model="test-model"))
        row = asyncio.run(ActivityDecisionRunner(world, Fake(error)).decide("length"))
        assert row["status"] == "PROVIDER_CONTRACT_ERROR"
        assert row["failure_category"] == "OUTPUT_BUDGET_EXHAUSTED"
        assert row["input_tokens"] == 123
        assert row["provider_model"] == "test-model"
        assert world.minute == 0


def test_multiple_runners_share_persistent_budget(tmp_path):
    with ContinuityWorld(tmp_path / "w.db") as world:
        seed_demo(world)
        fake = Fake()
        first = ActivityDecisionRunner(world, fake, max_calls=1)
        second = ActivityDecisionRunner(world, fake, max_calls=1)
        assert asyncio.run(first.decide("first"))["status"] == "DECISION_ACCEPTED"
        world.advance("finish", 30)
        assert asyncio.run(second.decide("second"))["status"] == "REQUEST_BUDGET_EXHAUSTED"
        assert fake.calls == 1


def test_cancellation_is_persisted_and_not_retried(tmp_path):
    class Cancelled:
        async def complete(self, system, user):
            raise asyncio.CancelledError
    with ContinuityWorld(tmp_path / "w.db") as world:
        seed_demo(world)
        runner = ActivityDecisionRunner(world, Cancelled())
        try:
            asyncio.run(runner.decide("cancelled"))
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("cancellation must propagate")
        fake = Fake()
        result = asyncio.run(ActivityDecisionRunner(world, fake).decide("cancelled"))
        assert result["status"] == "ALREADY_ATTEMPTED"
        assert result["previous_status"] == "REQUEST_CANCELLED"
        assert fake.calls == 0
