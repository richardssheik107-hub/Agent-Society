"""Ablation artifacts expose raw tables without prompts, secrets, or winners."""

import csv
import json

import pytest

from social_sim.evaluation.ablation_metrics import aggregate_ablation_metrics
from social_sim.evaluation.ablation_report import write_ablation_report
from test_ablation_metrics import CONFIG_HASH, RESTAURANT, make_episode, make_step


def test_report_writes_policy_and_cell_tables_and_manifest(tmp_path) -> None:
    episodes = [
        make_episode(
            "C0_state", "S1_LAST_REJECTION",
            (make_step("BUY", "meal", accepted=False, reason="NOT_AT_SELLER"),),
            success=False, prelude_rejections=1,
        ),
        make_episode(
            "C1_last", "S1_LAST_REJECTION",
            (make_step("MOVE", "restaurant", accepted=True, reason="ACCEPTED", after=RESTAURANT),),
            prelude_rejections=1,
        ),
    ]
    policies = ("C0_state", "C1_last")
    scenarios = ("S1_LAST_REJECTION", "S2_BURIED_REJECTION")
    summary = aggregate_ablation_metrics(episodes, policies=policies, scenarios=scenarios)
    report = write_ablation_report(
        tmp_path, summary, episodes,
        policies=policies,
        scenarios=scenarios,
        repetitions_per_cell=2,
        provider_alias="ark-code-latest",
        experiment_config_hash=CONFIG_HASH,
        created_at="2026-09-16T00:00:00+00:00",
    )
    policy_json = json.loads(report.policy_metrics_json.read_text(encoding="utf-8"))
    cell_json = json.loads(report.policy_scenario_metrics_json.read_text(encoding="utf-8"))
    manifest = json.loads(report.dataset_manifest.read_text(encoding="utf-8"))
    markdown = report.summary_markdown.read_text(encoding="utf-8")
    with report.summary_csv.open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    assert policy_json["policies"]["C0_state"]["prelude_rejection_count"] == 1
    assert policy_json["policies"]["C0_state"]["model_rejection_count"] == 1
    assert cell_json["cells"]["C1_last"]["S1_LAST_REJECTION"]["first_rejection_repeat_rate"] == 0
    assert len(rows) == 4
    assert next(row for row in rows if row["scenario"] == "S2_BURIED_REJECTION")["first_rejection_repeat_rate"] == "N/A"
    assert next(row for row in rows if row["scenario"] == "S2_BURIED_REJECTION")["first_rejection_eligible_episodes"] == "0"
    assert manifest["trajectory_schema_version"] == "0.1"
    assert manifest["experiment_type"] == "context_ablation"
    assert manifest["episode_count"] == 2
    assert manifest["step_count"] == 2
    assert manifest["repetitions_per_cell"] == 2
    assert manifest["contains_hidden_reasoning"] is False
    assert manifest["contains_raw_prompt"] is False
    assert "## Overall by Policy" in markdown
    assert "## Policy × Scenario" in markdown
    assert "Prelude rejections" in markdown
    assert "N/A (n=0)" in markdown
    assert "Provider error rate excludes TIMEOUT" in markdown
    assert "BEST POLICY" not in markdown
    with pytest.raises(FileExistsError):
        write_ablation_report(
            tmp_path, summary, episodes, policies=policies, scenarios=scenarios,
            repetitions_per_cell=2, provider_alias="ark-code-latest",
            experiment_config_hash=CONFIG_HASH,
        )


