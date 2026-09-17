from social_sim.human_data.models import HumanActivityEpisode, HumanActivityType


def test_episode_is_domain_neutral_and_checks_span():
    episode = HumanActivityEpisode("p", "d", 1, 0, 30, 30, "010101", "Sleeping", HumanActivityType.SLEEP, None, "ATUS_2025")
    assert episode.canonical_activity is HumanActivityType.SLEEP
    try:
        HumanActivityEpisode("p", "d", 1, 0, 30, 20, "010101", "Sleeping", HumanActivityType.SLEEP, None, "ATUS_2025")
    except ValueError:
        pass
    else:
        assert False, "mismatched span accepted"
