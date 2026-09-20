"""Q6 回归：真实 SQLite 持久化、幂等、回滚、部分进度和显式重看。"""
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from social_sim.continuity import ContinuityWorld, ObjectDefinition, initial_actor, validate_world
from social_sim.continuity.benchmark import run_days, seed_demo
from social_sim.continuity.context import decision_prompt, observe, parse_proposal
from social_sim.continuity.models import digest


@pytest.fixture
def world(tmp_path):
    w = ContinuityWorld(tmp_path / "world.sqlite")
    seed_demo(w)
    yield w
    w.close()


def assert_ok(result):
    assert result["accepted"], result


def test_seed_is_idempotent_after_restart(tmp_path):
    path = tmp_path / "world.sqlite"
    with ContinuityWorld(path) as w:
        seed_demo(w)
        w.act("buy", 1, "BUY", "game_a")
        before = w.store.snapshot()
    with ContinuityWorld(path) as w:
        seed_demo(w)
        assert w.store.snapshot() == before


def test_changed_fixture_not_silently_applied(world):
    with pytest.raises(ValueError, match="fixture mismatch"):
        world.seed([initial_actor(1, 1)], [])


@pytest.mark.parametrize("target,satiety,kcal,price", [
    ("food_bread", 350, 320, 1200), ("food_meal", 600, 650, 2000),
])
def test_same_eat_rule_uses_object_attributes(world, target, satiety, kcal, price):
    assert_ok(world.act("move", 1, "MOVE", "restaurant"))
    before = world.store.actor(1)
    assert_ok(world.act("buy", 1, "BUY", target))
    assert_ok(world.act("eat", 1, "EAT", target))
    after = world.store.actor(1)
    assert after["money_cents"] == before["money_cents"] - price
    assert after["hunger_milli"] == before["hunger_milli"] - satiety
    assert after["calories_kcal"] == before["calories_kcal"] + kcal
    assert world.store.link(1, target)["quantity"] == 0
    validate_world(world)


def test_duplicate_purchase_does_not_charge_again(world):
    first = world.act("same", 1, "BUY", "game_a")
    before = world.store.snapshot()
    count = len(world.store.events())
    assert_ok(first)
    assert world.act("same", 1, "BUY", "game_a")["replayed"]
    assert world.store.snapshot() == before
    assert len(world.store.events()) == count


def test_id_collision_does_not_execute_a_different_command(world):
    assert_ok(world.act("id", 1, "BUY", "game_a"))
    before = world.store.snapshot()
    result = world.act("id", 1, "EAT", "food_bread")
    assert result["reason"] == "REQUEST_ID_REUSE"
    assert world.store.snapshot() == before


def test_durable_ownership_does_not_disappear_and_double_buy_rejected(world):
    world.act("buy", 1, "BUY", "game_a")
    assert world.act("again", 1, "BUY", "game_a")["reason"] == "ALREADY_OWNED"
    assert world.store.link(1, "game_a")["quantity"] == 1
    validate_world(world)


def test_rejected_action_leaves_facts_unchanged(world):
    before = world.store.snapshot()
    assert world.act("eat", 1, "EAT", "food_bread")["reason"] == "ITEM_NOT_OWNED"
    assert world.store.snapshot() == before


def test_meal_macro_has_one_high_level_choice_and_real_duration(world):
    assert_ok(world.start("meal", 1, "MEAL", "food_meal"))
    assert world.store.actor(1)["location"] == "home"
    assert_ok(world.advance("t14", 14))
    assert world.store.actor(1)["location"] == "home"
    assert_ok(world.advance("t15", 15))
    assert world.store.actor(1)["location"] == "restaurant"
    assert world.store.link(1, "food_meal")["quantity"] == 1
    assert world.store.actor(1)["calories_kcal"] == 0
    assert_ok(world.advance("t45", 45))
    assert world.store.commitment(1) is None
    assert world.store.link(1, "food_meal")["quantity"] == 0
    assert world.store.actor(1)["calories_kcal"] == 650
    assert sum(e["kind"] == "COMMITMENT_STARTED" for e in world.store.events()) == 1
    assert sum(e["kind"] == "PURCHASED" for e in world.store.events()) == 1
    validate_world(world)


