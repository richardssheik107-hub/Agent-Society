"""M5 的兼容和交付门禁以真实文件/冻结 Git 为准，不只断言成功标签。"""
import importlib.util
import subprocess
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
