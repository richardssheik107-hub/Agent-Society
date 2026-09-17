from social_sim.calibration.duration import comparisons, duration_stats
from tests.test_behavior_ontology_calibration import make_day


def test_episode_and_daily_distinct_and_instantaneous_not_comparable():
    stats = duration_stats((make_day(),), ("PERSONAL_CARE", "CHORES"))
    assert stats["CHORES"]["episode"]["median"] == 120
    assert stats["CHORES"]["daily"]["median"] == 120
    assert stats["PERSONAL_CARE"]["episode"]["median"] == 60
    result = {x.activity: x for x in comparisons(stats)}
    assert result["EAT"].comparison_status == "NOT_COMPARABLE"
    assert result["MOVE"].comparison_status == "NOT_COMPARABLE"
    assert result["CHORES"].recommended_candidate == 120
    assert result["SLEEP"].recommended_candidate == 360
