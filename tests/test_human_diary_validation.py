from social_sim.human_data.models import HumanActivityEpisode, HumanActivityType, HumanDayDiary
from social_sim.human_data.validation import validate_diary


def _ep(index, start, end):
    return HumanActivityEpisode("p", "d", index, start, end, end - start, "010101", "Sleeping", HumanActivityType.SLEEP, None, "ATUS_2025")


def test_excludes_non_24_hour_diary():
    result = validate_diary(HumanDayDiary("p", "d", (_ep(1, 0, 100),), 100))
    assert not result.valid
    assert "not_24_hours" in result.reasons


def test_detects_overlap_and_index_error():
    result = validate_diary(HumanDayDiary("p", "d", (_ep(1, 0, 800), _ep(3, 700, 1440)), 1540))
    assert "overlap" in result.reasons
    assert "episode_index" in result.reasons
