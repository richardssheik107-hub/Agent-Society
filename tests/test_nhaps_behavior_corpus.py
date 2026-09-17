from social_sim.human_data.models import BehaviorCorpus, BehaviorDay, HumanActivityEpisode, HumanActivityType, merge_adjacent_same_activity
from social_sim.human_data.stats import summarize


def test_nested_sampling_and_midnight_clock():
    from social_sim.human_data.models import HumanDayDiary

    days = []
    for i in range(12):
        day_id = f"nhaps:{i}"
        episodes = (HumanActivityEpisode(str(i), day_id, 1, 0, 60, 60, "3", "sleep", HumanActivityType.SLEEP, "1", "NHAPS_AHTUS_1992_94"),
                    HumanActivityEpisode(str(i), day_id, 2, 60, 120, 60, "4", "imputed sleep", HumanActivityType.SLEEP, "1", "NHAPS_AHTUS_1992_94"))
        days.append(HumanDayDiary(str(i), day_id, episodes, 120, {"diary_start_clock_minute": 0}))
    corpus = BehaviorCorpus([BehaviorDay(d.day_id, merge_adjacent_same_activity(d.episodes), d.metadata) for d in days])
    assert set(d.day_id for d in corpus.sample_days(5, 42)) < set(d.day_id for d in corpus.sample_days(10, 42))
    stats = summarize(tuple(days))
    assert stats["start_bins"][("SLEEP", 0)] == 12
    assert stats["canonical_merged_episode_count"] == 12


def test_weighted_diary_quantiles():
    from scripts.build_nhaps_ahtus_behavior_corpus import weighted_distribution

    stats = weighted_distribution([(10, 0.0), (20, 1.0), (30, 3.0)])
    assert stats["mean"] == 27.5
    assert stats["median"] == 30
    assert stats["count_positive_weight"] == 2
