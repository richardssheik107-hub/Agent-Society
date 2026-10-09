"""冻结的 M5 会话合同；模拟时间、服务预算和评价阈值分别声明。"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, fields
from pathlib import Path
import json

from social_sim.continuity.models import digest, integer

PROTOCOL_VERSION = "M5_LONGRUN_V1"
SIMULATION_DAY_MINUTES = 1440


@dataclass(frozen=True)
class WarningThresholds:
    """仅用于合成 milli 状态的观测预警，不是医学规范或行为干预。"""

    hunger_high: int = 900
    energy_low: int = 150
    sustained_minutes: int = 180
    repeated_failure_count: int = 3
    no_improvement_decisions: int = 5
    money_decline_cents: int = 5000
    frequent_travel_count: int = 5

    def __post_init__(self) -> None:
        integer(self.hunger_high, "hunger_high", 0, 1000)
        integer(self.energy_low, "energy_low", 0, 1000)
        for name in ("sustained_minutes", "repeated_failure_count",
                     "no_improvement_decisions", "money_decline_cents", "frequent_travel_count"):
            integer(getattr(self, name), name, 1, 100000)


@dataclass(frozen=True)
class LongRunConfig:
    """本 Runtime 创建的新版本世界显式 opt-in；ContinuityWorld 默认仍关闭。

    provider 预算默认为零，即使持有 API key 也不获得真实执行权限。
    protocol_hash 只覆盖稳定配置，不把提交 SHA 自引用进协议。
    """

    protocol_version: str = PROTOCOL_VERSION
    mode: str = "offline"
    sim_days: int = 7
    max_decisions: int = 1000
    max_provider_requests: int = 0
    max_wall_seconds: float = 600.0
    request_timeout_seconds: float = 60.0
    max_micro_steps: int = 1000
    step_minutes: int = 15
    max_context_chars: int = 12000
    max_context_tokens: int = 12000
    recent_activity_limit: int = 5
    goal_mode: str = "OPEN_AUTONOMOUS"
    goals: tuple[str, ...] = ()
    seed: int = 20261009
    acquire_enabled: bool = True
    max_consecutive_errors: int = 3
    max_no_progress: int = 5
    provider_minimal_request: bool = True
    provider_max_tokens: int = 64
    provider_temperature: float = 0.0
    provider_thinking_disabled: bool = False
    warnings: WarningThresholds = WarningThresholds()

    def __post_init__(self) -> None:
        if self.protocol_version != PROTOCOL_VERSION:
            raise ValueError("UNSUPPORTED_M5_PROTOCOL")
        if self.mode not in {"offline", "real"}:
            raise ValueError("INVALID_MODE")
        if self.goal_mode not in {"OPEN_AUTONOMOUS", "GOAL_CONDITIONED"}:
            raise ValueError("INVALID_GOAL_MODE")
        if not isinstance(self.goals, tuple) or len(self.goals) > 5:
            raise ValueError("GOALS_MUST_BE_BOUNDED_TUPLE")
        if any(not isinstance(g, str) or not g.strip() or len(g) > 2000 for g in self.goals):
            raise ValueError("INVALID_EXPERIMENT_GIVEN_GOAL")
        if (self.goal_mode == "OPEN_AUTONOMOUS" and self.goals
                or self.goal_mode == "GOAL_CONDITIONED" and not self.goals):
            raise ValueError("GOAL_MODE_MISMATCH")
        integer(self.sim_days, "sim_days", 1, 30)
        integer(self.max_decisions, "max_decisions", 1, 100000)
        integer(self.max_provider_requests, "max_provider_requests", 0, self.max_decisions)
        if self.mode == "offline" and self.max_provider_requests != 0:
            raise ValueError("OFFLINE_PROVIDER_BUDGET_MUST_BE_ZERO")
        integer(self.max_micro_steps, "max_micro_steps", 1, 10000)
        integer(self.step_minutes, "step_minutes", 1, 15)
        integer(self.max_context_chars, "max_context_chars", 128, 100000)
        integer(self.max_context_tokens, "max_context_tokens", 128, 100000)
        integer(self.recent_activity_limit, "recent_activity_limit", 1, 5)
        integer(self.seed, "seed", 0, 2**32 - 1)
        integer(self.max_consecutive_errors, "max_consecutive_errors", 1, 100)
        integer(self.max_no_progress, "max_no_progress", 1, 100)
        integer(self.provider_max_tokens, "provider_max_tokens", 1, 128)
        for name, upper in (("max_wall_seconds", 86400), ("request_timeout_seconds", 60)):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(name + "_MUST_BE_FINITE_NUMBER")
            if not math.isfinite(value) or not 0 < value <= upper:
                raise ValueError(name + "_OUT_OF_RANGE")
        temp = self.provider_temperature
        if (isinstance(temp, bool) or not isinstance(temp, (int, float))
                or not math.isfinite(temp) or not 0 <= temp <= 0.2):
            raise ValueError("INVALID_PROVIDER_TEMPERATURE")
        for name in ("acquire_enabled", "provider_minimal_request", "provider_thinking_disabled"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(name + "_MUST_BE_BOOLEAN")
        if not isinstance(self.warnings, WarningThresholds):
            raise ValueError("INVALID_WARNING_CONFIGURATION")

    @property
    def horizon_minutes(self) -> int:
        return self.sim_days * SIMULATION_DAY_MINUTES

    def to_dict(self) -> dict:
        data = asdict(self)
        data["goals"] = list(self.goals)
        return data

    @property
    def protocol_hash(self) -> str:
        return digest(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> LongRunConfig:
        if not isinstance(data, dict):
            raise ValueError("PROTOCOL_MUST_BE_OBJECT")
        if set(data) - {f.name for f in fields(cls)}:
            raise ValueError("UNKNOWN_PROTOCOL_FIELDS")
        values = dict(data)
        if "goals" in values:
            if not isinstance(values["goals"], list):
                raise ValueError("GOALS_MUST_BE_JSON_ARRAY")
            values["goals"] = tuple(values["goals"])
        if "warnings" in values:
            if not isinstance(values["warnings"], dict):
                raise ValueError("WARNINGS_MUST_BE_OBJECT")
            values["warnings"] = WarningThresholds(**values["warnings"])
        return cls(**values)

    @classmethod
    def load(cls, path: str | Path) -> LongRunConfig:
        def unique(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError("DUPLICATE_PROTOCOL_KEY")
                result[key] = value
            return result
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8"),
                                        object_pairs_hook=unique))
