import pytest

from social_sim.calibration.ontology import CORE5, DOMAIN_ORDER
from social_sim.calibration.profiles import recommendation
from social_sim.calibration.validation import validate_profile
from social_sim.calibration.validation import validate_coverage


def test_recommendation_gates_and_shadow_profile():
    assert recommendation(.93, .95, False, True) == "RECOMMENDED_FOR_NEXT_EXPERIMENT"
    assert recommendation(.89, .95, False, True) == "NOT_READY"
    assert recommendation(.93, .95, True, True) == "NOT_READY"
    profile = {"source": {"dataset": "NHAPS_AHTUS_1992_94", "archive_sha256": "x"},
               "ontology": {"status": "EXPERIMENTAL", "activities": [*CORE5, *DOMAIN_ORDER]},
               "coverage": {"all_adults": {"minute_coverage": .93}},
               "duration_candidates": {activity: 30 for activity in (*CORE5, *DOMAIN_ORDER)}}
    validate_profile(profile, "x", "RECOMMENDED_FOR_NEXT_EXPERIMENT")
    profile["duration_candidates"]["WORK"] = 0
    with pytest.raises(ValueError, match="invalid experimental duration"):
        validate_profile(profile, "x", "RECOMMENDED_FOR_NEXT_EXPERIMENT")


def test_coverage_reconciliation_rejects_stale_input():
    core5 = {"episodes": 4, "covered_episodes": 2, "minutes": 240, "covered_minutes": 120, "minute_coverage": .5}
    core7 = {"minute_coverage": .75, "covered_minutes": 180, "OTHER_remaining_minutes": 60, "minutes": 240}
    baseline = {"total_episodes": 4, "mapped_to_core_count": 2, "total_minutes": 240, "mapped_to_core_minutes": 120}
    validate_coverage(core5, core7, baseline)
    baseline["mapped_to_core_minutes"] = 119
    with pytest.raises(ValueError, match="Core5 minute counts"):
        validate_coverage(core5, core7, baseline)
