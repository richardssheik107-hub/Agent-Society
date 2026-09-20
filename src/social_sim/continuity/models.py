"""Q6 的数据契约：事实由程序持有，模型只能提交意图。"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any

SCHEMA_VERSION = 1
ACTIVE_STATUSES = ("ACTIVE", "PAUSED")
TIMED_ACTIVITIES = {
    "WORK": 270, "SLEEP": 360, "LEISURE": 75,
    "PERSONAL_CARE": 30, "CHORES": 30,
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def integer(value: Any, name: str, low: int = 0, high: int = 10**12) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{name}: integer required in [{low}, {high}]")
    return value


def identity(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 128:
        raise ValueError("identifier must contain 1..128 characters")
    return value.strip()


def alias_key(value: str) -> str:
    return unicodedata.normalize("NFKC", identity(value)).casefold()


class Rejected(Exception):
    """可预期的领域拒绝；不允许写入部分后果。"""


@dataclass(frozen=True)
class ObjectDefinition:
    object_id: str
    name: str
    kind: str
    capabilities: tuple[str, ...]
    price_cents: int = 0
    calories_kcal: int = 0
    satiety_milli: int = 0
    duration_min: int = 30
    episodes: int = 0
    seller: str = "restaurant"
    aliases: tuple[str, ...] = ()
    attribute_source: str = "SYNTHETIC_FIXTURE"

    def __post_init__(self) -> None:
        identity(self.object_id)
        identity(self.name)
        if not self.capabilities or len(set(self.capabilities)) != len(self.capabilities):
            raise ValueError("capabilities must be nonempty and unique")
        if not all(isinstance(x, str) for x in self.capabilities):
            raise ValueError("invalid capability")
        integer(self.price_cents, "price_cents")
        integer(self.calories_kcal, "calories_kcal", high=100_000)
        integer(self.satiety_milli, "satiety_milli", high=1000)
        integer(self.duration_min, "duration_min", 1, 1440)
        integer(self.episodes, "episodes", high=100_000)
        if "watchable" in self.capabilities and self.episodes < 1:
            raise ValueError("watchable media requires episodes")
        for alias in self.aliases:
            identity(alias)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict) -> ObjectDefinition:
        data = dict(value)
        data["capabilities"] = tuple(data["capabilities"])
        data["aliases"] = tuple(data.get("aliases", ()))
        return cls(**data)


def initial_actor(actor_id: int, money_cents: int = 10000, location: str = "home") -> dict:
    integer(actor_id, "actor_id", 1)
    integer(money_cents, "money_cents")
    return {
        "actor_id": actor_id, "location": identity(location),
        "money_cents": money_cents, "hunger_milli": 800,
        "energy_milli": 700, "calories_kcal": 0,
        "work_minutes": 0, "version": 0,
    }


def initial_link() -> dict:
    return {"quantity": 0, "watched": [], "offsets": {},
            "view_counts": {}, "play_minutes": 0}


@dataclass(frozen=True)
class RuleParameters:
    """新世界初始化参数；有存档时禁止无迁移地偷偷更换规则。"""
    version: str = "q6_v1"
    travel_minutes: int = 15
    hunger_per_minute: int = 1
    awake_energy_cost_per_minute: int = 1
    sleep_energy_gain_per_minute: int = 2
    work_pay_cents_per_minute: int = 10

    def __post_init__(self) -> None:
        identity(self.version)
        integer(self.travel_minutes, "travel_minutes", 1, 1440)
        for name in ("hunger_per_minute", "awake_energy_cost_per_minute",
                     "sleep_energy_gain_per_minute", "work_pay_cents_per_minute"):
            integer(getattr(self, name), name, high=100_000)
