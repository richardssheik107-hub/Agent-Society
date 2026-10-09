"""M5 的兼容和交付门禁以真实文件/冻结 Git 为准，不只断言成功标签。"""
import importlib.util
import asyncio
import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STARTING_MAIN = "3603d68d43738a7fe1683211e7c7919b17ef5a14"


@pytest.mark.parametrize("name", [
    "src/social_sim/continuity/engine.py", "src/social_sim/continuity/store.py",
    "src/social_sim/continuity/models.py", "src/social_sim/continuity/context.py",
    "src/social_sim/continuity/m2_acquire.py", "src/social_sim/continuity/q6_1.py",
    "src/social_sim/continuity/q6_2.py", "src/social_sim/continuity/action_projection.py",
    "src/social_sim/continuity/q6_2_panel.py", "src/social_sim/decision/client.py",
    "config/experimental/q6_2_fixed_state_panel_v1.json",
    "config/experimental/q6_2_fixed_state_panel_v2.json",
    "docs/reference/q62_outcome_audit_results.json",
])
def test_frozen_existing_contracts_unchanged(name):
    original = subprocess.check_output(["git", "show", STARTING_MAIN + ":" + name], cwd=ROOT)
    assert (ROOT / name).read_bytes() == original


def test_official_submodule_gitlink_unchanged():
    sha = subprocess.check_output(["git", "rev-parse", "HEAD:third_party/AgentSociety"],
                                  cwd=ROOT, text=True).strip()
    assert sha == "670c94fff7c64c4f79b632125f2ccf968155e746"


def test_new_decisions_are_append_only_not_historical_reclassification():
    current = (ROOT / "docs/review/decisions.md").read_text(encoding="utf-8")
    assert "D02_DECISION=APPROVED_SCOPED_OPT_IN" in current
    assert "D09_DECISION=APPROVED_MULTIDIMENSIONAL_EVALUATION" in current
    assert "决定：待审核" in current
    assert "NO_CLEAR_DIFFERENCE" in current and "EXPLORATORY_POST_HOC" in current
    assert "UNRESOLVED" in current


def test_semantic_comparison_only_ignores_session_identity_and_runtime_timing():
    spec = importlib.util.spec_from_file_location("m5_validation", ROOT / "scripts/check_m5_longrun.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    def data(name, money):
        return {"session": {"session_id": name},
                "world": {"money_cents": money, "commitment": {"id": f"m5:{name}:000001"}},
                "events": [{"seq": 1, "minute": 0, "kind": "COMMITMENT_STARTED",
                            "command_id": f"m5:{name}:000001", "payload": {"id": f"m5:{name}:000001"}}],
                "requests": [{"ordinal": 1, "minute": 0, "proposal": {"activity": "ACQUIRE", "target": "game_a"}}],
                "commands": [{"id": name}]}
    assert module.semantic_evidence(data("plain", 100)) == module.semantic_evidence(data("resumed", 100))
    assert module.semantic_evidence(data("plain", 100)) != module.semantic_evidence(data("resumed", 99))


def test_validation_guard_cannot_open_external_network():
    spec = importlib.util.spec_from_file_location("m5_validation_guard", ROOT / "scripts/check_m5_longrun.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    import socket
    with module.offline_network_guard(), pytest.raises(RuntimeError, match="OFFLINE_NETWORK_FORBIDDEN"):
        socket.getaddrinfo("must-not-resolve.invalid", 443)


def test_budget_truncated_validation_keeps_failure_report_and_resources(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("m5_validation_failure", ROOT / "scripts/check_m5_longrun.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = replace(module.LongRunConfig(), max_wall_seconds=0.000001)
    monkeypatch.setattr(module.LongRunConfig, "load", lambda _: config)
    with pytest.raises(AssertionError, match="M5_ACTUAL_HORIZON_NOT_REACHED"):
        asyncio.run(module.run_one(tmp_path, 7, restarted=False, provenance={"execution_commit": STARTING_MAIN}))
    folder = tmp_path / "day7-plain"
    summary = json.loads((folder / "summary.json").read_text())
    resources = json.loads((folder / "resources.json").read_text())
    failure = json.loads((folder / "validation_failure.json").read_text())
    assert summary["stop_reason"] == resources["stop_reason"] == "WALL_CLOCK_LIMIT"
    assert summary["simulation_minutes"] == resources["simulation_minutes"] < 10080
    assert resources["horizon_reached"] is False and failure["result"] == "FAIL"
    assert (folder / "report.md").is_file() and resources["provider_requests"] == 0
