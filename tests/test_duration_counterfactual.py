from social_sim.calibration.duration import DurationComparison, decision_frequency_counterfactual


def test_scripted_completion_replay_has_no_llm():
    values = {key: DurationComparison(key, current, None, None, None, None, "NOT_COMPARABLE", candidate, "fixture") for key, current, candidate in (("SLEEP", 360, 360), ("WORK", 90, 270), ("LEISURE", 60, 80))}
    result = decision_frequency_counterfactual(values)
    assert result["horizon_minutes"] == 1080
    assert result["current_profile_activity_completion_events"] == 10
    assert result["candidate_profile_activity_completion_events"] == 5
    assert result["current_profile_estimated_decisions_per_day"] == 11
    assert result["calibrated_profile_estimated_decisions_per_day"] == 6
    assert result["estimated_decision_reduction"] == 5
