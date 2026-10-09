"""M2 独立工程场景：只用脚本意图、共享规则和隔离的 SQLite 世界。"""
from __future__ import annotations

import json
import platform
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from typing import Callable

from .engine import ContinuityWorld
from .m2_acquire import M2DecisionRunner, ScriptedM2Client, finish_m2_commitment
from .models import ObjectDefinition, canonical_json, digest, initial_actor
from .validation import validate_world

M2_VALIDATION_VERSION = "M2_ACQUIRE_OFFLINE_V1"
SESSION_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
                    + "\n", encoding="utf-8")


def _seed(world: ContinuityWorld, *, money: int = 300_000, stock: int = 100,
          actors: int = 1, actor_two_location: str = "home") -> None:
    """不调用或改写旧 fixture；第五对象仅属于本 M2 合成场景。"""
    people = [initial_actor(1, money_cents=money)]
    people.extend(initial_actor(i, money_cents=300_000, location=actor_two_location)
                  for i in range(2, actors + 1))
    world.seed(people, [
        (ObjectDefinition("food_bread", "测试面包", "FOOD", ("edible", "purchasable"),
                          1200, 320, 350, 30, aliases=("bread",)), 1000),
        (ObjectDefinition("food_meal", "测试餐食", "FOOD", ("edible", "purchasable"),
                          2000, 650, 600, 30, aliases=("meal",)), 1000),
        (ObjectDefinition("game_a", "测试游戏", "GAME", ("playable", "purchasable"),
                          price_cents=3000, duration_min=45, seller="home"), stock),
        (ObjectDefinition("series_a", "测试连续剧", "SERIES", ("watchable",),
                          duration_min=30, episodes=120, aliases=("测试剧",)), 0),
        (ObjectDefinition("game_office", "M2合成异地游戏", "GAME",
                          ("playable", "purchasable"), price_cents=4200,
                          duration_min=20, seller="office", aliases=("office_game",)), stock),
    ])


class _Case:
    def __init__(self, folder: Path, name: str, **fixture: object):
        self.folder = folder / name
        self.folder.mkdir()
        self.path = self.folder / "world.sqlite"
        self.world = ContinuityWorld(self.path, acquire_enabled=True)
        try:
            _seed(self.world, **fixture)
            self.initial = self.world.store.snapshot()
            self.data: dict = {
                "case": name, "result": "RUNNING", "configuration": self.world.activity_configuration,
                "initial_state": self.initial, "initial_state_hash": digest(self.initial),
                "checkpoints": [], "rule_results": [], "recovery": [],
                "fake_decision_calls": 0, "provider_requests": 0, "llm_calls": 0,
            }
            self.mark("INITIAL")
        except BaseException:
            self.world.close()
            raise

    def mark(self, label: str, commitment_id: str | None = None) -> None:
        checkpoint = {"label": label, "minute": self.world.minute,
                      "actors": self.world.store.snapshot()["actors"],
                      "objects": self.world.store.snapshot()["objects"],
                      "links": self.world.store.snapshot()["links"]}
        if commitment_id is not None:
            checkpoint["commitment"] = self.world.store.get_commitment(commitment_id)
        self.data["checkpoints"].append(checkpoint)
        self.persist()

    def rule(self, label: str, result: dict) -> dict:
        self.data["rule_results"].append({"label": label, **result})
        self.persist()
        return result

    def reopen(self, label: str) -> None:
        before = self.world.store.snapshot()
        configuration = self.world.activity_configuration
        self.world.close()
        self.world = ContinuityWorld(self.path)
        after = self.world.store.snapshot()
        assert before == after
        assert configuration == self.world.activity_configuration
        self.data["recovery"].append({"boundary": label, "result": "PASS",
                                      "state_hash": digest(after),
                                      "configuration": self.world.activity_configuration})
        self.mark("REOPEN_" + label)

    async def fake(self, request_id: str, activity: str, target: str) -> dict:
        client = ScriptedM2Client([canonical_json({"activity": activity, "target": target})])
        runner = M2DecisionRunner(self.world, client)
        result = await runner.decide(request_id)
        assert client.call_count == 1
        assert client.provider_request_count == 0
        self.data["fake_decision_calls"] += client.call_count
        self.rule(request_id, result)
        return result["result"]

    def persist(self) -> None:
        _write_json(self.folder / "case.json", self.data)

    def finish(self) -> dict:
        try:
            self.data["final_state"] = self.world.store.snapshot()
            self.data["events"] = self.world.store.events()
            self.data["events_hash"] = digest(self.data["events"])
            self.data["validation"] = validate_world(self.world)
            self.data["final_state_hash"] = digest(self.data["final_state"])
        except Exception as error:
            self.data["result"] = "FAIL"
            self.data["validation_error_type"] = type(error).__name__
        finally:
            try:
                self.persist()
            finally:
                self.world.close()
        return self.data


