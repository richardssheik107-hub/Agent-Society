from pathlib import Path

SCRIPT = (Path(__file__).resolve().parents[1] / "scripts/setup_q6_1_runtime.sh").read_text()


def test_setup_pins_python_312_before_system_python():
    assert 'command -v python3.12' in SCRIPT
    assert 'PYTHON_BIN="$(command -v python3.12)"' in SCRIPT
    assert 'python3 -m venv' not in SCRIPT


def test_setup_uses_uv_312_only_when_direct_interpreter_missing():
    assert 'uv python find 3.12' in SCRIPT
    assert 'uv python install 3.12' in SCRIPT
    assert 'uv venv --seed --python "$PYTHON_BIN" "$ENV"' in SCRIPT
    assert 'FAILURE_STAGE=PYTHON_312_UNAVAILABLE' in SCRIPT


def test_setup_rebuilds_incomplete_or_wrong_version_runtime():
    assert 'sys.version_info[:2] == (3, 12)' in SCRIPT
    assert '"$ENV/bin/python" -m pip --version' in SCRIPT
    assert 'quarantine=' in SCRIPT
    assert 'mv -- "$ENV" "$quarantine"' in SCRIPT


def test_setup_has_no_provider_execution_path():
    assert "allow-provider" not in SCRIPT

