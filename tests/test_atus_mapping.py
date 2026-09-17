from pathlib import Path

from social_sim.human_data.mapping import load_mapping
from social_sim.human_data.models import HumanActivityType


MAPPING = Path(__file__).resolve().parents[1] / "config/atus_activity_mapping.yaml"


def test_explicit_mapping_and_other_fallback():
    mapping = load_mapping(MAPPING)
    assert mapping.classify("010101")[0] is HumanActivityType.SLEEP
    assert mapping.classify("010102")[0] is HumanActivityType.OTHER
    assert mapping.classify("050101")[0] is HumanActivityType.WORK
    assert mapping.classify("050201")[0] is HumanActivityType.OTHER
    assert mapping.classify("110101")[0] is HumanActivityType.EAT
    assert mapping.classify("120301")[0] is HumanActivityType.LEISURE
    assert mapping.classify("130101")[0] is HumanActivityType.OTHER
    assert mapping.classify("180501")[0] is HumanActivityType.MOVE
    assert mapping.classify("181801")[0] is HumanActivityType.OTHER
