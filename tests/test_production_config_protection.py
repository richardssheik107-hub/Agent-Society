from pathlib import Path

import pytest

from social_sim.calibration.validation import file_sha256, validate_unchanged
from social_sim.daily.time import LEISURE_DURATION_MINUTES, SLEEP_DURATION_MINUTES, WORK_DURATION_MINUTES
from social_sim.decision.models import ActionType
from social_sim.rules.engine import RuleEngine


ROOT = Path(__file__).resolve().parents[1]


def test_production_actions_rules_and_durations_untouched():
    assert (SLEEP_DURATION_MINUTES, WORK_DURATION_MINUTES, LEISURE_DURATION_MINUTES) == (360, 90, 60)
    assert {action.value for action in ActionType} == {"WAIT", "REST", "MOVE", "BUY", "EAT", "SLEEP", "WORK", "LEISURE"}
    assert {action.value for action in RuleEngine()._rules} == {"MOVE", "BUY", "EAT", "SLEEP", "WORK", "LEISURE"}
    paths = [ROOT / "src/social_sim/daily/time.py", ROOT / "src/social_sim/rules/engine.py", ROOT / "src/social_sim/decision/models.py"]
    hashes = {path: file_sha256(path) for path in paths}
    validate_unchanged(hashes)


def test_change_detection_on_temp_file(tmp_path):
    file = tmp_path / "production.yaml"
    file.write_text("old", encoding="utf-8")
    original = file_sha256(file)
    file.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="production file modified"):
        validate_unchanged({file: original})


def test_builder_refuses_production_profile_target(tmp_path):
    from scripts.build_neutral_day_calibration import build

    with pytest.raises(ValueError, match="experimental"):
        build(source_dir=tmp_path, output=tmp_path / "out", profile_path=ROOT / "src/social_sim/daily/time.py")
