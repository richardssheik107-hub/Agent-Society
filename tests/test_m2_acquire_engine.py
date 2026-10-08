"""M2 获取规则、原子购买和独立 SQLite 连接的并发合同；请求为零。"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from social_sim.continuity import ContinuityWorld, ObjectDefinition, initial_actor, validate_world
from social_sim.continuity.benchmark import seed_demo
from social_sim.continuity.models import Rejected


def seed_acquire(world, *, seller="home", stock=2, money=10000, actors=1):
    """本轮专属合成目录；不改 Q6.2 四对象目录或历史产物。"""
    people = [initial_actor(1, money)]
    if actors == 2:
        people.append(initial_actor(2, 10000, location=seller))
    game = ObjectDefinition(
        "game_a", "M2合成游戏", "GAME", ("playable", "purchasable"),
        price_cents=3000, duration_min=45, seller=seller,
        aliases=("synthetic-game", "合成游戏别名"),
    )
    world.seed(people, [(game, stock)])


def purchased(world):
    return [event for event in world.store.events() if event["kind"] == "PURCHASED"]


def test_default_world_cannot_acquire_and_does_not_give_an_object(tmp_path):
    with ContinuityWorld(tmp_path / "default.sqlite") as world:
        seed_demo(world)
        before = world.store.snapshot()
        assert not world.acquire_enabled
        check = world.preview_activity(1, "ACQUIRE", "game_a")
        assert not check["start_allowed"] and not check["executable_now"]
        assert check["reason"] == "ACQUIRE_DISABLED"
        result = world.start("disabled", 1, "ACQUIRE", "game_a")
        assert not result["accepted"] and result["reason"] == "ACQUIRE_DISABLED"
        assert world.store.snapshot() == before
        assert not purchased(world)
        validate_world(world)


def test_same_seller_acquire_reuses_purchase_without_invented_time(tmp_path):
    with ContinuityWorld(tmp_path / "local.sqlite", acquire_enabled=True) as world:
        seed_acquire(world)
        before = world.store.actor(1)
        assert world.preview_activity(1, "PLAY", "game_a")["reason"] == "ITEM_NOT_OWNED"
        check = world.preview_activity(1, "ACQUIRE", "game_a")
        assert check["start_allowed"] and check["executable_now"]
        assert check["purchase_feasible_at_snapshot"]
        result = world.start("acquire", 1, "ACQUIRE", "game_a")
        assert result["accepted"] and result["commitment_status"] == "COMPLETED"
        commitment = world.store.get_commitment("acquire")
        assert commitment["activity"] == "ACQUIRE" and commitment["elapsed_min"] == 0
        assert world.store.commitment(1) is None
        assert world.minute == 0
        actor = world.store.actor(1)
        assert actor["money_cents"] == 7000
        assert actor["hunger_milli"] == before["hunger_milli"]
        assert actor["energy_milli"] == before["energy_milli"]
        assert actor["version"] > before["version"]
        assert world.store.object("game_a")["stock"] == 1
        assert world.store.link(1, "game_a")["quantity"] == 1
        assert world.store.link(1, "game_a")["play_minutes"] == 0
        assert len(purchased(world)) == 1
        assert purchased(world)[0]["payload"] == {
            "actor_id": 1, "object_id": "game_a", "cost_cents": 3000, "quantity": 1,
        }
        assert not any(event["kind"] == "TIME_ADVANCED" for event in world.store.events())
        assert world.preview_activity(1, "PLAY", "game_a")["executable_now"]
        validate_world(world)


def test_remote_acquire_has_committed_travel_then_zero_time_purchase(tmp_path):
    with ContinuityWorld(tmp_path / "remote.sqlite", acquire_enabled=True) as world:
        seed_acquire(world, seller="office")
        check = world.preview_activity(1, "ACQUIRE", "game_a")
        assert check["start_allowed"] and not check["executable_now"]
        assert check["reason"] == "REQUIRES_TRAVEL"
        assert check["purchase_feasible_at_snapshot"]
        assert world.start("acquire", 1, "ACQUIRE", "game_a")["accepted"]
        assert world.store.get_commitment("acquire")["phase"] == "MOVE"
        assert world.advance("midway", 7)["accepted"]
        assert world.store.actor(1)["location"] == "home"
        assert world.store.link(1, "game_a")["quantity"] == 0
        assert world.advance("arrival", 15)["accepted"]
        commitment = world.store.get_commitment("acquire")
        assert (commitment["phase"], commitment["status"], commitment["remaining_min"]) == (
            "BUY", "ACTIVE", 0,
        )
        assert commitment["elapsed_min"] == 15
        assert world.store.actor(1)["location"] == "office"
        assert world.store.actor(1)["money_cents"] == 10000
        assert world.store.link(1, "game_a")["quantity"] == 0
        assert world.advance("purchase", 15)["accepted"]
        assert world.store.get_commitment("acquire")["status"] == "COMPLETED"
        assert world.minute == 15
        assert world.store.actor(1)["hunger_milli"] == 815
        assert world.store.actor(1)["energy_milli"] == 685
        assert world.store.actor(1)["money_cents"] == 7000
        assert world.store.object("game_a")["stock"] == 1
        assert world.store.link(1, "game_a")["quantity"] == 1
        assert len(purchased(world)) == 1
        validate_world(world)


@pytest.mark.parametrize("stock,money,reason", [
    (2, 2999, "INSUFFICIENT_FUNDS"), (0, 10000, "OUT_OF_STOCK"),
])
@pytest.mark.parametrize("seller", ["home", "office"])
def test_initial_purchase_limits_reject_without_cost_or_commitment(
        tmp_path, stock, money, reason, seller):
    with ContinuityWorld(tmp_path / "limits.sqlite", acquire_enabled=True) as world:
        seed_acquire(world, stock=stock, money=money, seller=seller)
        before = world.store.snapshot()
        check = world.preview_activity(1, "ACQUIRE", "game_a")
        assert not check["start_allowed"] and not check["executable_now"]
        assert check["reason"] == reason
        result = world.start("acquire", 1, "ACQUIRE", "game_a")
        assert not result["accepted"] and result["reason"] == reason
        assert world.store.snapshot() == before
        assert world.store.commitment(1) is None
        assert not purchased(world)
        validate_world(world)


def test_owned_game_and_aliases_cannot_be_acquired_twice(tmp_path):
    with ContinuityWorld(tmp_path / "alias.sqlite", acquire_enabled=True) as world:
        seed_acquire(world)
        first = world.start("acquire", 1, "ACQUIRE", "SYNTHETIC-GAME")
        assert first["accepted"]
        assert world.store.get_commitment("acquire")["target"] == "game_a"
        before = world.store.snapshot()
        assert world.start("again", 1, "ACQUIRE", "合成游戏别名")["reason"] == "ALREADY_OWNED"
        assert world.store.snapshot() == before
        assert len(world.store.snapshot()["links"]) == 1
        assert len(purchased(world)) == 1
        validate_world(world)


@pytest.mark.parametrize("capabilities,reason", [
    (("playable",), "CAPABILITY_MISMATCH"),
    (("edible", "purchasable"), "UNSUPPORTED_ACQUIRE_OBJECT"),
])
def test_acquire_scope_does_not_expand_to_food_or_nonpurchasable_objects(
        tmp_path, capabilities, reason):
    with ContinuityWorld(tmp_path / "scope.sqlite", acquire_enabled=True) as world:
        item = ObjectDefinition("item", "隔离合成物品", "SYNTHETIC", capabilities, seller="home")
        world.seed([initial_actor(1)], [(item, 1)])
        before = world.store.snapshot()
        assert world.start("unsupported", 1, "ACQUIRE", "item")["reason"] == reason
        assert world.store.snapshot() == before
        assert not purchased(world)
        validate_world(world)


def test_missing_object_is_not_created_from_acquire_intent(tmp_path):
    with ContinuityWorld(tmp_path / "missing.sqlite", acquire_enabled=True) as world:
        seed_acquire(world)
        before = world.store.snapshot()
        assert world.start("unknown", 1, "ACQUIRE", "unknown-game")["reason"] == "OBJECT_NOT_FOUND"
        assert world.store.snapshot() == before


@pytest.mark.parametrize("interruption,reason", [
    ("unavailable", "OBJECT_UNAVAILABLE"), ("competing_purchase", "OUT_OF_STOCK"),
])
def test_mid_travel_failure_preserves_real_travel_and_never_half_purchases(
        tmp_path, interruption, reason):
    with ContinuityWorld(tmp_path / "failure.sqlite", acquire_enabled=True) as world:
        seed_acquire(world, seller="office", stock=1, actors=2)
        assert world.start("acquire", 1, "ACQUIRE", "game_a")["accepted"]
        assert world.advance("midway", 7)["accepted"]
        if interruption == "unavailable":
            assert world.set_available("off", "game_a", False)["accepted"]
        else:
            assert world.act("other-buyer", 2, "BUY", "game_a")["accepted"]
        assert world.store.get_commitment("acquire")["status"] == "ACTIVE"
        assert world.advance("arrival", 15)["accepted"]
        assert world.advance("settle", 15)["accepted"]
        commitment = world.store.get_commitment("acquire")
        assert commitment["status"] == "FAILED" and commitment["failure_reason"] == reason
        assert commitment["elapsed_min"] == 15
        actor = world.store.actor(1)
        assert (world.minute, actor["location"], actor["hunger_milli"], actor["energy_milli"]) == (
            15, "office", 815, 685,
        )
        assert actor["money_cents"] == 10000
        assert world.store.link(1, "game_a")["quantity"] == 0
        assert not any(event["payload"]["actor_id"] == 1 for event in purchased(world))
        assert world.store.object("game_a")["stock"] == (1 if interruption == "unavailable" else 0)
        validate_world(world)


def test_purchase_event_failure_rolls_back_trade_preserving_arrival(tmp_path, monkeypatch):
    with ContinuityWorld(tmp_path / "atomic.sqlite", acquire_enabled=True) as world:
        seed_acquire(world, seller="office")
        world.start("acquire", 1, "ACQUIRE", "game_a")
        world.advance("arrival", 15)
        before = world.store.snapshot()
        events = world.store.events()
        original = world.store.emit

        def fail_purchase(command, kind, payload):
            if kind == "PURCHASED":
                raise OSError("synthetic purchase ledger failure")
            return original(command, kind, payload)

        monkeypatch.setattr(world.store, "emit", fail_purchase)
        with pytest.raises(OSError, match="synthetic"):
            world.advance("settle", 15)
        assert world.store.snapshot() == before
        assert world.store.events() == events
        assert world.store.db.execute("SELECT 1 FROM commands WHERE id='settle'").fetchone() is None
        assert world.minute == 15 and world.store.actor(1)["location"] == "office"
        monkeypatch.setattr(world.store, "emit", original)
        assert world.advance("settle", 15)["accepted"]
        assert len(purchased(world)) == 1
        validate_world(world)


def test_domain_rejection_after_purchase_mutations_is_atomic(tmp_path, monkeypatch):
    with ContinuityWorld(tmp_path / "domain-atomic.sqlite", acquire_enabled=True) as world:
        seed_acquire(world, seller="office")
        world.start("acquire", 1, "ACQUIRE", "game_a")
        world.advance("arrival", 15)
        actor = world.store.actor(1)
        stock = world.store.object("game_a")["stock"]
        link = world.store.link(1, "game_a")
        original = world._buy

        def reject_after_purchase(actor_id, target):
            original(actor_id, target)
            raise Rejected("SYNTHETIC_AFTER_PURCHASE_REJECTION")

        monkeypatch.setattr(world, "_buy", reject_after_purchase)
        assert world.advance("settle", 15)["accepted"]
        commitment = world.store.get_commitment("acquire")
        assert commitment["status"] == "FAILED"
        assert commitment["failure_reason"] == "SYNTHETIC_AFTER_PURCHASE_REJECTION"
        assert world.store.actor(1) == actor
        assert world.store.object("game_a")["stock"] == stock
        assert world.store.link(1, "game_a") == link
        assert not purchased(world)
        assert world.minute == 15 and world.store.actor(1)["location"] == "office"
        validate_world(world)


def test_request_replay_and_conflict_do_not_repeat_transaction(tmp_path):
    with ContinuityWorld(tmp_path / "replay.sqlite", acquire_enabled=True) as world:
        seed_acquire(world)
        first = world.start("same", 1, "ACQUIRE", "game_a")
        before = world.store.snapshot()
        events = world.store.events()
        replay = world.start("same", 1, "ACQUIRE", "game_a")
        assert replay == {**first, "replayed": True}
        conflict = world.start("same", 1, "PLAY", "game_a")
        assert not conflict["accepted"] and conflict["reason"] == "REQUEST_ID_REUSE"
        assert world.store.snapshot() == before and world.store.events() == events
        assert len(purchased(world)) == 1
        validate_world(world)


def test_independent_sqlite_connections_compete_for_one_stock(tmp_path):
    """仅证明本 SQLite BEGIN IMMEDIATE 参考实现，不声称分布式 exactly-once。"""
    path = tmp_path / "stock-race.sqlite"
    with ContinuityWorld(path, acquire_enabled=True) as world:
        seed_acquire(world, stock=1, actors=2)
    barrier = Barrier(2)

    def acquire(actor_id):
        with ContinuityWorld(path) as world:
            barrier.wait(timeout=5)
            return world.start(f"acquire-{actor_id}", actor_id, "ACQUIRE", "game_a")

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(acquire, (1, 2)))
    assert sum(result["accepted"] for result in results) == 1
    assert {result["reason"] for result in results} == {"ACCEPTED", "OUT_OF_STOCK"}
    with ContinuityWorld(path) as world:
        assert world.store.object("game_a")["stock"] == 0
        assert sum(world.store.link(actor, "game_a")["quantity"] for actor in (1, 2)) == 1
        assert sum(world.store.actor(actor)["money_cents"] for actor in (1, 2)) == 17000
        assert len(purchased(world)) == 1
        assert len(world.store.snapshot()["commitments"]) == 1
        validate_world(world)


def test_independent_sqlite_connections_replaying_one_request_have_one_effect(tmp_path):
    path = tmp_path / "request-race.sqlite"
    with ContinuityWorld(path, acquire_enabled=True) as world:
        seed_acquire(world, stock=1)
    barrier = Barrier(2)

    def acquire(_):
        with ContinuityWorld(path) as world:
            barrier.wait(timeout=5)
            return world.start("same", 1, "ACQUIRE", "game_a")

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(acquire, range(2)))
    assert all(result["accepted"] for result in results)
    assert sum(result["replayed"] for result in results) == 1
    with ContinuityWorld(path) as world:
        assert world.store.object("game_a")["stock"] == 0
        assert world.store.actor(1)["money_cents"] == 7000
        assert world.store.link(1, "game_a")["quantity"] == 1
        assert len(purchased(world)) == 1
        validate_world(world)