def _accepted(result: dict) -> None:
    assert result["accepted"]


def _rejected(result: dict, reason: str) -> None:
    assert not result["accepted"]
    assert result["reason"] == reason


def _purchase_count(world: ContinuityWorld, *, actor_id: int | None = None) -> int:
    return sum(event["kind"] == "PURCHASED" and
               (actor_id is None or event["payload"]["actor_id"] == actor_id)
               for event in world.store.events())


def _finish(case: _Case, commitment_id: str) -> dict:
    progress = finish_m2_commitment(case.world, commitment_id)
    case.data.setdefault("deterministic_progress", []).append(progress)
    case.persist()
    return case.world.store.get_commitment(commitment_id)


def _no_purchase(case: _Case, target: str) -> None:
    assert case.world.store.actor(1)["money_cents"] == case.initial["actors"][0]["money_cents"]
    assert case.world.store.link(1, target)["quantity"] == 0
    assert _purchase_count(case.world, actor_id=1) == 0


async def _closed_loop(case: _Case) -> None:
    world = case.world
    initial_quantity = world.store.link(1, "game_a")["quantity"]
    stock_before = world.store.object("game_a")["stock"]
    assert initial_quantity == 0
    result = await case.fake("acquire-game", "ACQUIRE", "game_a")
    _accepted(result)
    commitment_id = result["commitment_id"]
    completed = _finish(case, commitment_id)
    assert completed["status"] == "COMPLETED"
    assert completed["target"] == "game_a"
    assert world.minute == 0
    assert world.store.actor(1)["money_cents"] == 297_000
    assert world.store.object("game_a")["stock"] == 99
    assert world.store.link(1, "game_a")["quantity"] == 1
    assert world.store.link(1, "game_a")["play_minutes"] == 0
    assert _purchase_count(world) == 1
    automatic_play = any(c["activity"] == "PLAY" for c in world.store.snapshot()["commitments"])
    case.mark("ACQUIRE_COMPLETED_NO_PLAY", commitment_id)
    case.reopen("PURCHASE_COMMITTED")
    assert case.world.store.get_commitment(commitment_id)["status"] == "COMPLETED"
    case.reopen("COMPLETED_QUERY")
    result = await case.fake("play-game", "PLAY", "game_a")
    _accepted(result)
    played = _finish(case, result["commitment_id"])
    assert played["status"] == "COMPLETED"
    assert case.world.minute == 45
    assert case.world.store.link(1, "game_a")["play_minutes"] == 45
    assert case.world.store.actor(1)["money_cents"] == 297_000
    assert _purchase_count(case.world) == 1
    case.mark("SEPARATE_PLAY_COMPLETED", result["commitment_id"])
    case.data["closed_loop"] = {
        "canonical_object_id": completed["target"], "initial_quantity": initial_quantity,
        "money_before_cents": case.initial["actors"][0]["money_cents"],
        "money_after_cents": case.world.store.actor(1)["money_cents"],
        "seller_stock_before": stock_before,
        "seller_stock_after": case.world.store.object("game_a")["stock"],
        "owned_quantity": case.world.store.link(1, "game_a")["quantity"],
        "acquire_minutes": completed["elapsed_min"], "separate_play_minutes": played["elapsed_min"],
        "play_legal": result["accepted"] and played["status"] == "COMPLETED",
        "automatic_play": automatic_play, "purchase_events": _purchase_count(case.world),
    }


