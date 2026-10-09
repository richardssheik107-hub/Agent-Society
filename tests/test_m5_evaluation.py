from copy import deepcopy

import pytest

from social_sim.continuity.engine import ContinuityWorld
from social_sim.continuity.models import canonical_json
from social_sim.longrun.behavior_audit import behavior_warnings
from social_sim.longrun.config import LongRunConfig, WarningThresholds
from social_sim.longrun.evaluation import (
    InvariantViolation, check_invariants, compare_semantic_runs, daily_metrics, evaluate,
    check_invariants_full,
)
from social_sim.longrun.policy import seed_world
from social_sim.longrun.reporting import build_summary, export_reports


def export_world(world, steps=(), requests=()):
    config = LongRunConfig()
    return {"world": world.store.snapshot(), "events": world.store.events(),
            "steps": list(steps), "requests": list(requests), "checkpoints": [],
            "manifest": {"config": config.to_dict()},
            "session": {"session_id": "test", "initial_minute": 0, "horizon_minute": 10080,
                        "invariants": check_invariants(world)}}


@pytest.mark.parametrize("field", ["money_cents", "hunger_milli", "energy_milli"])
def test_l1_checks_ledger_and_deterministic_need_rules(field):
    with ContinuityWorld(":memory:", acquire_enabled=True) as world:
        seed_world(world, LongRunConfig())
        assert check_invariants(world)["L1"] == "PASS"
        with world.store.transaction():
            actor = world.store.actor(1)
            actor[field] += 1
            world.store.put_actor(actor)
        with pytest.raises(InvariantViolation):
            check_invariants(world)


def test_l1_checks_commitment_progress_not_only_actor_facts():
    with ContinuityWorld(":memory:", acquire_enabled=True) as world:
        seed_world(world, LongRunConfig())
        world.start("sleep", 1, "SLEEP")
        world.advance("tick", 15)
        check_invariants(world)
        with world.store.transaction():
            c = world.store.get_commitment("sleep")
            c["elapsed_min"] += 1
            world.store.put_commitment(c)
        with pytest.raises(InvariantViolation):
            check_invariants(world)


def test_full_restart_audit_rejects_price_and_remaining_duration_tampering():
    with ContinuityWorld(":memory:", acquire_enabled=True) as world:
        seed_world(world, LongRunConfig())
        world.start("own", 1, "ACQUIRE", "game_a")
        with world.store.transaction():
            actor = world.store.actor(1)
            actor["money_cents"] += 1000
            world.store.put_actor(actor)
            row = world.store.db.execute("SELECT seq,payload FROM events WHERE kind='PURCHASED'").fetchone()
            import json
            payload = json.loads(row["payload"])
            payload["cost_cents"] = 2000
            world.store.db.execute("UPDATE events SET payload=? WHERE seq=?", (canonical_json(payload), row["seq"]))
        with pytest.raises(InvariantViolation):
            check_invariants_full(world)
    with ContinuityWorld(":memory:", acquire_enabled=True) as world:
        seed_world(world, LongRunConfig())
        world.start("sleep", 1, "SLEEP")
        world.advance("tick", 15)
        with world.store.transaction():
            c = world.store.get_commitment("sleep")
            c["remaining_min"] = 360
            world.store.put_commitment(c)
        with pytest.raises(InvariantViolation):
            check_invariants_full(world)


@pytest.mark.parametrize("static_target", ["rules", "object"])
def test_full_audit_keeps_genesis_parameter_contract(static_target):
    import json
    with ContinuityWorld(":memory:", acquire_enabled=True) as world:
        seed_world(world, LongRunConfig())
        with world.store.transaction():
            if static_target == "rules":
                data = json.loads(world.store.meta("rule_parameters"))
                data["work_pay_cents_per_minute"] += 1
                world.store.db.execute("UPDATE meta SET value=? WHERE key='rule_parameters'", (canonical_json(data),))
            else:
                row = world.store.db.execute("SELECT data FROM objects WHERE id='game_a'").fetchone()
                data = json.loads(row[0])
                data["price_cents"] += 1
                world.store.db.execute("UPDATE objects SET data=? WHERE id='game_a'", (canonical_json(data),))
        with pytest.raises(InvariantViolation):
            check_invariants_full(world)


