"""Offline prompt audit: exact frozen inputs, safe summaries and no client import."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from social_sim.continuity.action_projection import FEASIBLE, RAW
from social_sim.continuity.models import canonical_json, digest
from social_sim.continuity.q6_2_outcome_prompt import (
    EXTRA_INSTRUCTION,
    FROZEN_PROTOCOL_HASH,
    _expected_allocations,
    _rebuild_scenario,
    audit_prompt_intervention,
    summarize_prompt_pair,
)

ROOT = Path(__file__).resolve().parents[1]
# Hashes and length facts frozen by ae2123f, not raw prompt or provider output.
FROZEN_PROMPT_FACTS = (
    ("8da3d44503d69c9890ff5cfd0d971e31bc5ffd8779d86efa62a6a4c48022ad1b",
     "13936c437736c056fbd6734deedca216695b02c365a638d69f4e3e701020c0a1", 10, 1236, 1772),
    ("2e3128b71e7ab6fae1ef7c101dc7d65b2339bef436d1fe4acbd3990ec28edd14",
     "346034ecbb437fb8c0607a70dd38b58419355523e6abc7fa06582550c446be6c", 11, 1236, 1810),
    ("9b1c897ae16188ae2cf029438c2466105542ba9bb9c9cc45d6d818e7d9923c24",
     "da440168b70bab7c25d3b9cc13badb1e43cbee926fc45b85af3c6a4837c4ad8a", 7, 1243, 1659),
    ("e1f542dc3ad94e259fd7eaefcca8a78a7d6d6c7fda5eb001bf961ec69230ec31",
     "6d3c1e3d9eaa6ceef3deb4717a1dd7109ec78c1ac4bc0c1ae971bcdef931a9b3", 7, 1245, 1661),
    ("7d47c251146193bad9b21894f3a57447d47ca67e95653a1318f2cf65b5c84888",
     "5b7e9099b988be7063bbbde26eff0af238ef96ebfd56a6d618c8362a95447d9b", 10, 1238, 1774),
    ("65a1b2c66efa5ffac0d8de866af8c360f2f30cce8a50a01b4f5e51e6677ff0ee",
     "458f6f38ac05a63b66ae93d8a2bbf27b27e92e6de596b93cea3936b7ffb135a2", 9, 1245, 1740),
    ("adbf69ba7a85ff6c1fad2a2d3a3a09097d29225dd0ce402ef9bf129dec858b4b",
     "a23be0c8f42bd2d6f10487c767310a644a2173abbcf6d824e30dbeae215013d6", 10, 1236, 1772),
    ("040960eab7d35a4e29f719bf9522455fc62c2342f69f69126c65e8541ef9fe5c",
     "5f260694e0c5695aa73a6c6aca537cbf13cdc2eb33faf5be9df0869e8f1bf672", 8, 1239, 1693),
    ("20987621f5a063f48dc663cc4e50e8f2d630dd2307588f1a4ba4e0c5e022400a",
     "4484b7f541e62934509f1a1b46afaeb57c79e55857140717aee6ac865af5a4cc", 10, 1234, 1770),
    ("473fff647bbd8f5af6358e3d09826d63e6aa0248c08cb1570c727305f08375ad",
     "42d0a0133f45c1c8a9d00f3040661b37d10c905dac9a6b79e7c67b50fa1da943", 9, 1234, 1729),
    ("cb571acdd78d2e5c545d840c0f54d2e9ab9f671b1894bc590cfec5da6272e983",
     "5f11f3a712b9c4047402f656ddc4af941a505d5557567b15fbe4dc3b2102c513", 10, 1234, 1770),
    ("889a1dee69422de0b132dcd3bfe499d114e86403047d0b4a75a10b03790d1be7",
     "f81f7caaddc8b3392d17ffba15fb1c21ffb363d29996877019835b2c065a5ab9", 9, 1235, 1730),
)


@pytest.fixture(scope="module")
def panel():
    protocol = json.loads((ROOT / "config/experimental/q6_2_fixed_state_panel_v2.json").read_text())
    assert digest(protocol) == FROZEN_PROTOCOL_HASH
    scenarios = [_rebuild_scenario(row, protocol) for row in protocol["scenarios"]]
    allocated = _expected_allocations(protocol)
    by_scenario = {row["scenario_id"]: row for row in scenarios}
    cells = []
    for allocation in allocated:
        scenario, mode = by_scenario[allocation["scenario_id"]], allocation["condition"]
        missing = allocation["cell_id"] in {"c027", "c041"}
        cells.append({**allocation, "prompt_hash": scenario["prompt_hashes"][mode],
                      "prompt_chars": scenario["prompt_chars"][mode],
                      "candidate_hash": scenario["candidate_hash"],
                      "candidate_count": scenario["candidate_count"],
                      "input_tokens": None if missing else (300 if mode == RAW else 400),
                      "proposal_activity": None if missing else ("TRAVEL" if mode == RAW else "MEAL")})
    return protocol, scenarios, allocated, cells


def test_twelve_frozen_prompt_hashes_and_utf8_lengths(panel):
    for scenario, expected in zip(panel[1], FROZEN_PROMPT_FACTS, strict=True):
        a_hash, b_hash, count, a_chars, b_chars = expected
        assert scenario["prompt_hashes"] == {RAW: a_hash, FEASIBLE: b_hash}
        assert scenario["prompt_chars"] == {RAW: a_chars, FEASIBLE: b_chars}
        assert scenario["prompt_bytes"] == {RAW: a_chars + 34, FEASIBLE: b_chars + 34}
        assert scenario["candidate_count"] == count


def test_all_scenarios_and_cells_attested_and_no_causal_claim(panel):
    result = audit_prompt_intervention(*panel)
    assert result["audit_status"] == "PASS"
    assert len(result["scenarios"]) == 12 and len(result["cells"]) == 48
    assert all(row["frozen_cell_attestation"] == "PASS" for row in result["cells"])
    assert result["meal_before_travel_scenarios"] == 12
    assert result["meal_travel_comparable_scenarios"] == 12
    assert result["causal_mechanism_isolated"] is False
    assert result["evaluation_type"] == "EXPLORATORY_POST_HOC"
    assert result["new_real_provider_requests"] == 0
    assert result["input_token_observations"][RAW] == {
        "known_subtotal": 6900, "known": 23, "missing": 1, "eligible": 24}
    assert result["input_token_observations"][FEASIBLE]["missing"] == 1
    assert result["observed_activity_distribution"] == {RAW: {"TRAVEL": 23}, FEASIBLE: {"MEAL": 23}}
    assert [row["input_tokens"] for row in result["cells"]].count(None) == 2
    assert not {"global_score", "human_likeness_score", "human_need_score"} & result.keys()


@pytest.mark.parametrize("field", ["prompt_hash", "prompt_chars", "candidate_hash", "candidate_count"])
def test_cell_prompt_input_tampering_stops(panel, field):
    changed = copy.deepcopy(panel)
    changed[3][0][field] = "NOT_FROZEN"
    with pytest.raises(ValueError, match="OUTCOME_CELL_FROZEN_PROMPT_MISMATCH"):
        audit_prompt_intervention(*changed)


@pytest.mark.parametrize("field", ["state_hash", "observation_hash", "prompt_bytes", "prompt_hashes"])
def test_manifest_tampering_stops(panel, field):
    changed = copy.deepcopy(panel)
    changed[1][0][field] = "NOT_FROZEN"
    with pytest.raises(ValueError, match="OUTCOME_FROZEN_SCENARIO_PROMPT_MISMATCH"):
        audit_prompt_intervention(*changed)


@pytest.mark.parametrize("field,value", [("scenario_id", "s12"), ("repeat", 2), ("pair_id", "p024")])
def test_observed_cell_pair_identity_cannot_drift(panel, field, value):
    changed = copy.deepcopy(panel)
    changed[3][0][field] = value
    with pytest.raises(ValueError, match="OUTCOME_CELL_ALLOCATION_MISMATCH"):
        audit_prompt_intervention(*changed)


def test_protocol_change_not_accepted_as_original(panel):
    changed = copy.deepcopy(panel)
    changed[0]["max_prompt_chars"] += 1
    with pytest.raises(ValueError, match="OUTCOME_FROZEN_PROTOCOL_HASH_MISMATCH"):
        audit_prompt_intervention(*changed)


def test_allocated_schedule_not_reordered(panel):
    changed = copy.deepcopy(panel)
    changed[2].reverse()
    with pytest.raises(ValueError, match="OUTCOME_FROZEN_ALLOCATION_MISMATCH"):
        audit_prompt_intervention(*changed)


def test_missing_and_duplicate_cells_not_synthesized(panel):
    changed = copy.deepcopy(panel)
    changed[3].pop()
    with pytest.raises(ValueError, match="OUTCOME_PROMPT_PANEL_DIMENSION_MISMATCH"):
        audit_prompt_intervention(*changed)
    changed = copy.deepcopy(panel)
    changed[3][1] = changed[3][0]
    with pytest.raises(ValueError, match="OUTCOME_PROMPT_IDENTITIES_MISMATCH"):
        audit_prompt_intervention(*changed)


def synthetic_pair(options=None, secret="synthetic-sensitive-text"):
    facts = {"destinations": ["home"], "observation": {"name": secret}}
    options = options if options is not None else [
        {"activity": "MEAL", "target": "food_bread"},
        {"activity": "MEAL", "target": "food_meal"},
        {"activity": "TRAVEL", "target": "restaurant"},
    ]
    return ("Frozen ordinary system.", canonical_json(facts),
            "Frozen ordinary system." + EXTRA_INSTRUCTION,
            canonical_json({**facts, "executable_options": options}))


def test_prefix_structure_order_and_exposure_counts():
    row = summarize_prompt_pair(*synthetic_pair())
    assert row["system_a_exact_prefix_of_b"] is True
    assert row["system_equal"] is False
    assert row["user_a_exact_prefix_of_b"] is False
    assert row["shared_observation_equal"] is True
    assert row["candidate_activity_counts"]["MEAL"] == 2
    assert row["candidate_activity_positions_one_based"]["MEAL"] == [1, 2]
    assert row["candidate_activity_positions_one_based"]["TRAVEL"] == [3]
    assert row["meal_before_all_travel"] is True
    assert row["preference_ranking"] is False
    assert row["meal_macro_steps_in_b_candidates"] == "NOT_EXPLICITLY_EXPANDED"


def test_no_meal_exposure_does_not_fabricate_order_evidence():
    row = summarize_prompt_pair(*synthetic_pair([{"activity": "TRAVEL", "target": "home"}]))
    assert row["meal_and_travel_both_exposed"] is False
    assert row["meal_before_all_travel"] is False


def test_summary_does_not_emit_arbitrary_prompt_text_or_secret():
    secret = "synthetic-sensitive-token"
    result = summarize_prompt_pair(*synthetic_pair(secret=secret))
    encoded = canonical_json(result)
    assert secret not in encoded
    assert "Frozen ordinary system" not in encoded
    assert "food_bread" not in encoded
    assert EXTRA_INSTRUCTION not in encoded


@pytest.mark.parametrize("options", [
    [{"activity": "TRAVEL", "target": "home"}, {"activity": "MEAL", "target": "food_meal"}],
    [{"activity": "MEAL", "target": "food_meal"}] * 2,
])
def test_unsorted_or_duplicate_candidates_stop(options):
    with pytest.raises(ValueError, match="FROZEN_CANDIDATE_ORDER_MISMATCH"):
        summarize_prompt_pair(*synthetic_pair(options))


def test_extra_instruction_and_observation_must_be_exact():
    a, u_a, b, u_b = synthetic_pair()
    with pytest.raises(ValueError, match="FROZEN_SYSTEM_APPEND_MISMATCH"):
        summarize_prompt_pair(a, u_a, b + " changed", u_b)
    changed = json.loads(u_b)
    changed["observation"]["name"] = "changed"
    with pytest.raises(ValueError, match="FROZEN_OBSERVATION_CHANGED"):
        summarize_prompt_pair(a, u_a, b, canonical_json(changed))


def test_unknown_candidate_and_json_key_cannot_escape_summary():
    with pytest.raises(ValueError, match="FROZEN_CANDIDATE_STRUCTURE_MISMATCH"):
        summarize_prompt_pair(*synthetic_pair([{"activity": "private-model-text", "target": None}]))
    a, u_a, b, u_b = synthetic_pair()
    changed = json.loads(u_b)
    changed["private-secret-key"] = "private-secret-value"
    with pytest.raises(ValueError, match="FROZEN_USER_STRUCTURE_MISMATCH"):
        summarize_prompt_pair(a, u_a, b, canonical_json(changed))


def test_input_extra_fields_never_exported(panel):
    changed = copy.deepcopy(panel)
    changed[1][0]["completion"] = "synthetic-sensitive-completion"
    changed[3][0]["Authorization"] = "synthetic-sensitive-auth"
    result = audit_prompt_intervention(*changed)
    assert "synthetic-sensitive" not in canonical_json(result)


@pytest.mark.parametrize("value", [True, -1, "private-text"])
def test_invalid_token_observation_rejected(panel, value):
    changed = copy.deepcopy(panel)
    changed[3][0]["input_tokens"] = value
    with pytest.raises(ValueError, match="OUTCOME_INPUT_TOKEN_TYPE_MISMATCH"):
        audit_prompt_intervention(*changed)


def test_import_and_rebuild_have_no_real_client_import_graph():
    # Fresh interpreter matters: another test may have imported legacy runners.
    script = """