def test_meal_does_not_rebuy_owned_food(world):
    world.act("move", 1, "MOVE", "restaurant")
    world.act("buy", 1, "BUY", "food_bread")
    money = world.store.actor(1)["money_cents"]
    world.start("meal", 1, "MEAL", "food_bread")
    world.advance("finish", 30)
    assert world.store.actor(1)["money_cents"] == money
    validate_world(world)


def test_macro_failure_preserves_completed_travel_but_no_free_food(tmp_path):
    w = ContinuityWorld(tmp_path / "poor.db")
    w.seed([initial_actor(1, 0)], [(ObjectDefinition("meal", "餐", "FOOD",
           ("edible", "purchasable"), 100, 100, 100), 1)])
    try:
        assert_ok(w.start("m", 1, "MEAL", "meal"))
        w.advance("arrive", 15)
        assert w.store.actor(1)["location"] == "restaurant"
        assert w.store.get_commitment("m")["status"] == "FAILED"
        assert w.store.get_commitment("m")["failure_reason"] == "INSUFFICIENT_FUNDS"
        assert w.store.link(1, "meal")["quantity"] == 0
        validate_world(w)
    finally:
        w.close()


def test_busy_actor_cannot_start_another_activity_or_consume(world):
    world.start("one", 1, "WATCH", "series_a")
    assert world.start("two", 1, "SLEEP")["reason"] == "ACTIVITY_IN_PROGRESS"
    assert world.act("three", 1, "BUY", "game_a")["reason"] == "ACTIVITY_IN_PROGRESS"


def test_partial_watch_not_completed_by_plan_clock(world):
    world.start("watch", 1, "WATCH", "series_a")
    world.advance("10", 10)
    world.control("pause", 1, "PAUSE")
    world.advance("tomorrow", 1440)
    link = world.store.link(1, "series_a")
    assert link["offsets"] == {"1": 10}
    assert link["watched"] == []
    assert world.store.commitment(1)["remaining_min"] == 20
    world.control("resume", 1, "RESUME")
    world.advance("finish", 1460)
    assert world.store.link(1, "series_a")["watched"] == [1]
    assert world.next_episode(1, "series_a") == 2
    validate_world(world)


def test_cancel_and_restart_continues_from_partial_offset(world):
    world.start("w1", 1, "WATCH", "series_a")
    world.advance("10", 10)
    world.control("cancel", 1, "CANCEL")
    world.start("w2", 1, "WATCH", "series_a")
    assert world.store.commitment(1)["remaining_min"] == 20
    world.advance("30", 30)
    assert world.next_episode(1, "series_a") == 2
    validate_world(world)


def test_same_episode_requires_explicit_rewatch(world):
    world.start("one", 1, "WATCH", "series_a")
    world.advance("30", 30)
    assert world.start("bad", 1, "WATCH", "series_a", episode=1)["reason"] == "ALREADY_COMPLETED"
    assert_ok(world.start("good", 1, "WATCH", "series_a", episode=1, rewatch=True))
    world.advance("60", 60)
    assert world.store.link(1, "series_a")["view_counts"] == {"1": 2}
    assert world.next_episode(1, "series_a") == 2
    validate_world(world)


def test_episode_order_and_range_are_checked(world):
    assert world.start("skip", 1, "WATCH", "series_a", episode=2)["reason"] == "PREREQUISITE_EPISODE_MISSING"
    assert world.start("bad", 1, "WATCH", "series_a", episode=121)["reason"] == "UNKNOWN_EPISODE"
    assert world.start("repeat", 1, "WATCH", "series_a", episode=1, rewatch=True)["reason"] == "REWATCH_REQUIRES_COMPLETION"


def test_aliases_share_same_progress(world):
    world.start("s", 1, "WATCH", "测试剧")
    world.advance("f", 30)
    assert world.next_episode(1, "series_a") == 2
    assert world.next_episode(1, "测试连续剧") == 2


def test_actors_do_not_share_media_progress(tmp_path):
    with ContinuityWorld(tmp_path / "two.db") as w:
        seed_demo(w, actors=2)
        w.start("one", 1, "WATCH", "series_a")
        w.advance("f", 30)
        assert w.next_episode(1, "series_a") == 2
        assert w.next_episode(2, "series_a") == 1
        validate_world(w)


