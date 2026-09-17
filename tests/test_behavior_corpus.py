from social_sim.human_data.models import BehaviorCorpus, BehaviorDay


def test_nested_deterministic_sampling_without_oversampling():
    corpus = BehaviorCorpus([BehaviorDay(str(i), ()) for i in range(1200)])
    small = {day.day_id for day in corpus.sample_days(100, 42)}
    large = {day.day_id for day in corpus.sample_days(1000, 42)}
    assert small < large
    assert corpus.get_day("1").day_id == "1"
    try:
        corpus.sample_days(1201, 42)
    except ValueError:
        pass
    else:
        assert False, "oversampling accepted"
