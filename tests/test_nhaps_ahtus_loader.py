from pathlib import Path

import yaml

from social_sim.human_data.nhaps_ahtus import NhapsMapping, load_rows
from social_sim.human_data.validation import validate_diary


MAPPING = Path(__file__).resolve().parents[1] / "config/nhaps_ahtus_activity_mapping.yaml"


def _mapping():
    # Fake metadata is independent of the archive/network.
    rules = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))["rules"]
    return NhapsMapping(MAPPING, {r["source_code"]: r["source_label"] for r in rules})


def _rows():
    key = {"survey": 4, "wave": 1, "hhid": 11, "pid": 11}
    rows = [{**key, "epnum": i, "start": a, "end": b, "time": b - a, "main": code, "diaryday": 2, "month": 3, "year": 1993, "eloc": loc, "mtrav": -7, "recwght": 1, "lowqual": 0, "baddem": 0} for i, a, b, code, loc in [(2, 480, 500, 9, 1), (1, 0, 480, 3, 1), (3, 500, 1440, 93, 8)]]
    background = [{**key, "age": 40, "empstat": 1}]
    summary = [{**key, "tottime": 1440, "numep": 3, "tmain3": 480, "tmain9": 20, "tmain93": 940, "recwght": 1}]
    return rows, background, summary


def test_merge_order_clock_and_summary_crosscheck():
    result = load_rows(*_rows(), _mapping())
    assert result.raw_diarists == 1
    assert len(result.diaries) == 1
    diary = result.diaries[0]
    assert diary.metadata["diary_start_clock_minute"] == 0
    assert [ep.episode_index for ep in diary.episodes] == [1, 2, 3]
    assert [ep.start_minute for ep in diary.episodes] == [0, 480, 500]
    assert validate_diary(diary).valid
    assert not result.summary_mismatches


def test_missing_age_and_summary_mismatch():
    episodes, background, summary = _rows()
    background[0]["age"] = -8
    assert load_rows(episodes, background, summary, _mapping()).missing_age_cases == 1
    background[0]["age"] = 40
    summary[0]["tmain3"] = 479
    result = load_rows(episodes, background, summary, _mapping())
    assert result.summary_mismatches[0][0] == result.diaries[0].day_id


def test_gaps_not_filled():
    episodes, background, summary = _rows()
    episodes[0]["start"] = 490
    episodes[0]["time"] = 10
    summary[0]["tottime"] = 1430
    summary[0]["tmain9"] = 10
    result = load_rows(episodes, background, summary, _mapping())
    assert "gap" in validate_diary(result.diaries[0]).reasons
