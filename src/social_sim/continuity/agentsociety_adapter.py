"""AS2 的薄适配器：复用既有确定性 Router，不启用 PersonAgent/ReAct。

此模块按需导入；纯领域测试不要求安装 AgentSociety。workspace checkpoint
保存的是 SQLite 事务快照，replay 仍是独立的分析产物。
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from agentsociety2.env import tool

from social_sim.world import ObservationBuilder, OfferState, PersonWorldState, WorldState
from social_sim.world.env import RuleWorldEnv

from .context import observe
from .engine import ContinuityWorld


class ContinuityEnv(RuleWorldEnv):
    """具有事实持久化和滚动活动的实验环境；不替换历史 RuleWorldEnv。"""

    def __init__(self, database_path: str, epoch: str = "2026-01-01T00:00:00+00:00") -> None:
        self.epoch = datetime.fromisoformat(epoch)
        if self.epoch.tzinfo is None:
            raise ValueError("epoch requires an explicit timezone")
        self.runtime = ContinuityWorld(database_path)
        self._bind_epoch()
        super().__init__(self._project())

    def _bind_epoch(self) -> None:
        with self.runtime.store.transaction():
            db = self.runtime.store.db
            db.execute("INSERT OR IGNORE INTO meta VALUES('epoch',?)", (self.epoch.isoformat(),))
            if self.runtime.store.meta("epoch") != self.epoch.isoformat():
                raise ValueError("checkpoint epoch mismatch")

    @classmethod
    def init_description(cls) -> str:
        return "ContinuityEnv(database_path, epoch): deterministic persistent experimental world."

    def _project(self) -> WorldState:
        state = self.runtime.store.snapshot()
        people = {}
        for actor in state["actors"]:
            inv = {r["object_id"]: r["state"]["quantity"] for r in state["links"]
                   if r["actor_id"] == actor["actor_id"] and r["state"]["quantity"]}
            people[actor["actor_id"]] = PersonWorldState(
                actor["actor_id"], actor["location"], actor["money_cents"] / 100,
                actor["hunger_milli"] / 1000, inv, actor["energy_milli"] / 1000,
            )
        try:
            locations = json.loads(self.runtime.store.meta("locations"))
        except KeyError:
            locations = ["home", "restaurant", "office", "park"]
        venues = {}
        for obj in state["objects"]:
            if "purchasable" in obj["capabilities"]:
                venues.setdefault(obj["seller"], {})[obj["object_id"]] = OfferState(
                    obj["object_id"], obj["price_cents"] / 100,
                    obj["stock"] if obj["available"] else 0,
                )
        return WorldState(self.epoch + timedelta(minutes=state["minute"]), people,
                          locations=locations, venues=venues)

    def refresh_projection(self) -> None:
        self.world_state = self._project()
        self.observation_builder = ObservationBuilder(self.world_state)

    @tool(readonly=True, kind="observe")
    def observe_person(self, agent_id: int) -> dict:
        """读取当前人物、有限候选和已保存的追剧进度；不调用模型。"""
        try:
            return observe(self.runtime, agent_id)
        except KeyError:
            return {"agent_id": agent_id, "error": "unknown_agent_id"}

    async def init(self, start_datetime: datetime) -> None:
        self.refresh_projection()
        self.t = self.world_state.time

    async def step(self, tick: int, t: datetime) -> None:
        if t.tzinfo is None:
            raise ValueError("simulation time requires timezone")
        seconds = (t - self.epoch).total_seconds()
        if seconds < 0 or seconds % 60:
            raise ValueError("Q6 adapter uses nonnegative whole simulation minutes")
        result = self.runtime.advance(f"as2-clock:{int(seconds)}", int(seconds // 60))
        if not result["accepted"]:
            raise ValueError(result["reason"])
        self.t = t
        self.refresh_projection()

    async def to_workspace(self, workspace_path: Path | None = None) -> None:
        if workspace_path is not None:
            self._bind_workspace(workspace_path)
        if self._workspace_root is None:
            raise ValueError("workspace must be bound before checkpoint")
        folder = self._workspace_root / "state"
        folder.mkdir(parents=True, exist_ok=True)
        destination = folder / "continuity.sqlite3"
        if Path(self.runtime.store.path).resolve() == destination.resolve():
            return
        fd, temporary = tempfile.mkstemp(prefix="continuity-", suffix=".sqlite3", dir=folder)
        os.close(fd)
        os.unlink(temporary)
        try:
            self.runtime.store.backup(temporary)
            with open(temporary, "rb") as source:
                os.fsync(source.fileno())
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    async def restore(self, workspace_path: Path) -> bool:
        self._bind_workspace(workspace_path)
        source = self._workspace_root / "state" / "continuity.sqlite3"
        if not source.exists():
            return False
        self.runtime.close()
        self.runtime = ContinuityWorld(source)
        self._bind_epoch()
        self.refresh_projection()
        self.t = self.world_state.time
        return True

    async def close(self) -> None:
        self.runtime.close()