async def _remote(case: _Case) -> None:
    case.reopen("BEFORE_DEPARTURE")
    result = await case.fake("remote", "ACQUIRE", "office_game")
    _accepted(result)
    commitment_id = result["commitment_id"]
    case.mark("MOVE_BEFORE_TIME_ADVANCE", commitment_id)
    case.reopen("MOVE_NOT_STARTED")
    _accepted(case.rule("travel-five", case.world.advance("travel-five", 5)))
    assert case.world.store.get_commitment(commitment_id)["remaining_min"] == 10
    case.mark("MID_MOVE", commitment_id)
    case.reopen("MID_MOVE")
    _accepted(case.rule("arrive", case.world.advance("arrive", 15)))
    arrived = case.world.store.get_commitment(commitment_id)
    assert arrived["status"] == "ACTIVE" and arrived["phase"] == "BUY"
    assert arrived["remaining_min"] == 0
    assert case.world.store.actor(1)["location"] == "office"
    _no_purchase(case, "game_office")
    case.mark("ARRIVAL_BEFORE_PURCHASE", commitment_id)
    case.reopen("ARRIVAL_BEFORE_PURCHASE")
    completed = _finish(case, commitment_id)
    assert completed["status"] == "COMPLETED"
    assert completed["target"] == "game_office"
    assert case.world.minute == 15
    actor = case.world.store.actor(1)
    assert actor["money_cents"] == 295_800
    assert actor["hunger_milli"] == 815 and actor["energy_milli"] == 685
    assert case.world.store.object("game_office")["stock"] == 99
    assert case.world.store.link(1, "game_office")["quantity"] == 1
    assert _purchase_count(case.world) == 1
    case.mark("REMOTE_PURCHASE_COMPLETED", commitment_id)
    case.reopen("REMOTE_PURCHASE_COMMITTED")
    initial_actor_state = case.initial["actors"][0]
    initial_object = next(obj for obj in case.initial["objects"] if obj["object_id"] == "game_office")
    case.data["remote_acquire"] = {
        "canonical_object_id": completed["target"], "status": completed["status"],
        "money_before_cents": initial_actor_state["money_cents"],
        "money_after_cents": case.world.store.actor(1)["money_cents"],
        "seller_stock_before": initial_object["stock"],
        "seller_stock_after": case.world.store.object("game_office")["stock"],
        "owned_quantity": case.world.store.link(1, "game_office")["quantity"],
        "minutes": case.world.minute - case.initial["minute"],
        "location": case.world.store.actor(1)["location"],
        "hunger_before": initial_actor_state["hunger_milli"],
        "hunger_after": case.world.store.actor(1)["hunger_milli"],
        "energy_before": initial_actor_state["energy_milli"],
        "energy_after": case.world.store.actor(1)["energy_milli"],
    }


def _start_rejection(case: _Case, target: str, reason: str) -> None:
    result = case.rule("rejected-acquire", case.world.start("rejected-acquire", 1, "ACQUIRE", target))
    _rejected(result, reason)
    _no_purchase(case, target)
    assert case.world.minute == 0
    case.mark("REJECTED_WITHOUT_EFFECTS")
    case.reopen("START_REJECTED")


def _owned(case: _Case) -> None:
    _accepted(case.rule("legitimate-setup-buy", case.world.act("legitimate-setup-buy", 1, "BUY", "game_a")))
    before = case.world.store.snapshot()
    _rejected(case.rule("owned-acquire", case.world.start("owned-acquire", 1, "ACQUIRE", "game_a")),
              "ALREADY_OWNED")
    assert case.world.store.snapshot() == before
    assert _purchase_count(case.world) == 1
    case.mark("ALREADY_OWNED_NO_SECOND_PURCHASE")