@pytest.mark.parametrize("invariants,stop", [
    ({"invariants": "FAIL", "L1": "FAIL"}, None),
    ({"invariants": "FAIL", "L1": "PASS"}, None),
    ({"invariants": "PASS", "L1": "PASS"}, "INVARIANT_FAILED"),
])
def test_confirmed_l1_failure_is_not_hidden(invariants, stop):
    with ContinuityWorld(":memory:", acquire_enabled=True) as world:
        seed_world(world, LongRunConfig())
        data = export_world(world)
        data["session"].update(invariants=invariants, stop_reason=stop)
        assert evaluate(data)["L1"]["status"] == "FAIL"


def test_corrupt_world_exports_failure_and_retains_review_packet(tmp_path):
    from social_sim.longrun.session import LongRunSession
    with LongRunSession.create(tmp_path, "bad", LongRunConfig(), {}) as session:
        with session.world.store.transaction():
            actor = session.world.store.actor(1)
            actor["money_cents"] += 1
            session.world.store.put_actor(actor)
        summary = export_reports(session)
        assert summary["evaluation"]["L1"]["status"] == "FAIL"
        assert (session.dir / "summary.json").is_file()
        assert (session.dir / "report.md").is_file()


def test_timely_daily_report_matches_final_export(tmp_path):
    import asyncio
    from social_sim.longrun.policy import FakeLongRunPolicy
    from social_sim.longrun.runner import LongRunRunner
    from social_sim.longrun.session import LongRunSession
    config = LongRunConfig(sim_days=7)
    with LongRunSession.create(tmp_path, "one", config, {}) as session:
        result = asyncio.run(LongRunRunner(session, FakeLongRunPolicy(session.world, config)).run())
        assert result["simulation_minutes"] == 10080
        report_path = session.dir / "daily/day001.json"
        original = report_path.read_bytes()
        raw = session.export_data()
        raw_warnings = behavior_warnings(raw["requests"], raw["steps"], config.warnings)
        assert not any(w["code"] == "CONSECUTIVE_DECISIONS_NO_SIMULATION_PROGRESS" for w in raw_warnings)
        assert export_reports(session)["evaluation"]["L1"]["status"] == "PASS"
        assert report_path.read_bytes() == original


def test_warning_only_records_and_layers_do_not_infer_human_success():
    with ContinuityWorld(":memory:", acquire_enabled=True) as world:
        seed_world(world, LongRunConfig())
        state = world.store.snapshot()
        failed = [{"status": "RULE_REJECTED", "minute": 0,
                   "proposal": {"activity": "PLAY", "target": "game_a"},
                   "before_state": state, "after_state": state} for _ in range(5)]
        before = deepcopy(failed)
        warnings = behavior_warnings(failed, [], WarningThresholds())
        assert any(w["code"] == "REPEATED_FAILED_PROPOSAL_UNCHANGED_STATE" for w in warnings)
        assert any(w["code"] == "CONSECUTIVE_DECISIONS_NO_SIMULATION_PROGRESS" for w in warnings)
        assert all(w["intervention"] == "NONE" for w in warnings)
        assert failed == before and world.store.snapshot() == state
        result = evaluate(export_world(world, requests=failed))
        assert result["L1"]["status"] == "PASS"
        assert result["L2"]["aggregate_score"] is None
        assert result["L3"]["status"] == "UNRESOLVED"
        assert result["L3"]["human_review"] == "未审核"


def test_start_commands_at_different_observation_minutes_do_not_imply_no_progress():
    state = {"actor": {"money_cents": 10000, "hunger_milli": 800, "energy_milli": 700,
                       "work_minutes": 0}, "minute": 0}
    requests = []
    for minute in (0, 30, 60, 90, 120):
        observed = {**state, "minute": minute}
        requests.append({"minute": minute, "before_state": observed, "after_state": observed,
                         "status": "DECISION_ACCEPTED", "proposal": {"activity": "LEISURE", "target": None}})
    warnings = behavior_warnings(requests, [])
    assert not any(w["code"] == "CONSECUTIVE_DECISIONS_NO_SIMULATION_PROGRESS" for w in warnings)


