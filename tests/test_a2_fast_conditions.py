"""Fixed 20-cell design and completed-cell-only comparisons."""

from social_sim.behavior_prior.benchmark import CONDITIONS, aggregate_condition, matched_comparisons, schedule


def test_five_conditions_and_rotated_twenty_cell_schedule():
    assert [(c.name, c.corpus, c.prior_limit) for c in CONDITIONS] == [
        ("C0", None, 0), ("C1", "B100", 1), ("C2", "B1000", 1),
        ("C3", "BALL", 1), ("C4", "BALL", 3),
    ]
    rows = schedule()
    assert len(rows) == 20
    assert [row["episode"] for row in rows] == list(range(1, 21))
    assert [row["condition"] for row in rows[:5]] == [c.name for c in CONDITIONS]
    assert [row["condition"] for row in rows[5:10]] == ["C2", "C3", "C4", "C0", "C1"]
    assert len({(row["segment"], row["condition"]) for row in rows}) == 20


def test_unmatched_truncated_episode_excluded_from_pairing():
    rows = [
        {"condition": "C0", "segment": "WORK", "segment_completion": True,
         "idle_minutes": 30, "idle_ratio": 0.2, "repeated_invalid_count": 0,
         "same_state_decision_count": 0, "decision_count": 3, "decision_burst_count": 0,
         "rejection_rate": 0.0, "unresolved_need_minutes": 0,
         "obligation_neglect_minutes": 0, "unique_activity_types": 2, "active_minutes": 150},
        {"condition": "C3", "segment": "WORK", "segment_completion": False,
         "idle_minutes": 0, "idle_ratio": 0, "repeated_invalid_count": 0,
         "same_state_decision_count": 0, "decision_count": 1, "decision_burst_count": 0,
         "rejection_rate": 0.0, "unresolved_need_minutes": 0,
         "obligation_neglect_minutes": 0, "unique_activity_types": 1, "active_minutes": 15},
    ]
    assert matched_comparisons(rows)["prior_effect_C0_C3"]["matched_complete_count"] == 0
    assert matched_comparisons(rows)["prior_effect_C0_C3"]["deltas_right_minus_left"]["idle_minutes"] is None
    assert aggregate_condition([])["complete_segments"] == 0