def _travel_failure(case: _Case, *, stock_competitor: bool) -> None:
    world = case.world
    _accepted(case.rule("travel-acquire", world.start("travel-acquire", 1, "ACQUIRE", "game_office")))
    _accepted(case.rule("travel-five", world.advance("travel-five", 5)))
    if stock_competitor:
        _accepted(case.rule("competitor-buy", world.act("competitor-buy", 2, "BUY", "game_office")))
        reason = "OUT_OF_STOCK"
    else:
        _accepted(case.rule("delist", world.set_available("delist", "game_office", False)))
        reason = "OBJECT_UNAVAILABLE"
    assert world.store.get_commitment("travel-acquire")["status"] == "ACTIVE"
    _accepted(case.rule("arrive", world.advance("arrive", 15)))
    assert world.store.get_commitment("travel-acquire")["phase"] == "BUY"
    case.mark("FAILED_PURCHASE_NOT_YET_ATTEMPTED", "travel-acquire")
    final = _finish(case, "travel-acquire")
    assert final["status"] == "FAILED" and final["failure_reason"] == reason
    assert world.minute == 15
    actor = world.store.actor(1)
    assert actor["location"] == "office" and actor["hunger_milli"] == 815
    assert actor["energy_milli"] == 685
    _no_purchase(case, "game_office")
    assert world.store.object("game_office")["stock"] == (0 if stock_competitor else 100)
    case.mark("FAILED_WITH_TRAVEL_PRESERVED", "travel-acquire")
    case.reopen("FAILED_AFTER_TRAVEL")
    before = case.world.store.snapshot()
    final_again = _finish(case, "travel-acquire")
    assert final_again == final and case.world.store.snapshot() == before


def _cancel(case: _Case, *, at_arrival: bool) -> None:
    world = case.world
    _accepted(case.rule("cancel-acquire", world.start("cancel-acquire", 1, "ACQUIRE", "game_office")))
    until = 15 if at_arrival else 5
    _accepted(case.rule("travel", world.advance("travel", until)))
    case.mark("BEFORE_CANCEL", "cancel-acquire")
    _accepted(case.rule("cancel", world.control("cancel", 1, "CANCEL")))
    case.reopen("CANCELLED_BUY" if at_arrival else "CANCELLED_MOVE")
    _accepted(case.rule("later", case.world.advance("later", until + 20)))
    assert case.world.store.get_commitment("cancel-acquire")["status"] == "CANCELLED"
    _no_purchase(case, "game_office")
    assert case.world.store.object("game_office")["stock"] == 100
    case.mark("CANCELLED_NO_HIDDEN_PURCHASE", "cancel-acquire")


def _pause(case: _Case, *, at_arrival: bool) -> None:
    world = case.world
    _accepted(case.rule("pause-acquire", world.start("pause-acquire", 1, "ACQUIRE", "game_office")))
    until = 15 if at_arrival else 5
    _accepted(case.rule("travel", world.advance("travel", until)))
    _accepted(case.rule("pause", world.control("pause", 1, "PAUSE")))
    case.reopen("PAUSED_BUY" if at_arrival else "PAUSED_MOVE")
    _accepted(case.rule("pause-time", case.world.advance("pause-time", until + 7)))
    paused = case.world.store.get_commitment("pause-acquire")
    assert paused["status"] == "PAUSED"
    assert paused["remaining_min"] == (0 if at_arrival else 10)
    _no_purchase(case, "game_office")
    case.mark("PAUSED_NO_PURCHASE", "pause-acquire")
    _accepted(case.rule("resume", case.world.control("resume", 1, "RESUME")))
    completed = _finish(case, "pause-acquire")
    assert completed["status"] == "COMPLETED"
    assert case.world.minute == 22
    assert _purchase_count(case.world) == 1
    case.mark("RESUMED_COMPLETED", "pause-acquire")


def _replay(case: _Case) -> None:
    world = case.world
    initial = world.start("idempotent", 1, "ACQUIRE", "game_office")
    _accepted(case.rule("first-start", initial))
    before = world.store.snapshot()
    events = world.store.events()
    replay = case.rule("start-replay", world.start("idempotent", 1, "ACQUIRE", "game_office"))
    assert replay["replayed"] and world.store.snapshot() == before
    assert world.store.events() == events
    conflict = case.rule("conflicting-target", world.start("idempotent", 1, "ACQUIRE", "game_a"))
    _rejected(conflict, "REQUEST_ID_REUSE")
    assert world.store.snapshot() == before and world.store.events() == events
    _accepted(case.rule("arrival", world.advance("arrival", 15)))
    final = _finish(case, "idempotent")
    assert final["status"] == "COMPLETED"
    case.reopen("COMPLETED_REQUEST_REPLAY")
    before = case.world.store.snapshot()
    events = case.world.store.events()
    replay = case.rule("completed-start-replay", case.world.start("idempotent", 1, "ACQUIRE", "game_office"))
    assert replay["replayed"]
    assert replay["commitment_status"] == initial["commitment_status"]
    assert case.world.store.get_commitment("idempotent")["status"] == "COMPLETED"
    assert case.world.store.snapshot() == before and case.world.store.events() == events
    assert _purchase_count(case.world) == 1
    case.mark("REPLAY_RETURNS_STORED_RESULT_NO_EFFECTS", "idempotent")