def test_registered_steps_are_not_time_or_resource_evidence():
    state = {"actor": {"money_cents": 10000, "hunger_milli": 1000, "energy_milli": 0,
                       "work_minutes": 0}, "minute": 0}
    requests = [{"request_id": f"r{i}", "minute": 0, "before_state": state, "after_state": state,
                 "status": "RULE_REJECTED", "proposal": {"activity": "PLAY", "target": "game_a"}}
                for i in range(3)]
    steps = [{"status": "REGISTERED", "commitment_id": f"r{i}", "phase": "WORK",
              "from_minute": 0, "to_minute": 360, "before_state": state, "after_state": state}
             for i in range(3)]
    warnings = behavior_warnings(requests, steps)
    assert any(w["code"] == "CONSECUTIVE_DECISIONS_NO_SIMULATION_PROGRESS" for w in warnings)
    assert not any(w["code"] in {"SUSTAINED_HIGH_HUNGER", "SUSTAINED_LOW_ENERGY"} for w in warnings)


def test_rejected_work_proposals_do_not_claim_observed_income():
    requests = []
    for index, balance in enumerate((15000, 13000, 11000, 9000, 7000)):
        observed = {"minute": index * 30, "actor": {"money_cents": balance, "work_minutes": 0}}
        requests.append({"minute": index * 30, "before_state": observed, "after_state": observed,
                         "status": "RULE_REJECTED", "proposal": {"activity": "WORK", "target": None}})
    assert any(w["code"] == "DECLINING_MONEY_WITHOUT_OBSERVED_WORK"
               for w in behavior_warnings(requests, []))


def test_cross_midnight_work_and_purchases_use_actual_minutes():
    with ContinuityWorld(":memory:", acquire_enabled=True) as world:
        seed_world(world, LongRunConfig())
        world.act("office", 1, "MOVE", "office")
        world.advance("pre", 1430)
        world.start("work", 1, "WORK")
        before = world.store.snapshot()
        world.advance("work30", 1460)
        after = world.store.snapshot()
        data = export_world(world, [{"status": "COMMITTED", "activity": "WORK", "phase": "WORK",
                                    "from_minute": 1430, "to_minute": 1460,
                                    "before_state": before, "after_state": after}])
        days = daily_metrics(data)
        assert days[0]["activity_phase_minutes"]["WORK"] == 10
        assert days[1]["activity_phase_minutes"]["WORK"] == 20
        assert [d["work_income_cents"] for d in days] == [100, 200]
        assert days[0]["final_state"] is None
        assert days[1]["initial_state"] is None
        world.control("cancel", 1, "CANCEL")
        world.act("restaurant", 1, "MOVE", "restaurant")
        world.start("meal", 1, "MEAL", "food_meal")
        world.advance("eat", 1490)
        days = daily_metrics(export_world(world))
        assert days[0]["purchase_spending_cents"] == 0
        assert days[1]["purchase_spending_cents"] == 2000
        assert days[1]["meal_events"] == 1


def test_export_missing_tokens_and_secrets_are_not_fabricated(tmp_path):
    with ContinuityWorld(":memory:", acquire_enabled=True) as world:
        seed_world(world, LongRunConfig())
        data = export_world(world, requests=[{"status": "INVALID_MODEL_OUTPUT", "input_tokens": None,
                                            "raw_text": "SECRET_RAW_COMPLETION", "api_key": "SECRET_KEY"}])
        summary = export_reports(data, tmp_path)
        assert summary["costs"]["input_tokens"]["known_subtotal"] is None
        assert summary["costs"]["input_tokens"]["missing_rate"] == 1
        assert "SECRET_RAW_COMPLETION" not in (tmp_path / "requests.jsonl").read_text()
        assert "SECRET_KEY" not in (tmp_path / "requests.jsonl").read_text()
        assert summary["evaluation"]["L3"]["status"] == "UNRESOLVED"


def test_semantic_compare_ignores_session_and_command_names_but_keeps_behavior():
    with ContinuityWorld(":memory:", acquire_enabled=True) as world:
        seed_world(world, LongRunConfig())
        world.start("one", 1, "SLEEP")
        world.advance("step", 20)
        first = export_world(world)
        second = deepcopy(first)
        second["session"]["session_id"] = "other"
        second["world"]["commitments"][0]["id"] = "renamed"
        for event in second["events"]:
            event["command_id"] = "different"
            if "id" in event["payload"]:
                event["payload"]["id"] = "renamed"
        assert compare_semantic_runs(first, second)["equivalent"]
        second["world"]["actors"][0]["money_cents"] += 1
        assert not compare_semantic_runs(first, second)["equivalent"]
        summary = build_summary(first)
        assert summary["simulation_minutes"] == 20
