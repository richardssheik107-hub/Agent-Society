"""Q6.1 离线 fake-provider 契约；整个文件禁止真实网络和模型请求。"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from social_sim.continuity import ContinuityWorld, ObjectDefinition, initial_actor
from social_sim.continuity.benchmark import seed_demo
from social_sim.continuity.decision import ActivityDecisionRunner
from social_sim.continuity.q6_1 import (
    Q61PilotRunner,
    analyze_rows,
    environment_record,
    validate_decision_budget,
    write_artifacts,
)


class SequenceClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.call_count = 0
        self.provider_request_count = 0
        self.last_metadata = None

    async def complete(self, system_prompt, user_prompt):
        del system_prompt, user_prompt
        self.call_count += 1
        self.provider_request_count += 1
        reply = self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        self.last_metadata = SimpleNamespace(
            provider_model="fake-model", finish_reason="stop", http_status=200
        )
        return SimpleNamespace(
            raw_text=reply,
            provider_model="fake-model",
            input_tokens=11,
            output_tokens=7,
            reasoning_tokens=None,
        )


def run_pilot(path, replies, **kwargs):
    world = ContinuityWorld(path)
    seed_demo(world)
    client = SequenceClient(replies)
    try:
        summary, rows = asyncio.run(Q61PilotRunner(world, client, **kwargs).run())
        return summary, rows, client, world
    except BaseException:
        world.close()
        raise


def test_four_legal_proposals_form_one_continuous_chain(tmp_path):
    summary, rows, client, world = run_pilot(
        tmp_path / "world.db",
        ['{"activity":"WATCH","target":"series_a"}'] * 4,
        max_decisions=4,
    )
    try:
        assert client.call_count == 4
        assert summary["application_calls"] == 4
        assert summary["accepted_decisions"] == 4
        assert summary["completed_decisions"] == 4
        assert summary["STATE_FEEDBACK_VISIBLE"] is True
        assert summary["STATE_FEEDBACK_CHANGED"] is True
        assert world.next_episode(1, "series_a") == 5
        assert rows[-1]["commitment_status"] == "COMPLETED"
    finally:
        world.close()


def test_watch_feedback_exposes_episode_two_before_second_request(tmp_path):
    summary, rows, client, world = run_pilot(
        tmp_path / "world.db",
        ['{"activity":"WATCH","target":"series_a"}'] * 2,
        max_decisions=2,
    )
    try:
        assert summary["media_continuity_exercised"] is True
        assert rows[1]["media_progress_before"]["series_a"]["next_episode"] == 2
        assert rows[1]["observation_digest_before"] == rows[0]["observation_digest_after"]
        assert client.call_count == 2
    finally:
        world.close()


def test_owned_game_survives_restart(tmp_path):
    path = tmp_path / "world.db"
    with ContinuityWorld(path) as world:
        seed_demo(world)
        assert world.act("buy-game", 1, "BUY", "game_a")["accepted"]
        assert world.store.link(1, "game_a")["quantity"] == 1
    with ContinuityWorld(path) as restored:
        seed_demo(restored)
        assert restored.store.link(1, "game_a")["quantity"] == 1


def test_same_request_id_has_one_effect_and_one_provider_call(tmp_path):
    path = tmp_path / "world.db"
    with ContinuityWorld(path) as world:
        seed_demo(world)
        client = SequenceClient(['{"activity":"WATCH","target":"series_a"}'])
        runner = ActivityDecisionRunner(world, client, max_calls=2)
        first = asyncio.run(runner.decide("same"))
        assert first["status"] == "DECISION_ACCEPTED"
        world.advance("finish", 30)
        event_count = len(world.store.events())
        second = asyncio.run(runner.decide("same"))
        assert second["status"] == "ALREADY_RECORDED"
        assert len(world.store.events()) == event_count
        assert client.call_count == 1


def test_invalid_json_stops_without_state_progress(tmp_path):
    path = tmp_path / "world.db"
    with ContinuityWorld(path) as world:
        seed_demo(world)
        before = world.store.snapshot()
        client = SequenceClient(["not-json"])
        summary, rows = asyncio.run(Q61PilotRunner(world, client).run())
        assert rows[0]["decision_status"] == "INVALID_MODEL_OUTPUT"
        assert summary["invalid_outputs"] == 1
        assert summary["provider_requests"] == 1
        assert world.store.snapshot() == before
        assert client.call_count == 1


def test_provider_timeout_stops_without_state_progress(tmp_path):
    path = tmp_path / "world.db"
    with ContinuityWorld(path) as world:
        seed_demo(world)
        client = SequenceClient([httpx.ReadTimeout("not persisted")])
        summary, rows = asyncio.run(
            Q61PilotRunner(world, client, hard_timeout_seconds=0.1).run()
        )
        assert rows[0]["decision_status"] == "PROVIDER_TIMEOUT"
        assert summary["provider_failures"] == 1
        assert summary["application_calls"] == 1
        assert world.minute == 0
        assert world.store.commitment(1) is None


def test_rule_rejection_stops_and_keeps_facts(tmp_path):
    path = tmp_path / "world.db"
    with ContinuityWorld(path) as world:
        seed_demo(world)
        before = world.store.snapshot()
        client = SequenceClient(['{"activity":"PLAY","target":"game_a"}'])
        summary, rows = asyncio.run(Q61PilotRunner(world, client).run())
        assert rows[0]["decision_status"] == "RULE_REJECTED"
        assert summary["rule_rejections"] == 1
        assert world.store.snapshot() == before
        assert client.call_count == 1


def test_commitment_failure_is_distinct_from_rule_rejection(tmp_path):
    path = tmp_path / "poor.db"
    item = ObjectDefinition(
        "food_meal", "测试餐食", "FOOD", ("edible", "purchasable"),
        price_cents=2000, calories_kcal=650, satiety_milli=600, seller="restaurant",
    )
    with ContinuityWorld(path) as world:
        world.seed([initial_actor(1, money_cents=0)], [(item, 1)])
        client = SequenceClient(['{"activity":"MEAL","target":"food_meal"}'])
        summary, rows = asyncio.run(Q61PilotRunner(world, client).run())
        assert rows[0]["decision_status"] == "DECISION_ACCEPTED"
        assert rows[0]["commitment_status"] == "FAILED"
        assert summary["commitment_failures"] == 1
        assert summary["rule_rejections"] == 0


def test_restart_does_not_repeat_completed_provider_request(tmp_path):
    path = tmp_path / "world.db"
    with ContinuityWorld(path) as world:
        seed_demo(world)
        first_client = SequenceClient(['{"activity":"WATCH","target":"series_a"}'])
        summary, _ = asyncio.run(Q61PilotRunner(world, first_client, max_decisions=1).run())
        assert summary["application_calls"] == 1
    with ContinuityWorld(path) as restored:
        seed_demo(restored)
        second_client = SequenceClient(['{"activity":"WATCH","target":"series_a"}'])
        runner = ActivityDecisionRunner(restored, second_client, max_calls=4)
        row = asyncio.run(runner.decide("q6_1:1"))
        assert row["status"] == "ALREADY_RECORDED"
        assert second_client.call_count == 0


def test_fifth_request_is_blocked_by_four_call_budget(tmp_path):
    path = tmp_path / "world.db"
    with ContinuityWorld(path) as world:
        seed_demo(world)
        client = SequenceClient(['{"activity":"WATCH","target":"series_a"}'] * 5)
        summary, _ = asyncio.run(Q61PilotRunner(world, client, max_decisions=4).run())
        assert summary["application_calls"] == 4
        assert client.call_count == 4
        runner = ActivityDecisionRunner(world, client, max_calls=4)
        assert asyncio.run(runner.decide("fifth"))["status"] == "REQUEST_BUDGET_EXHAUSTED"
        assert client.call_count == 4


def test_artifacts_exclude_raw_reasoning_and_secrets(tmp_path):
    path = tmp_path / "world.db"
    output = tmp_path / "artifact"
    with ContinuityWorld(path) as world:
        seed_demo(world)
        secret_reply = "not-json sk-test-secret reasoning_content hidden"
        client = SequenceClient([secret_reply])
        summary, rows = asyncio.run(Q61PilotRunner(world, client, max_decisions=1).run())
        environment = environment_record(
            tmp_path, provider_model="fake-model", real_provider=False
        )
        assert environment_record(
            tmp_path, provider_model="sk-test-secret", real_provider=False
        )["provider_model"] is None
        write_artifacts(output, world, summary, rows, environment)
    content = "".join(file.read_text(encoding="utf-8") for file in output.iterdir())
    assert "sk-test-secret" not in content
    assert "reasoning_content" not in content
    assert "hidden" not in content
    assert (output / "summary.json").is_file()
    assert (output / "decisions.jsonl").is_file()
    assert (output / "events.jsonl").is_file()
    assert (output / "final_state.json").is_file()
    assert (output / "environment.json").is_file()
    assert (output / "report_zh.md").is_file()


def test_marker_analyzer_does_not_read_future_labels():
    rows = [{
        "STATE_FEEDBACK_VISIBLE": True,
        "STATE_FEEDBACK_CHANGED": True,
        "proposal_activity": "WATCH",
        "media_progress_before": {"series_a": {"watched": []}},
        "inventory_delta": {},
        "MEDIA_PROGRESS_MONOTONIC": True,
        "INVENTORY_CONSISTENT": True,
        "MONEY_CONSISTENT": True,
        "NO_TIME_REVERSAL": True,
        "decision_status": "DECISION_ACCEPTED",
        "commitment_status": "COMPLETED",
        "request_id": "one",
        "acceptable_action_set": ["FUTURE_LABEL"],
    }]
    result = analyze_rows(rows)
    assert result["STATE_FEEDBACK_VISIBLE"] is True
    assert "FUTURE_LABEL" not in json.dumps(result)
    assert "human_like" not in json.dumps(result).lower()


def test_default_budget_rejects_unapproved_extension():
    with pytest.raises(ValueError, match="extended-pilot"):
        validate_decision_budget(5)
    validate_decision_budget(5, extended_pilot=True)
    with pytest.raises(ValueError, match="12"):
        validate_decision_budget(13, extended_pilot=True)


def test_real_entrypoint_without_flag_makes_zero_requests(capsys):
    from scripts.run_q6_1_real_continuity import main

    assert main(["--max-decisions", "4"]) == 0
    output = capsys.readouterr().out
    assert "REAL_PROVIDER_EXECUTED=NO" in output
    assert "PROVIDER_REQUESTS=0" in output


def test_real_entrypoint_rejects_more_than_four_without_extension():
    from scripts.run_q6_1_real_continuity import main

    with pytest.raises(SystemExit):
        main(["--allow-provider", "--max-decisions", "5"])


def test_public_decision_client_import_and_construction_without_network():
    from social_sim.decision import OpenAICompatibleDecisionClient

    transport = httpx.MockTransport(
        lambda request: pytest.fail("real transport must not be called")
    )
    client = OpenAICompatibleDecisionClient(
        base_url="http://offline.test/v1",
        model="offline-model",
        api_key="dummy",
        timeout_seconds=1,
        minimal_request=True,
        transport=transport,
    )
    try:
        assert client.call_count == 0
        assert client.provider_request_count == 0
    finally:
        asyncio.run(client.aclose())


def test_real_entrypoint_constructs_client_through_public_export_without_network(
    monkeypatch, tmp_path, capsys
):
    import scripts.run_q6_1_real_continuity as entrypoint

    constructed = []

    class ConstructionProbe:
        def __init__(self, **kwargs):
            constructed.append(kwargs)

        async def aclose(self):
            return None

    class PilotProbe:
        def __init__(self, world, client, **kwargs):
            assert client.__class__ is ConstructionProbe
            self.world = world
            self.client = client
            self.kwargs = kwargs

        async def run(self):
            return ({
                "application_calls": 0,
                "provider_requests": 0,
                "provider_failures": 0,
                "invalid_outputs": 0,
                "commitment_failures": 0,
                "final_invariants": {"invariants": "PASS"},
                "STATE_FEEDBACK_VISIBLE": True,
                "STATE_FEEDBACK_CHANGED": True,
                "termination_reason": "BUDGET_COMPLETED",
            }, [])

    monkeypatch.setenv("CONTINUITY_BASE_URL", "http://offline.test/v1")
    monkeypatch.setenv("CONTINUITY_MODEL", "offline-model")
    monkeypatch.setenv("CONTINUITY_API_KEY", "dummy")
    monkeypatch.setattr("social_sim.decision.OpenAICompatibleDecisionClient", ConstructionProbe)
    monkeypatch.setattr(entrypoint, "Q61PilotRunner", PilotProbe)
    monkeypatch.setattr(entrypoint, "write_artifacts", lambda *args: None)
    args = entrypoint.parser().parse_args([
        "--allow-provider", "--max-decisions", "1", "--output", str(tmp_path / "artifact")
    ])

    assert asyncio.run(entrypoint.run(args)) == 0
    assert len(constructed) == 1
    assert constructed[0]["base_url"] == "http://offline.test/v1"
    assert constructed[0]["model"] == "offline-model"
    assert capsys.readouterr().out.count("REAL_PROVIDER_EXECUTED=YES") == 1