def _alias(case: _Case) -> None:
    world = case.world
    _accepted(case.rule("alias-acquire", world.start("alias-acquire", 1, "ACQUIRE", "office_game")))
    assert world.store.get_commitment("alias-acquire")["target"] == "game_office"
    final = _finish(case, "alias-acquire")
    assert final["status"] == "COMPLETED"
    before = world.store.snapshot()
    _rejected(case.rule("alias-repeat", world.start("alias-repeat", 1, "ACQUIRE", "M2合成异地游戏")),
              "ALREADY_OWNED")
    assert world.store.snapshot() == before
    assert world.store.link(1, "game_office")["quantity"] == 1
    assert _purchase_count(world) == 1
    case.data["canonical_object_id"] = "game_office"
    case.mark("ALIAS_SINGLE_OWNERSHIP", "alias-acquire")


def _concurrent(case: _Case) -> None:
    barrier = Barrier(2)

    def buyer(actor_id: int) -> dict:
        with ContinuityWorld(case.path) as world:
            barrier.wait(timeout=10)
            return world.start(f"race-{actor_id}", actor_id, "ACQUIRE", "game_a")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(buyer, (1, 2)))
    for index, result in enumerate(results, 1):
        case.rule(f"distinct-connection-race-{index}", result)
    assert sum(result["accepted"] for result in results) == 1
    assert sorted(result["reason"] for result in results) == ["ACCEPTED", "OUT_OF_STOCK"]
    assert _purchase_count(case.world) == 1
    assert case.world.store.object("game_a")["stock"] == 0
    assert sum(case.world.store.link(actor_id, "game_a")["quantity"] for actor_id in (1, 2)) == 1
    assert sum(case.world.store.actor(actor_id)["money_cents"] for actor_id in (1, 2)) == 597_000
    case.mark("SQLITE_DISTINCT_CONNECTION_SINGLE_PURCHASE")
    case.reopen("STOCK_RACE_COMMITTED")


def _configuration(case: _Case) -> None:
    case.reopen("CONFIGURATION_PERSISTED")
    try:
        other = ContinuityWorld(case.path, acquire_enabled=False)
    except ValueError:
        case.data["configuration_mismatch"] = "REJECTED"
    else:
        other.close()
        raise AssertionError("configuration mismatch was not rejected")
    case.mark("CONFIGURATION_MISMATCH_FAIL_CLOSED")


