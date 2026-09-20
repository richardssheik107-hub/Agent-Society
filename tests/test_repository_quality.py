"""仓库整理不能悄悄丢测试，缺失外部数据必须可识别。"""
import ast
from pathlib import Path

from conftest import HISTORICAL_DATA_TESTS, HISTORICAL_INPUTS, ROOT, missing_historical_inputs


def test_historical_skip_registry_has_only_eight_existing_tests():
    assert len(HISTORICAL_DATA_TESTS) == 8
    for entry in HISTORICAL_DATA_TESTS:
        name, function = entry.split("::")
        tree = ast.parse((ROOT / name).read_text(encoding="utf-8"))
        assert any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and node.name == function for node in tree.body)
        assert not name.startswith("tests/test_continuity")


def test_historical_missing_inputs_are_explicit(tmp_path):
    assert missing_historical_inputs(tmp_path) == HISTORICAL_INPUTS
    for name in HISTORICAL_INPUTS:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture existence only; not used as human data", encoding="utf-8")
    # 存在后不再跳过；格式和 hash 仍由原 loader 严格检查。
    assert missing_historical_inputs(tmp_path) == ()


def test_archived_real_entrypoints_are_inert():
    for name in ("behavior_prior_corpus_resume_remaining.py", "behavior_prior_corpus_finalize_existing.py"):
        tree = ast.parse((ROOT / "smoke" / name).read_text(encoding="utf-8"))
        assert not any(isinstance(n, (ast.Import, ast.ImportFrom)) for n in ast.walk(tree))
        assert (ROOT / "archive/legacy_tools" / name).is_file()


def test_current_document_entrypoints_exist():
    for name in ("README.md", "repository.md", "research_status.md", "architecture.md", "plan.md", "runbook.md"):
        assert (ROOT / "docs/current" / name).is_file()
    assert Path(ROOT / "scripts/run_continuity.py").is_file()
