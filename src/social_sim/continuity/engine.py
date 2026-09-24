"""参数化规则与滚动活动执行。一次意图不等于一次完成；实际用时才能推进进度。"""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from dataclasses import asdict

from .models import (TIMED_ACTIVITIES, ObjectDefinition, Rejected, RuleParameters, alias_key,
                     canonical_json, digest, identity, integer)
from .store import StateStore


class ContinuityWorld:
    def __init__(self, path: str | Path, parameters: RuleParameters | None = None) -> None:
        self.store = StateStore(path)
        try:
            with self.store.transaction():
                row = self.store.db.execute("SELECT value FROM meta WHERE key='rule_parameters'").fetchone()
                if row:
                    saved = RuleParameters(**json.loads(row[0]))
                    if parameters is not None and parameters != saved:
                        raise ValueError("rule parameters changed; explicit migration required")
                    self.parameters = saved
                else:
                    self.parameters = parameters or RuleParameters()
                    self.store.db.execute("INSERT INTO meta VALUES('rule_parameters',?)",
                                          (canonical_json(asdict(self.parameters)),))
        except BaseException:
            self.store.close()
            raise
        self._request = ""

    def close(self) -> None:
        self.store.close()

    def __enter__(self) -> ContinuityWorld:
        return self

    def __exit__(self, *args) -> None:
        self.close()

    @property
    def minute(self) -> int:
        return self.store.minute

    def seed(self, actors: list[dict], objects: list[tuple[ObjectDefinition, int]],
             locations: tuple[str, ...] = ("home", "restaurant", "office", "park")) -> None:
        """只初始化空世界；同一初始配置重启时绝不重置余额、进度或库存。"""
        fixture = {"actors": actors, "objects": [(o.to_dict(), n) for o, n in objects],
                   "locations": locations}
        fingerprint = digest(fixture)
        with self.store.transaction():
            prior = self.store.db.execute("SELECT value FROM meta WHERE key='fixture'").fetchone()
            if prior:
                if prior[0] != fingerprint:
                    raise ValueError("fixture mismatch; use an explicit migration/new world")
                return
            if not locations or len(set(locations)) != len(locations):
                raise ValueError("locations must be nonempty and unique")
            for actor in actors:
                self._validate_actor(actor)
                if actor["location"] not in locations:
                    raise ValueError("unknown initial location")
                self.store.db.execute("INSERT INTO actors VALUES(?,?)",
                                      (actor["actor_id"], canonical_json(actor)))
            for obj, stock in objects:
                integer(stock, "stock")
                if obj.seller not in locations:
                    raise ValueError("seller must be a valid location")
                self.store.db.execute("INSERT INTO objects(id,data,stock) VALUES(?,?,?)",
                                      (obj.object_id, canonical_json(obj.to_dict()), stock))
                for name in {obj.object_id, obj.name, *obj.aliases}:
                    key = alias_key(name)
                    row = self.store.db.execute("SELECT object_id FROM aliases WHERE name=?", (key,)).fetchone()
                    if row and row[0] != obj.object_id:
                        raise ValueError("ambiguous object alias")
                    self.store.db.execute("INSERT OR IGNORE INTO aliases VALUES(?,?)", (key, obj.object_id))
            self.store.db.execute("INSERT INTO meta VALUES('fixture',?)", (fingerprint,))
            self.store.db.execute("INSERT INTO meta VALUES('locations',?)", (canonical_json(locations),))
            self.store.emit("seed", "WORLD_CREATED", {"fixture": fingerprint, "initial": self.store.snapshot()})

    @staticmethod
    def _validate_actor(actor: dict) -> None:
        integer(actor["actor_id"], "actor_id", 1)
        identity(actor["location"])
        for name in ("money_cents", "calories_kcal", "work_minutes", "version"):
            integer(actor[name], name)
        for name in ("hunger_milli", "energy_milli"):
            integer(actor[name], name, high=1000)

    def _actor(self, actor_id: int) -> dict:
        try:
            return self.store.actor(actor_id)
        except KeyError as error:
            raise Rejected("ACTOR_NOT_FOUND") from error

    def resolve(self, target: str) -> str:
        row = self.store.db.execute("SELECT object_id FROM aliases WHERE name=?", (alias_key(target),)).fetchone()
        if row is None:
            raise Rejected("OBJECT_NOT_FOUND")
        return row[0]

    def _object(self, target: str, capability: str | None = None) -> dict:
        try:
            obj = self.store.object(self.resolve(target))
        except KeyError as error:
            raise Rejected("OBJECT_NOT_FOUND") from error
        if capability and capability not in obj["capabilities"]:
            raise Rejected("CAPABILITY_MISMATCH")
        if not obj["available"]:
            raise Rejected("OBJECT_UNAVAILABLE")
        return obj

    def _save_actor(self, actor: dict) -> None:
        actor["version"] += 1
        self._validate_actor(actor)
        self.store.put_actor(actor)

    def _emit(self, kind: str, payload: dict) -> None:
        self.store.emit(self._request, kind, payload)

    def _command(self, request_id: str, payload: dict, operation: Callable[[], dict | None]) -> dict:
        request_id = identity(request_id)
        fingerprint = digest(payload)
        with self.store.transaction():
            previous = self.store.db.execute("SELECT fingerprint,result FROM commands WHERE id=?", (request_id,)).fetchone()
            if previous:
                if previous[0] != fingerprint:
                    return {"accepted": False, "reason": "REQUEST_ID_REUSE", "replayed": False}
                return {**json.loads(previous[1]), "replayed": True}
            self._request = request_id
            self.store.db.execute("SAVEPOINT effect")
            try:
                detail = operation() or {}
                result = {"accepted": True, "reason": "ACCEPTED", "minute": self.minute, **detail}
                self.store.db.execute("RELEASE effect")
            except Rejected as error:
                self.store.db.execute("ROLLBACK TO effect")
                self.store.db.execute("RELEASE effect")
                result = {"accepted": False, "reason": str(error), "minute": self.minute}
                self._emit("ACTION_REJECTED", {"operation": payload["op"],
                           "actor_id": payload.get("actor_id"), "reason": str(error)})
            finally:
                self._request = ""
            self.store.db.execute("INSERT INTO commands VALUES(?,?,?)",
                                  (request_id, fingerprint, canonical_json(result)))
        return {**result, "replayed": False}

    def _check_version(self, actor: dict, expected: int | None) -> None:
        if expected is not None:
            integer(expected, "expected_version")
            if actor["version"] != expected:
                raise Rejected("STALE_STATE")

    @staticmethod
    def _check_purchase(actor: dict, obj: dict, link: dict, *,
                        require_location: bool = True) -> None:
        """购买阶段的共享条件；读取事实，不购买、不预留库存。"""
        if require_location and actor["location"] != obj["seller"]:
            raise Rejected("NOT_AT_SELLER")
        if obj["stock"] < 1:
            raise Rejected("OUT_OF_STOCK")
        if actor["money_cents"] < obj["price_cents"]:
            raise Rejected("INSUFFICIENT_FUNDS")
        if "edible" not in obj["capabilities"] and link["quantity"] > 0:
            raise Rejected("ALREADY_OWNED")

    def _buy(self, actor_id: int, target: str) -> None:
        actor = self._actor(actor_id)
        obj = self._object(target, "purchasable")
        oid = obj["object_id"]
        link = self.store.link(actor_id, oid)
        self._check_purchase(actor, obj, link)
        actor["money_cents"] -= obj["price_cents"]
        link["quantity"] += 1
        self._save_actor(actor)
        self.store.put_link(actor_id, oid, link)
        self.store.db.execute("UPDATE objects SET stock=stock-1 WHERE id=?", (oid,))
        self._emit("PURCHASED", {"actor_id": actor_id, "object_id": oid,
                               "cost_cents": obj["price_cents"], "quantity": 1})

    def _eat(self, actor_id: int, target: str) -> None:
        actor = self._actor(actor_id)
        obj = self._object(target, "edible")
        oid = obj["object_id"]
        link = self.store.link(actor_id, oid)
        if link["quantity"] < 1:
            raise Rejected("ITEM_NOT_OWNED")
        before = actor["hunger_milli"]
        actor["hunger_milli"] = max(0, before - obj["satiety_milli"])
        actor["calories_kcal"] += obj["calories_kcal"]
        link["quantity"] -= 1
        self._save_actor(actor)
        self.store.put_link(actor_id, oid, link)
        self._emit("ATE", {"actor_id": actor_id, "object_id": oid, "quantity": 1,
                          "calories_kcal": obj["calories_kcal"],
                          "hunger_before": before, "hunger_after": actor["hunger_milli"]})

    def act(self, request_id: str, actor_id: int, action: str, target: str,
            expected_version: int | None = None) -> dict:
        """保留逐动作对照入口；正在持续活动时不能绕过控制器另行消费。"""
        integer(actor_id, "actor_id", 1)
        identity(target)
        def operation():
            actor = self._actor(actor_id)
            self._check_version(actor, expected_version)
            if self.store.commitment(actor_id):
                raise Rejected("ACTIVITY_IN_PROGRESS")
            if action == "BUY":
                self._buy(actor_id, target)
            elif action == "EAT":
                self._eat(actor_id, target)
            elif action == "MOVE":
                if target not in json.loads(self.store.meta("locations")):
                    raise Rejected("UNKNOWN_DESTINATION")
                if actor["location"] == target:
                    raise Rejected("ALREADY_AT_DESTINATION")
                actor["location"] = target
                self._save_actor(actor)
                self._emit("MOVED", {"actor_id": actor_id, "destination": target,
                                    "mode": "LEGACY_INSTANT_BASELINE"})
            else:
                raise Rejected("UNSUPPORTED_ACTION")
        return self._command(request_id, {"op": "act", "actor_id": actor_id, "action": action,
                             "target": target, "expected_version": expected_version}, operation)

    def next_episode(self, actor_id: int, object_id: str) -> int | None:
        self._actor(actor_id)
        obj = self._object(object_id, "watchable")
        watched = set(self.store.link(actor_id, obj["object_id"])["watched"])
        return next((i for i in range(1, obj["episodes"] + 1) if i not in watched), None)

    def _prepare_activity(self, request_id: str, actor_id: int, activity: str,
                          target: str | None, episode: int | None, rewatch: bool,
                          expected_version: int | None) -> tuple[dict, dict]:
        """启动与只读投影共用的前置检查；不提交任何状态或事件。"""
        actor = self._actor(actor_id)
        self._check_version(actor, expected_version)
        if self.store.commitment(actor_id):
            raise Rejected("ACTIVITY_IN_PROGRESS")
        if activity != "WATCH" and (episode is not None or rewatch):
            raise Rejected("UNEXPECTED_MEDIA_ARGUMENT")
        c = {"id": request_id, "actor_id": actor_id, "activity": activity,
             "target": None, "episode": None, "rewatch": rewatch,
             "phase": activity, "status": "ACTIVE", "remaining_min": 0,
             "elapsed_min": 0, "started_minute": self.minute, "failure_reason": None}
        if activity in ("MEAL", "WATCH", "PLAY"):
            if not target:
                raise Rejected("MISSING_TARGET")
            cap = {"MEAL": "edible", "WATCH": "watchable", "PLAY": "playable"}[activity]
            obj = self._object(target, cap)
            c["target"] = obj["object_id"]
            link = self.store.link(actor_id, c["target"])
            if activity == "MEAL":
                if link["quantity"]:
                    c["phase"], c["remaining_min"] = "EAT", obj["duration_min"]
                elif actor["location"] != obj["seller"]:
                    c["phase"], c["remaining_min"] = "MOVE", self.parameters.travel_minutes
                    c["destination"] = obj["seller"]
                else:
                    c["phase"] = "BUY"
            elif activity == "WATCH":
                ep = episode if episode is not None else self.next_episode(actor_id, c["target"])
                if ep is None:
                    raise Rejected("SERIES_COMPLETED")
                if ep > obj["episodes"]:
                    raise Rejected("UNKNOWN_EPISODE")
                if ep in link["watched"] and not rewatch:
                    raise Rejected("ALREADY_COMPLETED")
                if rewatch and ep not in link["watched"]:
                    raise Rejected("REWATCH_REQUIRES_COMPLETION")
                if not rewatch and ep != self.next_episode(actor_id, c["target"]):
                    raise Rejected("PREREQUISITE_EPISODE_MISSING")
                c["episode"] = ep
                offset = 0 if rewatch else link["offsets"].get(str(ep), 0)
                c["remaining_min"] = obj["duration_min"] - offset
            else:
                if not link["quantity"]:
                    raise Rejected("ITEM_NOT_OWNED")
                c["remaining_min"] = obj["duration_min"]
        elif activity == "TRAVEL":
            if target not in json.loads(self.store.meta("locations")):
                raise Rejected("UNKNOWN_DESTINATION")
            if actor["location"] == target:
                raise Rejected("ALREADY_AT_DESTINATION")
            c["phase"], c["remaining_min"] = "MOVE", self.parameters.travel_minutes
            c["destination"] = target
        elif activity in TIMED_ACTIVITIES:
            if activity == "WORK" and actor["location"] != "office":
                raise Rejected("NOT_AT_ACTIVITY_LOCATION")
            if activity in ("SLEEP", "PERSONAL_CARE", "CHORES") and actor["location"] != "home":
                raise Rejected("NOT_AT_ACTIVITY_LOCATION")
            c["remaining_min"] = TIMED_ACTIVITIES[activity]
        else:
            raise Rejected("UNSUPPORTED_ACTIVITY")
        return actor, c

    def start(self, request_id: str, actor_id: int, activity: str, target: str | None = None,
              *, episode: int | None = None, rewatch: bool = False,
              expected_version: int | None = None) -> dict:
        integer(actor_id, "actor_id", 1)
        if not isinstance(rewatch, bool):
            raise ValueError("rewatch must be boolean")
        if episode is not None:
            integer(episode, "episode", 1, 100_000)
        def operation():
            actor, c = self._prepare_activity(
                request_id, actor_id, activity, target, episode, rewatch, expected_version)
            self.store.put_commitment(c)
            self._save_actor(actor)
            self._emit("COMMITMENT_STARTED", dict(c))
            self._settle(c)
            return {"commitment_id": request_id,
                    "commitment_status": self.store.get_commitment(request_id)["status"]}
        return self._command(request_id, {"op": "start", "actor_id": actor_id,
                             "activity": activity, "target": target, "episode": episode,
                             "rewatch": rewatch, "expected_version": expected_version}, operation)

    def preview_activity(self, actor_id: int, activity: str, target: str | None = None,
                         *, episode: int | None = None, rewatch: bool = False,
                         expected_version: int | None = None) -> dict:
        """只读、当前快照下的可执行性；不保证未来库存/事件不变。

        start_allowed 区别于 executable_now：旧 MEAL 可以先接受出发，后在
        购买阶段失败。投影提前检查该阶段，却不改变原启动/执行语义。
        这里只判断规则条件，不判断人类偏好或进食合理性。
        """
        integer(actor_id, "actor_id", 1)
        if not isinstance(rewatch, bool):
            raise ValueError("rewatch must be boolean")
        if episode is not None:
            integer(episode, "episode", 1, 100_000)
        with self.store.read_snapshot():
            result = {"activity": activity, "target": target,
                      "executable_now": False, "start_allowed": False,
                      "reason": None, "blocked_stage": "START",
                      "state_version": None, "simulation_minute": self.minute,
                      "scope": "CURRENT_SNAPSHOT_NO_EXTERNAL_CHANGES"}
            try:
                result["state_version"] = self._actor(actor_id)["version"]
                actor, c = self._prepare_activity(
                    "q62:preview", actor_id, activity, target, episode, rewatch, expected_version)
                result["start_allowed"] = True
                needs_purchase = activity == "MEAL" and c["phase"] != "EAT"
                if needs_purchase:
                    result["blocked_stage"] = "PURCHASE"
                    obj = self._object(c["target"], "purchasable")
                    link = self.store.link(actor_id, c["target"])
                    self._check_purchase(actor, obj, link, require_location=False)
                result.update(executable_now=True, reason="ELIGIBLE", blocked_stage=None,
                              requires_purchase=needs_purchase, phase=c["phase"],
                              resolved_episode=c["episode"])
            except Rejected as error:
                result["reason"] = str(error)
            return result

    def _settle(self, c: dict) -> None:
        """每个微步骤仍受规则约束；先前已经成功的阶段不会被伪装成未发生。"""
        if c["status"] != "ACTIVE" or c["phase"] != "BUY":
            return
        try:
            self._buy(c["actor_id"], c["target"])
            c["phase"] = "EAT"
            c["remaining_min"] = self._object(c["target"], "edible")["duration_min"]
        except Rejected as error:
            c["status"], c["failure_reason"] = "FAILED", str(error)
            self._emit("COMMITMENT_FAILED", {"id": c["id"], "reason": str(error)})
        self.store.put_commitment(c)

    def control(self, request_id: str, actor_id: int, operation: str) -> dict:
        integer(actor_id, "actor_id", 1)
        def execute():
            actor = self._actor(actor_id)
            c = self.store.commitment(actor_id)
            if c is None:
                raise Rejected("NO_COMMITMENT")
            transitions = {("ACTIVE", "PAUSE"): "PAUSED", ("PAUSED", "RESUME"): "ACTIVE",
                           ("ACTIVE", "CANCEL"): "CANCELLED", ("PAUSED", "CANCEL"): "CANCELLED"}
            status = transitions.get((c["status"], operation))
            if not status:
                raise Rejected("INVALID_TRANSITION")
            c["status"] = status
            self.store.put_commitment(c)
            self._save_actor(actor)
            self._emit("COMMITMENT_" + status, {"id": c["id"], "actor_id": actor_id})
            return {"commitment_id": c["id"], "status": status}
        return self._command(request_id, {"op": "control", "actor_id": actor_id,
                             "operation": operation}, execute)

    def set_available(self, request_id: str, target: str, available: bool) -> dict:
        """世界管理接口，不在模型决策权限中。"""
        if not isinstance(available, bool):
            raise ValueError("available must be boolean")
        def operation():
            oid = self.resolve(target)
            self.store.db.execute("UPDATE objects SET available=? WHERE id=?", (int(available), oid))
            self._emit("AVAILABILITY_CHANGED", {"object_id": oid, "available": available})
            if not available:
                for actor_id in self.store.actor_ids():
                    c = self.store.commitment(actor_id)
                    if c and c["target"] == oid:
                        c["status"], c["failure_reason"] = "FAILED", "OBJECT_UNAVAILABLE"
                        self.store.put_commitment(c)
                        self._save_actor(self._actor(actor_id))
                        self._emit("COMMITMENT_FAILED", {"id": c["id"], "reason": "OBJECT_UNAVAILABLE"})
        return self._command(request_id, {"op": "availability", "target": target,
                             "available": available}, operation)

    def advance(self, request_id: str, to_minute: int) -> dict:
        integer(to_minute, "to_minute")
        def operation():
            if to_minute < self.minute:
                raise Rejected("TIME_REVERSAL")
            while self.minute < to_minute:
                active = [c for i in self.store.actor_ids()
                          if (c := self.store.commitment(i)) and c["status"] == "ACTIVE"]
                boundary = min([to_minute] + [self.minute + c["remaining_min"] for c in active])
                dt = boundary - self.minute
                if dt <= 0:
                    raise RuntimeError("non-positive phase duration")
                phase_by_actor = {c["actor_id"]: c["phase"] for c in active}
                for actor_id in self.store.actor_ids():
                    actor = self._actor(actor_id)
                    actor["hunger_milli"] = min(1000, actor["hunger_milli"] + dt * self.parameters.hunger_per_minute)
                    rate = (self.parameters.sleep_energy_gain_per_minute if phase_by_actor.get(actor_id) == "SLEEP"
                            else -self.parameters.awake_energy_cost_per_minute)
                    actor["energy_milli"] = max(0, min(1000, actor["energy_milli"] + rate * dt))
                    if phase_by_actor.get(actor_id) == "WORK":
                        actor["work_minutes"] += dt
                        actor["money_cents"] += dt * self.parameters.work_pay_cents_per_minute
                    self._save_actor(actor)
                before_minute = self.minute
                self.store.set_minute(boundary)
                self._emit("TIME_ADVANCED", {"from_minute": before_minute, "to_minute": boundary})
                for c in active:
                    c["elapsed_min"] += dt
                    c["remaining_min"] -= dt
                    actor_id = c["actor_id"]
                    if c["phase"] in ("WATCH", "PLAY"):
                        link = self.store.link(actor_id, c["target"])
                        if c["phase"] == "PLAY":
                            link["play_minutes"] += dt
                        elif not c["rewatch"]:
                            key = str(c["episode"])
                            link["offsets"][key] = link["offsets"].get(key, 0) + dt
                        self.store.put_link(actor_id, c["target"], link)
                        self._emit("MEDIA_PROGRESS", {"id": c["id"], "actor_id": actor_id,
                                   "object_id": c["target"], "minutes": dt,
                                   "episode": c["episode"], "rewatch": c["rewatch"]})
                    if c["phase"] == "WORK":
                        self._emit("WORKED", {"actor_id": actor_id, "minutes": dt, "income_cents": dt * self.parameters.work_pay_cents_per_minute})
                    self.store.put_commitment(c)
                    if c["remaining_min"] == 0:
                        self._finish_phase(c)
            return {"minute": self.minute}
        return self._command(request_id, {"op": "advance", "to_minute": to_minute}, operation)

    def _finish_phase(self, c: dict) -> None:
        actor_id = c["actor_id"]
        if c["phase"] == "MOVE":
            actor = self._actor(actor_id)
            actor["location"] = c["destination"]
            self._save_actor(actor)
            self._emit("MOVED", {"actor_id": actor_id, "destination": c["destination"],
                                 "mode": "COMMITMENT_TRAVEL"})
            if c["activity"] == "TRAVEL":
                c["status"] = "COMPLETED"
                self.store.put_commitment(c)
                self._emit("COMMITMENT_COMPLETED", {"id": c["id"], "actor_id": actor_id,
                                                    "activity": c["activity"]})
                return
            c["phase"] = "BUY"
            self.store.put_commitment(c)
            self._settle(c)
            return
        try:
            if c["phase"] == "EAT":
                self._eat(actor_id, c["target"])
            elif c["phase"] == "WATCH":
                link = self.store.link(actor_id, c["target"])
                ep = c["episode"]
                if ep not in link["watched"]:
                    link["watched"] = sorted([*link["watched"], ep])
                key = str(ep)
                link["view_counts"][key] = link["view_counts"].get(key, 0) + 1
                self.store.put_link(actor_id, c["target"], link)
                self._emit("REWATCH_COMPLETED" if c["rewatch"] else "EPISODE_COMPLETED",
                           {"actor_id": actor_id, "object_id": c["target"], "episode": ep})
            c["status"] = "COMPLETED"
            self._emit("COMMITMENT_COMPLETED", {"id": c["id"], "actor_id": actor_id,
                                                "activity": c["activity"]})
        except Rejected as error:
            c["status"], c["failure_reason"] = "FAILED", str(error)
            self._emit("COMMITMENT_FAILED", {"id": c["id"], "reason": str(error)})
        self.store.put_commitment(c)