async def run_m2_validation(output_root: Path, session: str) -> dict:
    """排他创建 session；所有失败产物保留，不改写任何原实验目录。"""
    if not isinstance(session, str) or not SESSION_PATTERN.fullmatch(session):
        raise ValueError("session must be a short safe identifier")
    output = Path(output_root).resolve() / session
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(exist_ok=False)
    try:
        completed = subprocess.run(["git", "rev-parse", "HEAD"],
                                   cwd=Path(__file__).resolve().parents[3],
                                   capture_output=True, text=True, check=True, timeout=10)
        head = completed.stdout.strip()
        if not re.fullmatch(r"[0-9a-f]{40}", head):
            head = "NOT_AVAILABLE"
    except (OSError, subprocess.SubprocessError):
        head = "NOT_AVAILABLE"
    try:
        status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=normal"],
                                cwd=Path(__file__).resolve().parents[3],
                                capture_output=True, text=True, check=True, timeout=10)
        git_dirty: bool | str = bool(status.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        git_dirty = "NOT_AVAILABLE"
    provenance = {"git_head": head, "git_dirty": git_dirty,
                  "python_version": platform.python_version()}
    _write_json(output / "configuration.json", {
        "version": M2_VALIDATION_VERSION, "mode": "offline",
        "world_configuration": {"version": "M2_ACQUIRE_V1", "acquire_enabled": True},
        "acquire_production_default": "DISABLED", "d02_product_semantics_approved": False,
        "fixture": "M2_SYNTHETIC_FIVE_OBJECTS", "provider_requests": 0, "llm_calls": 0,
        "historical_sessions_read": False, "historical_sessions_modified": False,
        "provenance": provenance,
    })
    specifications: list[tuple[str, Callable, dict]] = [
        ("same_seller_acquire_restart_play", _closed_loop, {}),
        ("remote_acquire_all_restart_boundaries", _remote, {}),
        ("insufficient_funds", lambda c: _start_rejection(c, "game_a", "INSUFFICIENT_FUNDS"), {"money": 2999}),
        ("out_of_stock", lambda c: _start_rejection(c, "game_a", "OUT_OF_STOCK"), {"stock": 0}),
        ("already_owned", _owned, {}),
        ("not_purchasable", lambda c: _start_rejection(c, "series_a", "CAPABILITY_MISMATCH"), {}),
        ("consumable_excluded", lambda c: _start_rejection(c, "food_bread", "UNSUPPORTED_ACQUIRE_OBJECT"), {}),
        ("delisted_during_travel", lambda c: _travel_failure(c, stock_competitor=False), {}),
        ("stock_exhausted_during_travel", lambda c: _travel_failure(c, stock_competitor=True),
         {"stock": 1, "actors": 2, "actor_two_location": "office"}),
        ("cancel_during_move", lambda c: _cancel(c, at_arrival=False), {}),
        ("cancel_at_buy", lambda c: _cancel(c, at_arrival=True), {}),
        ("paused_move_restart", lambda c: _pause(c, at_arrival=False), {}),
        ("paused_buy_restart", lambda c: _pause(c, at_arrival=True), {}),
        ("request_replay_and_conflict", _replay, {}),
        ("canonical_alias", _alias, {}),
        ("concurrent_last_stock", _concurrent, {"stock": 1, "actors": 2}),
        ("persisted_opt_in_configuration", _configuration, {}),
    ]
    cases = []
    for name, execute, fixture in specifications:
        try:
            case = _Case(output, name, **fixture)
        except Exception as error:
            # 初始化失败也留档；不重建 world，不覆盖部分初始化的证据。
            failed = {"case": name, "result": "FAIL", "error_type": type(error).__name__,
                      "failure_stage": "WORLD_INITIALIZATION", "fake_decision_calls": 0,
                      "provider_requests": 0, "llm_calls": 0}
            (output / name).mkdir(exist_ok=True)
            _write_json(output / name / "case.json", failed)
            cases.append(failed)
            continue
        try:
            result = execute(case)
            if result is not None:
                await result
            case.data["result"] = "PASS"
        except Exception as error:
            # 只保存错误分类，绝不回显未知文本、prompt 或敏感环境。
            case.data["result"] = "FAIL"
            case.data["error_type"] = type(error).__name__
        finally:
            cases.append(case.finish())
    overall = "PASS" if all(case["result"] == "PASS" for case in cases) else "FAIL"
    summary = {
        "version": M2_VALIDATION_VERSION, "mode": "offline", "session": session,
        "result": overall, "cases": [{"case": c["case"], "result": c["result"]} for c in cases],
        "passed": sum(c["result"] == "PASS" for c in cases), "total": len(cases),
        "fake_decision_calls": sum(c["fake_decision_calls"] for c in cases),
        "provider_requests": 0, "llm_calls": 0, "real_provider_executed": False,
        "d02_product_semantics_approved": False, "human_behavior_appropriateness": "NOT_TESTED",
        "concurrency_scope": "SQLite distinct connections; not distributed exactly-once",
        "closed_loop": cases[0].get("closed_loop"),
        "remote_acquire": cases[1].get("remote_acquire"),
        "historical_sessions_read": False, "historical_sessions_modified": False,
        "provenance": provenance,
    }
    _write_json(output / "summary.json", summary)
    lines = ["# M2 合法获取与使用：独立离线工程报告", "",
             f"版本：{M2_VALIDATION_VERSION}；模式：offline；结果：{overall}。", "",
             "本实验仅使用合成 fixture、fake 高层提案及确定性规则。没有真实 provider，"
             "没有读取原 Q6.2/M1.5 session；每个场景均使用新的 SQLite world。", "",
             "| 场景 | 结果 |", "| --- | --- |"]
    lines.extend(f"| {case['case']} | {case['result']} |" for case in cases)
    lines += ["", f"执行 HEAD：`{provenance['git_head']}`；"
              f"git_dirty：`{provenance['git_dirty']}`；"
              f"Python：`{provenance['python_version']}`。",
              "git_dirty=true 为开发工作树执行，不能视为已冻结提交的正式验收。", ""]
    if summary["closed_loop"] is not None:
        loop = summary["closed_loop"]
        lines += [f"同地闭环 `{loop['canonical_object_id']}`：拥有量 "
                  f"{loop['initial_quantity']} → {loop['owned_quantity']}；余额 "
                  f"{loop['money_before_cents']} → {loop['money_after_cents']} cents；卖家库存 "
                  f"{loop['seller_stock_before']} → {loop['seller_stock_after']}；"
                  f"ACQUIRE {loop['acquire_minutes']} 分钟，独立 PLAY "
                  f"{loop['separate_play_minutes']} 分钟；合法 PLAY：{loop['play_legal']}；"
                  f"自动 PLAY：{loop['automatic_play']}；购买事件：{loop['purchase_events']}。", ""]
    else:
        lines += ["同地获取→重启→独立 PLAY 闭环未完成；不得宣称闭环通过。", ""]
    if summary["remote_acquire"] is not None:
        remote = summary["remote_acquire"]
        lines += [f"异地获取 `{remote['canonical_object_id']}` 终态：{remote['status']}；"
                  f"耗时 {remote['minutes']} 分钟，到达 `{remote['location']}`；余额 "
                  f"{remote['money_before_cents']} → {remote['money_after_cents']} cents；库存 "
                  f"{remote['seller_stock_before']} → {remote['seller_stock_after']}；拥有量 "
                  f"{remote['owned_quantity']}；饥饿 {remote['hunger_before']} → "
                  f"{remote['hunger_after']}；精力 {remote['energy_before']} → "
                  f"{remote['energy_after']}。", ""]
    else:
        lines += ["异地获取场景未完成；具体失败与阶段证据见对应 case.json。", ""]
    lines += ["", f"场景通过：{summary['passed']}/{summary['total']}；"
              f"fake 决策次数：{summary['fake_decision_calls']}；真实模型请求：0。", "",
              "本版本合同：同地 ACQUIRE 不增加交易或旅行时间；异地需按旅行规则推进，"
              "到达后重新检查库存、余额、可用性。失败旅行的已发生时间、位置和需求变化"
              "不得回滚；失败购买不得扣钱或赠送物品。完成 ACQUIRE 不自动 PLAY，"
              "必须由下一次明确提案开始。各性质是否实际通过以场景结果为准。", "",
              "完整钱、库存、拥有量、事件、状态版本、commitment 与恢复边界见各 case.json。"
              "所有场景的 SQLite 文件和失败证据均保留。请求重放返回历史启动结果，"
              "最新 commitment 终态通过持久存储查询；两者不能混为同一时点。", "",
              "此报告不替代 pytest、完整 CI、AS2 或历史冻结验收，"
              "不证明真人行为适当性或长期自主生活。并发保证限当前 SQLite 参考实现。", "",
              "ACQUIRE_PRODUCTION_DEFAULT = DISABLED；D02_PRODUCT_SEMANTICS_APPROVED = NO；"
              "HUMAN_BEHAVIOR_APPROPRIATENESS = NOT_TESTED；REAL_PROVIDER_REQUESTS_THIS_TASK = 0。", "",
              "D-02 的重复购买、失败继续策略、自动旅行、动态价格/库存、优先级和主动积累语义"
              "仍待人工批准；D-09 仍待审核。旧 Q6.2 NO_CLEAR_DIFFERENCE 和"
              "M1.5 EXPLORATORY_POST_HOC 不由本工程实验改写。", ""]
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary
