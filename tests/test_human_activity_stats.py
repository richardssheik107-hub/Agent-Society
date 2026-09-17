from social_sim.human_data.models import HumanActivityEpisode, HumanActivityType, HumanDayDiary, merge_adjacent_same_activity
from social_sim.human_data.stats import summarize


def _ep(index, start, end, kind):
    return HumanActivityEpisode("p", "d", index, start, end, end - start, "x", "x", kind, None, "fixture")


def test_merge_before_transition_and_minute_coverage():
    episodes = (_ep(1, 0, 600, HumanActivityType.SLEEP), _ep(2, 600, 700, HumanActivityType.WORK), _ep(3, 700, 800, HumanActivityType.WORK), _ep(4, 800, 1440, HumanActivityType.OTHER))
    diary = HumanDayDiary("p", "d", episodes, 1440)
    assert len(merge_adjacent_same_activity(episodes)) == 3
    result = summarize((diary,))
    assert result["transitions"][("SLEEP", "WORK")] == 1
    assert result["transitions"][("WORK", "OTHER")] == 1
    assert result["transitions"][("WORK", "WORK")] == 0
    assert result["coverage"]["mapped_to_core_minutes"] == 800
    assert result["episode_duration"]["WORK"]["median"] == 200
