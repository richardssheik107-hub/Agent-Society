from pathlib import Path
from zipfile import ZipFile
import hashlib
import json

from scripts.build_atus_behavior_corpus import build
from social_sim.human_data.atus import load_atus_activity
from social_sim.human_data.mapping import load_mapping
from social_sim.human_data.validation import validate_diary


MAPPING = Path(__file__).resolve().parents[1] / "config/atus_activity_mapping.yaml"


def test_24_hour_clock_wrap_and_adult_roster_filter(tmp_path):
    activity = tmp_path / "activity.csv"
    respondent = tmp_path / "respondent.csv"
    roster = tmp_path / "roster.csv"
    activity.write_text("TUCASEID,TUACTIVITY_N,TUACTDUR24,TUSTARTTIM,TUSTOPTIME,TUTIER1CODE,TUTIER2CODE,TUTIER3CODE,TEWHERE\nA,1,1200,04:00:00,00:00:00,01,01,01,-1\nA,2,240,00:00:00,04:00:00,01,01,01,-1\nB,1,1440,04:00:00,04:00:00,01,01,01,-1\n", encoding="utf-8")
    respondent.write_text("TUCASEID,TELFS,TUDIARYDATE,TUDIARYDAY\nA,1,20250106,2\nB,5,20250107,3\n", encoding="utf-8")
    roster.write_text("TUCASEID,TULINENO,TEAGE\nA,1,40\nB,1,17\n", encoding="utf-8")
    result = load_atus_activity(activity, respondent, roster, load_mapping(MAPPING))
    assert result.activity_rows == 3
    assert len(result.diaries) == 1
    assert result.diaries[0].metadata["weekday"] is True
    assert result.diaries[0].metadata["clock_mismatch_count"] == 0
    assert validate_diary(result.diaries[0]).valid


def test_offline_build_uses_zip_headers_and_emits_manifest(tmp_path):
    root = tmp_path / "atus" / "2025"
    raw = root / "raw"
    raw.mkdir(parents=True)
    contents = {
        "atusact-2025.zip": "TUCASEID,TUACTIVITY_N,TUACTDUR24,TUSTARTTIM,TUSTOPTIME,TUTIER1CODE,TUTIER2CODE,TUTIER3CODE,TEWHERE\nA,1,480,04:00:00,12:00:00,01,01,01,-1\nA,2,480,12:00:00,20:00:00,05,01,01,2\nA,3,480,20:00:00,04:00:00,12,03,01,1\n",
        "atusresp-2025.zip": "TUCASEID,TELFS,TUDIARYDATE,TUDIARYDAY\nA,1,20250106,2\n",
        "atusrost-2025.zip": "TUCASEID,TULINENO,TEAGE\nA,1,40\n",
        "atuswho-2025.zip": "TUCASEID,TUACTIVITY_N,TUWHO_CODE\nA,2,18\n",
    }
    records = []
    for name, content in contents.items():
        path = raw / name
        with ZipFile(path, "w") as archive:
            archive.writestr(name.replace(".zip", ".dat"), content)
        records.append({"name": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    (root / "SOURCE.json").write_text(json.dumps({"source_page": "https://www.bls.gov/tus/data/datafiles-2025.htm", "files": records}), encoding="utf-8")
    output = tmp_path / "run"
    result = build(root, output, MAPPING)
    assert result["raw_activity_rows"] == 3
    assert result["valid_adult_diaries"] == 1
    assert result["employed_weekday_diaries"] == 1
    assert (output / "dataset_manifest.json").exists()
    assert (output / "behavior_days.jsonl").exists()
    assert json.loads((output / "mapping_coverage.json").read_text())["all_adults"]["mapped_to_core_count"] == 3
