"""真实 M2 CLI 离线护栏、排他产物和失败保留合同。"""
from __future__ import annotations

import builtins
import importlib.util
import json
from pathlib import Path

import pytest

from social_sim.continuity import m2_validation

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("m2_cli", ROOT / "scripts/run_m2_acquire_validation.py")
assert SPEC and SPEC.loader
CLI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLI)


def test_real_cli_is_offline_without_environment_or_provider_imports(tmp_path, monkeypatch):
    original_import = builtins.__import__
    original_open = builtins.open
    original_read = Path.read_text

    def safe_import(name, *args, **kwargs):
        assert not name.startswith(("social_sim.decision", "social_sim.provider_runtime",
                                    "httpx", "litellm", "dotenv"))
        return original_import(name, *args, **kwargs)

    def safe_open(file, *args, **kwargs):
        assert not isinstance(file, (str, Path)) or Path(file).name != ".env"
        return original_open(file, *args, **kwargs)

    def safe_read(path, *args, **kwargs):
        assert path.name != ".env"
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", safe_import)
    monkeypatch.setattr(builtins, "open", safe_open)
    monkeypatch.setattr(Path, "read_text", safe_read)
    assert CLI.main(["--session", "contract", "--output-root", str(tmp_path)]) == 0
    summary = json.loads((tmp_path / "contract/summary.json").read_text())
    assert summary["passed"] == summary["total"] == 17
    assert summary["fake_decision_calls"] == 3
    assert summary["provider_requests"] == summary["llm_calls"] == 0
    assert not summary["real_provider_executed"]
    loop = summary["closed_loop"]
    assert loop["initial_quantity"] == 0 and loop["owned_quantity"] == 1
    assert loop["acquire_minutes"] == 0 and loop["separate_play_minutes"] == 45
    assert loop["play_legal"] and not loop["automatic_play"]
    for case in summary["cases"]:
        folder = tmp_path / "contract" / case["case"]
        assert (folder / "world.sqlite").is_file()
        data = json.loads((folder / "case.json").read_text())
        assert data["validation"]["invariants"] == "PASS"
        assert data["events"] and data["initial_state"] and data["final_state"]
        assert data["configuration"]["acquire_enabled"]


def test_cli_cannot_switch_to_real_mode(tmp_path):
    with pytest.raises(SystemExit) as error:
        CLI.main(["--mode", "real", "--output-root", str(tmp_path)])
    assert error.value.code == 2 and not list(tmp_path.iterdir())


def test_cli_duplicate_session_refuses_overwrite(tmp_path):
    assert CLI.main(["--session", "once", "--output-root", str(tmp_path)]) == 0
    files = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert CLI.main(["--session", "once", "--output-root", str(tmp_path)]) == 1
    assert files == {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


@pytest.mark.parametrize("session", ["../escape", "bad/name", "", "a" * 81])
def test_cli_unsafe_session_cannot_escape_output(tmp_path, session):
    assert CLI.main(["--session", session, "--output-root", str(tmp_path)]) == 1
    assert not list(tmp_path.iterdir())


def test_cli_retains_failed_scenario_and_never_saves_unknown_error_text(tmp_path, monkeypatch):
    def fail(_case):
        raise RuntimeError("SENSITIVE_EXCEPTION_MUST_NOT_BE_STORED")

    monkeypatch.setattr(m2_validation, "_owned", fail)
    assert CLI.main(["--session", "failure", "--output-root", str(tmp_path)]) == 1
    summary = json.loads((tmp_path / "failure/summary.json").read_text())
    assert summary["result"] == "FAIL" and summary["passed"] == 16
    folder = tmp_path / "failure/already_owned"
    data = json.loads((folder / "case.json").read_text())
    assert data["result"] == "FAIL" and data["error_type"] == "RuntimeError"
    assert (folder / "world.sqlite").is_file() and data["initial_state"] and data["final_state"]
    assert data["events"]
    assert all("SENSITIVE_EXCEPTION_MUST_NOT_BE_STORED" not in p.read_text()
               for p in (tmp_path / "failure").rglob("*.json"))