import builtins, json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path('src').resolve()))
original_import = builtins.__import__
forbidden = ('social_sim.decision', 'social_sim.provider_runtime',
             'social_sim.continuity.q6_1', 'social_sim.continuity.q6_2_panel_fixtures')
def guarded(name, *args, **kwargs):
    if any(name == prefix or name.startswith(prefix + '.') for prefix in forbidden):
        raise AssertionError('FORBIDDEN_CLIENT_IMPORT')
    return original_import(name, *args, **kwargs)
builtins.__import__ = guarded
from social_sim.continuity.q6_2_outcome_prompt import _rebuild_scenario
protocol = json.loads(Path('config/experimental/q6_2_fixed_state_panel_v2.json').read_text())
row = _rebuild_scenario(protocol['scenarios'][5], protocol)
assert row['scenario_id'] == 's06'
assert not any(any(name == prefix or name.startswith(prefix + '.') for prefix in forbidden)
               for name in sys.modules)
assert os.environ['CONTINUITY_API_KEY'] == 'synthetic-only-key'
print('NO_API_CLIENT_IMPORT_OR_REQUEST_PASS')
"""
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT,
        env={**os.environ, "CONTINUITY_API_KEY": "synthetic-only-key"},
        text=True, capture_output=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "NO_API_CLIENT_IMPORT_OR_REQUEST_PASS"
