from pathlib import Path

import pytest
import yaml

from social_sim.human_data.models import HumanActivityType
from social_sim.human_data.nhaps_ahtus import NhapsMapping


MAPPING = Path(__file__).resolve().parents[1] / "config/nhaps_ahtus_activity_mapping.yaml"


def test_mapping_is_exact_and_conservative():
    rules = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))["rules"]
    labels = {r["source_code"]: r["source_label"] for r in rules}
    labels.update({6: "wash, dress, personal care", 20: "food preparation, cooking"})
    mapping = NhapsMapping(MAPPING, labels)
    assert mapping.classify(3)[0] == HumanActivityType.SLEEP
    assert mapping.classify(10)[0] == HumanActivityType.WORK
    assert mapping.classify(93)[0] == HumanActivityType.MOVE
    assert mapping.classify(6)[0] == HumanActivityType.OTHER
    assert mapping.classify(20)[0] == HumanActivityType.OTHER


def test_mapping_rejects_mismatched_real_metadata():
    with pytest.raises(ValueError, match="metadata label mismatch"):
        NhapsMapping(MAPPING, {3: "not sleep"})
