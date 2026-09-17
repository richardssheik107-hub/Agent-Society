from social_sim.calibration.coverage import measure
from social_sim.calibration.ontology import SOURCE_BY_CODE, TARGET_MINUTE_COVERAGE, select_minimal_ontology
from social_sim.human_data.models import HumanActivityEpisode, HumanActivityType, HumanDayDiary


def make_day(codes=(3, 6, 20, 22)):
    canonical = {3: HumanActivityType.SLEEP, 6: HumanActivityType.OTHER, 20: HumanActivityType.OTHER, 22: HumanActivityType.OTHER}
    episodes = tuple(HumanActivityEpisode("p", "d", index, (index - 1) * 60, index * 60, 60, str(code), "test", canonical[code], "1", "NHAPS_AHTUS_1992_94") for index, code in enumerate(codes, 1))
    return HumanDayDiary("p", "d", episodes, 60 * len(codes))


def test_explicit_domain_mapping_and_coverage_ladder():
    assert SOURCE_BY_CODE[6].domain == "PERSONAL_CARE"
    assert SOURCE_BY_CODE[20].domain == "CHORES"
    values = [measure((make_day(),), domains) for domains in ((), ("PERSONAL_CARE",), ("CHORES",), ("PERSONAL_CARE", "CHORES"))]
    assert [x["minute_coverage"] for x in values] == [.25, .5, .75, 1]
    assert [x["episode_coverage"] for x in values] == [.25, .5, .75, 1]
    assert TARGET_MINUTE_COVERAGE == .90


def test_minimal_selector_is_bounded_and_deterministic():
    mapping = {(): .82, ("PERSONAL_CARE",): .86, ("CHORES",): .91, ("PERSONAL_CARE", "CHORES"): .94}
    assert select_minimal_ontology(mapping) == ("CHORES",)
    assert select_minimal_ontology({key: value - .03 for key, value in mapping.items()}) == ("PERSONAL_CARE", "CHORES")
    assert select_minimal_ontology({key: value - .10 for key, value in mapping.items()}) is None
