"""文档重组不容许断链、遗漏来源或把英文旧计划重新当阅读入口。"""
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("documentation_audit", ROOT / "scripts/audit_documentation.py")
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.fixture
def docs_copy(tmp_path):
    shutil.copytree(ROOT / "docs", tmp_path / "docs")
    shutil.copy2(ROOT / "README.md", tmp_path / "README.md")
    return tmp_path


def test_current_documents_are_indexed_chinese_and_reachable():
    result = MODULE.audit(include_history=False)
    assert result["status"] == "PASS", result["errors"]
    assert result["current_markdown_count"] == 29
    assert result["provider_requests"] == 0


def test_root_has_four_reader_routes():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    for route in ("docs/stages/README.md", "docs/current/research_status.md",
                  "docs/reports/README.md", "docs/review/README.md"):
        assert route in text


def test_original_documents_have_complete_migration_inventory():
    result = MODULE.audit()
    assert result["status"] == "PASS", result["errors"]
    assert result["old_markdown_count"] == 68
    assert result["removed_count"] == 59
    assert all(len(row["original_blob"]) == 40 for row in result["inventory"])


def test_broken_link_fails(docs_copy):
    path = docs_copy / "docs/README.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n[坏链接](missing.md)\n", encoding="utf-8")
    assert any("BROKEN_LINK" in e for e in MODULE.audit(docs_copy, include_history=False)["errors"])


def test_broken_anchor_fails(docs_copy):
    path = docs_copy / "docs/README.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n[坏锚点](review/decisions.md#d-99)\n", encoding="utf-8")
    assert any("BROKEN_ANCHOR" in e for e in MODULE.audit(docs_copy, include_history=False)["errors"])


def test_english_document_title_fails(docs_copy):
    path = docs_copy / "docs/reports/meeting_brief.md"
    path.write_text("# English Only\n" + "\n".join(path.read_text(encoding="utf-8").splitlines()[1:]), encoding="utf-8")
    assert any("NON_CHINESE_TITLE" in e for e in MODULE.audit(docs_copy, include_history=False)["errors"])


def test_orphan_document_fails(docs_copy):
    (docs_copy / "docs/orphan.md").write_text("# 孤立文档\n", encoding="utf-8")
    errors = MODULE.audit(docs_copy, include_history=False)["errors"]
    assert any("UNINDEXED_DOCUMENT" in e for e in errors)
    assert any("UNREACHABLE_DOCUMENT" in e for e in errors)


def test_external_english_reading_link_fails(docs_copy):
    path = docs_copy / "docs/README.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n[外部旧报告](https://example.invalid/report.md)\n", encoding="utf-8")
    assert any("EXTERNAL_READING_DOCUMENT" in e for e in MODULE.audit(docs_copy, include_history=False)["errors"])


def test_duplicate_navigation_entry_fails(docs_copy):
    path = docs_copy / "docs/reference/navigation.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["groups"]["总目录"].append("docs/README.md")
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert "DUPLICATE_NAVIGATION_ENTRY" in MODULE.audit(docs_copy, include_history=False)["errors"]


def test_unclosed_fence_fails(docs_copy):
    path = docs_copy / "docs/README.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n```text\n", encoding="utf-8")
    assert any("UNCLOSED_CODE_FENCE" in e for e in MODULE.audit(docs_copy, include_history=False)["errors"])


def test_code_example_links_are_not_treated_as_real_links():
    text, balanced = MODULE.without_fences("# 标题\n```text\n[example](nonexistent.md)\n```\n")
    assert balanced
    assert not MODULE.LINK.findall(text)


def test_no_git_history_is_a_failure_not_a_skip(docs_copy):
    result = MODULE.audit(docs_copy)
    assert result["status"] == "FAIL"
    assert any("AUDIT_INCOMPLETE" in e for e in result["errors"])


def test_all_review_questions_have_explicit_anchors():
    text = (ROOT / "docs/review/decisions.md").read_text(encoding="utf-8")
    assert {f"d-{n:02}" for n in range(1, 10)}.issubset(MODULE.anchors(text))
    assert "待审核" in text