def test_duplicate_tick_never_advances_twice(world):
    world.start("w", 1, "WATCH", "series_a")
    world.advance("tick", 15)
    snap = world.store.snapshot()
    assert world.advance("tick", 15)["replayed"]
    assert world.store.snapshot() == snap


def test_backward_time_rejected(world):
    world.advance("forward", 10)
    snap = world.store.snapshot()
    assert world.advance("back", 5)["reason"] == "TIME_REVERSAL"
    assert world.store.snapshot() == snap


def test_stale_intent_rejected(world):
    version = world.store.actor(1)["version"]
    world.advance("t", 1)
    assert world.start("s", 1, "SLEEP", expected_version=version)["reason"] == "STALE_STATE"


def test_unavailable_media_interrupts_without_fake_completion(world):
    world.start("w", 1, "WATCH", "series_a")
    world.advance("10", 10)
    world.set_available("off", "series_a", False)
    world.advance("40", 40)
    assert world.store.get_commitment("w")["status"] == "FAILED"
    assert world.store.link(1, "series_a")["watched"] == []
    assert world.store.link(1, "series_a")["offsets"] == {"1": 10}
    world.set_available("on", "series_a", True)
    world.start("again", 1, "WATCH", "series_a")
    world.advance("60", 60)
    assert world.next_episode(1, "series_a") == 2
    validate_world(world)


def test_event_write_failure_rolls_back_state_and_command(world, monkeypatch):
    snapshot = world.store.snapshot()
    original = world.store.emit
    def fail(*args, **kwargs):
        raise OSError("simulated disk error")
    monkeypatch.setattr(world.store, "emit", fail)
    with pytest.raises(OSError):
        world.act("buy", 1, "BUY", "game_a")
    assert world.store.snapshot() == snapshot
    assert world.store.db.execute("SELECT count(*) FROM commands").fetchone()[0] == 0
    monkeypatch.setattr(world.store, "emit", original)
    assert_ok(world.act("buy", 1, "BUY", "game_a"))
    validate_world(world)


def test_two_connections_duplicate_command_exactly_one_effect(tmp_path):
    path = tmp_path / "shared.db"
    with ContinuityWorld(path) as w:
        seed_demo(w)
    def call():
        with ContinuityWorld(path) as w:
            return w.act("shared", 1, "BUY", "game_a")
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: call(), range(2)))
    assert sum(r["replayed"] for r in results) == 1
    with ContinuityWorld(path) as w:
        assert w.store.link(1, "game_a")["quantity"] == 1
        validate_world(w)


def test_backup_restores_mid_episode(world, tmp_path):
    world.start("w", 1, "WATCH", "series_a")
    world.advance("a", 10)
    copy = tmp_path / "backup.db"
    world.store.backup(copy)
    with ContinuityWorld(copy) as restored:
        assert restored.store.snapshot() == world.store.snapshot()
        restored.advance("end", 30)
        assert restored.next_episode(1, "series_a") == 2
        validate_world(restored)


def test_tampered_ledger_detected(world):
    with world.store.transaction():
        actor = world.store.actor(1)
        actor["money_cents"] += 1
        world.store.put_actor(actor)
    with pytest.raises(AssertionError, match="MONEY_LEDGER_MISMATCH"):
        validate_world(world)


def test_schema_version_fail_closed(tmp_path):
    path = tmp_path / "wrong.db"
    with ContinuityWorld(path):
        pass
    with sqlite3.connect(path) as db:
        db.execute("UPDATE meta SET value='999' WHERE key='schema_version'")
    with pytest.raises(ValueError, match="unsupported state schema"):
        ContinuityWorld(path)


def test_context_is_bounded_read_only_and_contains_next_episode(world):
    before = digest(world.store.snapshot())
    obs = observe(world, 1)
    assert len(obs["objects"]) <= 5
    assert next(o for o in obs["objects"] if o["id"] == "series_a")["available"]
    system, user = decision_prompt(world, 1)
    assert len(system + user) < 3500
    assert digest(world.store.snapshot()) == before
    world.start("s", 1, "SLEEP")
    with pytest.raises(ValueError, match="re-decided"):
        decision_prompt(world, 1)


