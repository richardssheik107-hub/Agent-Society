"""决策预算和失败路径只使用 fake provider；不得访问网络。"""
import asyncio
from types import SimpleNamespace

from social_sim.continuity import ContinuityWorld
from social_sim.continuity.benchmark import seed_demo
from social_sim.continuity.decision import ActivityDecisionRunner


class Fake:
    def __init__(self, text):
        self.text, self.calls = text, 0
    async def complete(self, system, user):
        self.calls += 1
        return SimpleNamespace(raw_text=self.text, provider_model="fake",
                               input_tokens=1, output_tokens=1)


def test_one_decision_then_ticks_do_not_recall_model(tmp_path):
    with ContinuityWorld(tmp_path / "world.db") as world:
        seed_demo(world)
        fake = Fake('{"activity":"WATCH","target":"series_a"}')
        runner = ActivityDecisionRunner(world, fake, max_calls=1)
        assert asyncio.run(runner.decide("q"))["status"] == "DECISION_ACCEPTED"
        assert asyncio.run(runner.decide("next"))["status"] == "COMMITMENT_PRESENT"
        world.advance("f", 30)
        assert asyncio.run(runner.decide("next"))["status"] == "REQUEST_BUDGET_EXHAUSTED"
        assert fake.calls == 1


def test_invalid_output_does_not_change_world_or_create_fake_wait(tmp_path):
    with ContinuityWorld(tmp_path / "world.db") as world:
        seed_demo(world)
        before = world.store.snapshot()
        fake = Fake("not json")
        runner = ActivityDecisionRunner(world, fake)
        row = asyncio.run(runner.decide("q"))
        assert row["status"] == "INVALID_MODEL_OUTPUT"
        assert world.store.snapshot() == before
        assert fake.calls == 1


def test_provider_error_not_stored_as_behavioral_idle(tmp_path):
    class Error:
        last_metadata = SimpleNamespace(http_status=401)
        async def complete(self, system, user):
            raise RuntimeError("super-secret-key in raw response")
    with ContinuityWorld(tmp_path / "world.db") as world:
        seed_demo(world)
        log = tmp_path / "log.jsonl"
        runner = ActivityDecisionRunner(world, Error(), journal_path=log)
        row = asyncio.run(runner.decide("q"))
        assert row["status"] == "PROVIDER_ERROR"
        assert row["http_status"] == 401
        assert "super-secret" not in log.read_text()
        assert world.minute == 0


def test_committed_id_after_restart_does_not_recall_provider(tmp_path):
    with ContinuityWorld(tmp_path / "world.db") as world:
        seed_demo(world)
        world.start("q", 1, "WATCH", "series_a")
        world.advance("f", 30)
        fake = Fake('{"activity":"WATCH","target":"series_a"}')
        runner = ActivityDecisionRunner(world, fake)
        assert asyncio.run(runner.decide("q"))["status"] == "ALREADY_RECORDED"
        assert fake.calls == 0


def test_failed_provider_attempt_is_not_silently_reissued(tmp_path):
    path = tmp_path / "world.db"
    with ContinuityWorld(path) as world:
        seed_demo(world)
        fake = Fake("bad json")
        runner = ActivityDecisionRunner(world, fake)
        asyncio.run(runner.decide("failed"))
    with ContinuityWorld(path) as world:
        fake = Fake('{"activity":"WATCH","target":"series_a"}')
        runner = ActivityDecisionRunner(world, fake)
        assert asyncio.run(runner.decide("failed"))["status"] == "ALREADY_ATTEMPTED"
        assert fake.calls == 0


def test_provider_wall_time_is_bounded(tmp_path):
    class Slow:
        async def complete(self, system, user):
            await asyncio.sleep(1)
    with ContinuityWorld(tmp_path / "world.db") as world:
        seed_demo(world)
        runner = ActivityDecisionRunner(world, Slow(), hard_timeout_seconds=0.01)
        row = asyncio.run(runner.decide("timeout"))
        assert row["status"] == "PROVIDER_TIMEOUT"
        assert world.minute == 0
        assert world.store.commitment(1) is None