def test_source_status_not_confused_with_behavioral_success():
    q4 = (ROOT / "docs/studies/q4_resource_visibility.md").read_text(encoding="utf-8")
    q5 = (ROOT / "docs/studies/q5_rule_scaling.md").read_text(encoding="utf-8")
    q61 = (ROOT / "docs/studies/q61_real_pilot.md").read_text(encoding="utf-8")
    q62 = (ROOT / "docs/studies/q62_action_projection.md").read_text(encoding="utf-8")
    assert "UNRESOLVED" in q4
    assert "不是完整千万对象世界已完成" in q5
    assert "INSUFFICIENT_EVIDENCE" in q61
    # The old autonomous short-chain and the newly executed fixed panel are
    # different protocols. Real execution is not proof of behavioral benefit.
    assert "旧8-call真实短链仍未运行" in q62
    assert "已完成唯一真实session" in q62
    assert "MODEL_BENEFIT=NO_CLEAR_DIFFERENCE" in q62
    assert "REAL_DATA_COVERAGE=PARTIAL" in q62
    assert "不证明两种提示等效" in q62
    assert "LONG_TERM_HUMAN_LIKENESS=NOT_TESTED" in q62
    assert "SHORT_HORIZON_STATE_CONTINUITY=INSUFFICIENT_EVIDENCE" in q62


def test_original_current_entrypoints_preserved():
    for name in ("README.md", "research_status.md", "three_core_questions_experiment_summary.md",
                 "plan.md", "runbook.md", "acceptance.md", "architecture.md", "repository.md", "branches.md"):
        assert (ROOT / "docs/current" / name).is_file()


def test_m15_outcome_audit_and_human_packet_are_separately_navigable():
    navigation = json.loads((ROOT / "docs/reference/navigation.json").read_text(encoding="utf-8"))
    assert "docs/studies/q62_outcome_audit.md" in navigation["groups"]["研究问题"]
    assert "docs/studies/q62_outcome_human_review.md" in navigation["groups"]["人工审核"]
    assert "d-09" in navigation["review_ids"]
    status = (ROOT / "docs/current/research_status.md").read_text(encoding="utf-8")
    assert "q62_outcome_audit.md" in status and "q62_outcome_human_review.md" in status
    assert "UNKNOWN" in status
    assert "HUMAN_REVIEW_COMPLETED=NO" in status
    assert "HUMAN_NEED_SATISFACTION_CONCLUSION=UNRESOLVED" in status
    assert "NEW_REAL_PROVIDER_REQUESTS=0" in status


def test_m15_posthoc_boundaries_do_not_rewrite_original_research_conclusions():
    study = (ROOT / "docs/studies/q62_action_projection.md").read_text(encoding="utf-8")
    plan = (ROOT / "docs/current/plan.md").read_text(encoding="utf-8")
    decisions = (ROOT / "docs/review/decisions.md").read_text(encoding="utf-8")
    report = (ROOT / "docs/studies/q62_outcome_audit.md").read_text(encoding="utf-8")
    for text in (study, plan, decisions):
        assert "EXPLORATORY_POST_HOC" in text
        assert "NO_CLEAR_DIFFERENCE" in text
        assert "UNRESOLVED" in text
        assert "NEW_REAL_PROVIDER_REQUESTS=0" in text
        assert "q62_outcome_human_review.md" in text
    assert "EXPLORATORY_POST_HOC" in report
    assert "UNKNOWN" in report
    assert "HUMAN_REVIEW_COMPLETED" in report and "NO" in report
    assert "q62_outcome_human_review.md" in report
    assert "待审核" in decisions.split('id="d-09"', 1)[1]
    assert "未实现、未运行、未验证" in decisions
    assert "不合成总分" in decisions


def test_m15_public_json_is_valid_complete_and_never_imputes_timeout_effects():
    result = json.loads((ROOT / "docs/reference/q62_outcome_audit_results.json").read_text(encoding="utf-8"))
    assert result["schema"] == "Q62_OUTCOME_SAFE_DELIVERY_V1"
    assert len(result["cells"]) == 48 and len(result["pairs"]) == 24
    assert result["aggregates"]["complete_pairs"] == 22
    assert result["source_integrity"]["file_count"] == 297
    assert len(result["source_integrity"]["source_file_hashes"]) == 297
    missing = [p for p in result["pairs"] if not p["complete"]]
    assert [p["pair_id"] for p in missing] == ["p014", "p021"]
    assert all(all(v is None for v in p["B_minus_A"].values()) for p in missing)
    timed_out = [c for c in result["cells"] if c["status"] == "PROVIDER_TIMEOUT"]
    assert len(timed_out) == 2
    assert all(c["hunger_relief"] is None and c["money_delta"] is None
               and c["minutes_elapsed"] is None for c in timed_out)
    assert result["markers"]["NEW_REAL_PROVIDER_REQUESTS"] == 0
    assert result["markers"]["ORIGINAL_Q62_CONCLUSION"] == "NO_CLEAR_DIFFERENCE"
    assert result["human_review_completed"] is False
    assert result["human_review_key_published"] is False