@pytest.mark.parametrize("raw", [
    '{"activity":"SLEEP","activity":"WORK","target":null}',
    '{"activity":"SLEEP","target":"series_a"}',
    '{"activity":"DELETE_DATABASE","target":null}',
    '{"activity":"WATCH","target":null}',
    '{"activity":"SLEEP","target":null,"extra":1}',
])
def test_strict_proposal_rejects_invalid_contract(raw):
    with pytest.raises(ValueError):
        parse_proposal(raw)


def test_strict_proposal_accepts_only_intent():
    assert parse_proposal('{"activity":"WATCH","target":"series_a"}') == {
        "activity": "WATCH", "target": "series_a"}


def test_seven_days_restart_duplicate_and_uninterrupted_match(tmp_path):
    a = run_days(tmp_path / "uninterrupted.db", 7)
    b = run_days(tmp_path / "restarted.db", 7, restart=True, duplicate_commands=True)
    assert a["state_hash"] == b["state_hash"]
    assert a["events"] == b["events"]
    assert b["completed_days"] == 7
    assert b["duplicate_commands_checked"] > 0
    assert b["restarts"] > 0
    assert b["provider_requests"] == 0
    assert not b["autonomous_human_likeness_proven"]


def test_process_dies_mid_transaction_rolls_back(tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path
    path = tmp_path / "crash.db"
    with ContinuityWorld(path) as w:
        seed_demo(w)
        before = w.store.snapshot()
    code = """
import os, sys
from social_sim.continuity import ContinuityWorld
w=ContinuityWorld(sys.argv[1])
with w.store.transaction():
    a=w.store.actor(1)
    a['money_cents']=0
    w.store.put_actor(a)
    os._exit(23)
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    result = subprocess.run([sys.executable, "-c", code, str(path)], env=env,
                            check=False, timeout=10)
    assert result.returncode == 23
    with ContinuityWorld(path) as w:
        assert w.store.snapshot() == before
        validate_world(w)


def test_two_actors_cannot_purchase_the_last_stock_twice(tmp_path):
    path = tmp_path / "last.db"
    with ContinuityWorld(path) as w:
        item = ObjectDefinition("one", "唯一物品", "GAME", ("playable", "purchasable"),
                                price_cents=100, seller="home")
        w.seed([initial_actor(1), initial_actor(2)], [(item, 1)])
    def buy(actor):
        with ContinuityWorld(path) as w:
            return w.act(f"buy-{actor}", actor, "BUY", "one")
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(buy, [1, 2]))
    assert sum(r["accepted"] for r in results) == 1
    assert {r["reason"] for r in results} == {"ACCEPTED", "OUT_OF_STOCK"}
    with ContinuityWorld(path) as w:
        validate_world(w)


def test_rule_parameters_are_persistent_and_version_checked(tmp_path):
    from social_sim.continuity.models import RuleParameters
    path = tmp_path / "rules.db"
    with ContinuityWorld(path, RuleParameters(travel_minutes=10)) as w:
        seed_demo(w)
        w.start("travel", 1, "TRAVEL", "office")
        assert w.store.commitment(1)["remaining_min"] == 10
    with ContinuityWorld(path) as w:
        assert w.parameters.travel_minutes == 10
    with pytest.raises(ValueError, match="explicit migration"):
        ContinuityWorld(path, RuleParameters(travel_minutes=15))


def test_deleted_owned_link_is_detected(world):
    assert_ok(world.act('buy', 1, 'BUY', 'game_a'))
    world.store.db.execute('DELETE FROM links')
    with pytest.raises(AssertionError, match='INVENTORY_LEDGER_MISMATCH'):
        validate_world(world)


def test_partial_episode_progress_rollback_is_detected(world):
    assert_ok(world.start('watch', 1, 'WATCH', 'series_a'))
    assert_ok(world.advance('tick', 10))
    link = world.store.link(1, 'series_a')
    link['offsets']['1'] = 0
    world.store.put_link(1, 'series_a', link)
    with pytest.raises(AssertionError, match='MEDIA_OFFSET_LEDGER_MISMATCH'):
        validate_world(world)


def test_completed_episode_deletion_is_detected(world):
    assert_ok(world.start('watch', 1, 'WATCH', 'series_a'))
    assert_ok(world.advance('tick', 30))
    link = world.store.link(1, 'series_a')
    link['watched'] = []
    world.store.put_link(1, 'series_a', link)
    with pytest.raises(AssertionError, match='COMPLETION_LEDGER_MISMATCH'):
        validate_world(world)
