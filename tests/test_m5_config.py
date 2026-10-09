"""M5 明确预算、严格协议与合成预警边界。"""
from dataclasses import replace
from pathlib import Path

import pytest

from social_sim.longrun.config import LongRunConfig, WarningThresholds


def test_default_no_real_authorization_and_exact_day_minutes():
    config = LongRunConfig()
    assert config.mode == "offline" and config.max_provider_requests == 0
    assert config.horizon_minutes == 10080
    assert replace(config, sim_days=30).horizon_minutes == 43200


def test_checked_in_protocol_round_trip_and_hash():
    root = Path(__file__).resolve().parents[1]
    config = LongRunConfig.load(root / "config/experimental/m5_longrun_v1.json")
    assert config == LongRunConfig.from_dict(config.to_dict())
    assert len(config.protocol_hash) == 64
    assert replace(config, sim_days=30).protocol_hash != config.protocol_hash


@pytest.mark.parametrize("change", [
    {"sim_days": True}, {"sim_days": 0}, {"sim_days": 31},
    {"max_provider_requests": 1}, {"max_decisions": 0},
    {"step_minutes": 16}, {"max_wall_seconds": float("nan")},
    {"request_timeout_seconds": 61}, {"max_context_tokens": 0},
    {"recent_activity_limit": 6}, {"acquire_enabled": 1},
    {"goal_mode": "GOAL_CONDITIONED"}, {"goals": ("buy game",)},
    {"provider_temperature": float("inf")}, {"provider_max_tokens": 129},
])
def test_invalid_protocol_fails_closed(change):
    with pytest.raises((ValueError, TypeError)):
        replace(LongRunConfig(), **change)


def test_goal_given_by_experiment_and_warnings_not_global_score():
    config = LongRunConfig(goal_mode="GOAL_CONDITIONED", goals=("合法获得游戏并随后使用",))
    assert config.to_dict()["goals"] == ["合法获得游戏并随后使用"]
    assert isinstance(config.warnings, WarningThresholds)
    assert "human_score" not in config.to_dict()


def test_unknown_and_duplicate_protocol_fields_rejected(tmp_path):
    with pytest.raises(ValueError, match="UNKNOWN_PROTOCOL_FIELDS"):
        LongRunConfig.from_dict({"money_cents": 999999})
    path = tmp_path / "duplicate.json"
    path.write_text('{"mode":"offline","mode":"real"}', encoding="utf-8")
    with pytest.raises(ValueError, match="DUPLICATE_PROTOCOL_KEY"):
        LongRunConfig.load(path)
