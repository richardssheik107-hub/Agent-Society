import sys

from scripts import build_neutral_day_calibration as script


def test_dry_run_does_not_write_files(tmp_path, monkeypatch, capsys):
    target = tmp_path / "output"
    profile = tmp_path / "experimental/profile.yaml"
    monkeypatch.setattr(script, "verified_inputs", lambda _: ({"dataset": "NHAPS_AHTUS_1992_94", "archive_sha256": "fixture"}, {}))
    monkeypatch.setattr(sys, "argv", ["calibration", "--dry-run", "--input", str(tmp_path), "--output", str(target), "--profile", str(profile)])
    script.main()
    assert '"dry_run": true' in capsys.readouterr().out
    assert not target.exists()
    assert not profile.exists()
