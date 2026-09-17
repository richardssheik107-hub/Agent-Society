from social_sim.calibration.coverage import measure, merged_shadow
from tests.test_behavior_ontology_calibration import make_day


def test_core7_remerges_raw_other_and_changes_transitions():
    day = make_day((3, 6, 20, 22))
    assert [e.activity for e in merged_shadow(day, ())] == ["SLEEP", "OTHER"]
    assert [e.activity for e in merged_shadow(day, ("PERSONAL_CARE", "CHORES"))] == ["SLEEP", "PERSONAL_CARE", "CHORES"]
    old = measure((day,), ())
    new = measure((day,), ("PERSONAL_CARE", "CHORES"))
    assert old["transition_coverage"] == 0
    assert new["transition_coverage"] == 1
    assert new["transition_counts"][("PERSONAL_CARE", "CHORES")] == 1
    assert ("CHORES", "CHORES") not in new["transition_counts"]