def test_report_flags_backend_change_and_rejects_mismatched_hash(tmp_path) -> None:
    first = make_episode(
        "C0_state", "S0_BASELINE",
        (make_step("MOVE", "restaurant", accepted=True, reason="ACCEPTED", after=RESTAURANT),),
    )
    second = make_episode(
        "C1_last", "S0_BASELINE",
        (make_step("MOVE", "restaurant", accepted=True, reason="ACCEPTED", after=RESTAURANT,
                   provider_model="glm-5.4"),),
    )
    episodes = [first, second]
    summary = aggregate_ablation_metrics(episodes)
    report = write_ablation_report(
        tmp_path, summary, episodes, policies=("C0_state", "C1_last"),
        scenarios=("S0_BASELINE",), repetitions_per_cell=2,
        provider_alias="ark-code-latest", experiment_config_hash=CONFIG_HASH,
    )
    assert "MODEL_BACKEND_STABLE=NO" in report.summary_markdown.read_text(encoding="utf-8")
    assert "MODEL_BACKEND_CHANGED_DURING_EXPERIMENT" in report.summary_markdown.read_text(encoding="utf-8")
    assert "## By Actual Provider Backend" in report.summary_markdown.read_text(encoding="utf-8")
    policy_data = json.loads(report.policy_metrics_json.read_text(encoding="utf-8"))
    cell_data = json.loads(report.policy_scenario_metrics_json.read_text(encoding="utf-8"))
    assert policy_data["backend_policy_metrics"]["glm-5.3"]["C0_state"]["episodes"] == 1
    assert cell_data["backend_cells"]["glm-5.4"]["C1_last"]["S0_BASELINE"]["episodes"] == 1
    with pytest.raises(ValueError, match="experiment_config_hash"):
        write_ablation_report(
            tmp_path / "other", summary, episodes, policies=("C0_state", "C1_last"),
            scenarios=("S0_BASELINE",), repetitions_per_cell=2,
            provider_alias="ark-code-latest", experiment_config_hash="b" * 64,
        )


def test_report_separates_mixed_episode_from_step_provider_models(tmp_path) -> None:
    mixed = make_episode(
        "C0_state", "S1_LAST_REJECTION",
        (
            make_step("BUY", "meal", accepted=False, reason="NOT_AT_SELLER",
                      provider_model="glm-5.3", context_chars=200, input_tokens=100),
            make_step("MOVE", "restaurant", accepted=True, reason="ACCEPTED",
                      after=RESTAURANT, provider_model="glm-5.4", context_chars=300,
                      input_tokens=120),
        ),
        prelude_rejections=1,
    )
    summary = aggregate_ablation_metrics([mixed])
    report = write_ablation_report(
        tmp_path, summary, [mixed], policies=("C0_state",),
        scenarios=("S1_LAST_REJECTION",), repetitions_per_cell=2,
        provider_alias="ark-code-latest", experiment_config_hash=CONFIG_HASH,
    )
    cells = json.loads(report.policy_scenario_metrics_json.read_text(encoding="utf-8"))
    policy = json.loads(report.policy_metrics_json.read_text(encoding="utf-8"))
    markdown = report.summary_markdown.read_text(encoding="utf-8")
    model_cells = cells["provider_model_steps"]
    assert model_cells["glm-5.3"]["C0_state"]["S1_LAST_REJECTION"]["rejected_actions"] == 1
    assert model_cells["glm-5.4"]["C0_state"]["S1_LAST_REJECTION"]["rejected_actions"] == 0
    assert cells["backend_cells"]["MIXED_BACKEND"]["C0_state"]["S1_LAST_REJECTION"]["episodes"] == 1
    assert policy["backend_episode_success_attributable"]["MIXED_BACKEND"] is False
    assert "N/A (not attributable)" in markdown
    assert "Episode success is not attributed" in markdown


def test_first_repeat_is_na_for_baseline_and_failed_first_request(tmp_path) -> None:
    baseline = make_episode(
        "C0_state", "S0_BASELINE",
        (make_step("MOVE", "restaurant", accepted=True, reason="ACCEPTED", after=RESTAURANT),),
    )
    no_first_step = make_episode(
        "C0_state", "S1_LAST_REJECTION", (), success=False, prelude_rejections=1,
    )
    no_first_step.termination_reason = "PROVIDER_ERROR"
    no_first_step.provider_errors = 1
    summary = aggregate_ablation_metrics([baseline, no_first_step])
    report = write_ablation_report(
        tmp_path, summary, [baseline, no_first_step], policies=("C0_state",),
        scenarios=("S0_BASELINE", "S1_LAST_REJECTION"), repetitions_per_cell=2,
        provider_alias="ark-code-latest", experiment_config_hash=CONFIG_HASH,
    )
    with report.summary_csv.open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    assert [row["first_rejection_repeat_rate"] for row in rows] == ["N/A", "N/A"]
    assert [row["first_rejection_eligible_episodes"] for row in rows] == ["0", "0"]
    assert "N/A (n=0)" in report.summary_markdown.read_text(encoding="utf-8")
