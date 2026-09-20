"""测试默认离线；只有明确依赖未入库真人语料的历史复核才按缺失条件跳过。"""
from __future__ import annotations

import os
import socket
from pathlib import Path

import pytest

# 上游在导入时检查配置；不读取用户 .env，也不使用真实凭据。
os.environ["AGENTSOCIETY_LLM_API_KEY"] = "offline-placeholder-not-a-secret"
os.environ["AGENTSOCIETY_LLM_API_BASE"] = "http://127.0.0.1:9/v1"
os.environ["AGENTSOCIETY_LLM_MODEL"] = "openai/offline-placeholder"
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_INPUTS = (
    "run/calibration/neutral_day_v1/calibration_manifest.json",
    "run/calibration/neutral_day_v1/behavior_days_core7_candidate.jsonl",
)
# 逐测试登记，不忽略整个文件，不把缺少真实语料伪装成合成数据通过。
HISTORICAL_DATA_TESTS = frozenset({
    "tests/test_a2_final.py::test_split_is_day_level_nested_and_reproducible",
    "tests/test_a2_final.py::test_heldout_scorer_uses_eval_only_and_is_deterministic",
    "tests/test_a2_final.py::test_fixed_panel_schedule_and_context_scope",
    "tests/test_behavior_prior_context.py::test_r0_equals_a20_g2_and_prior_is_only_delta",
    "tests/test_behavior_prior_context.py::test_formatter_short_neutral_and_no_probabilities",
    "tests/test_behavior_prior_index.py::test_nested_worker_corpus_reproducible",
    "tests/test_behavior_prior_index.py::test_index_reproducible_and_never_returns_other",
    "tests/test_behavior_prior_index.py::test_threshold_selection_uses_measured_sparsity",
})


def missing_historical_inputs(root: Path = ROOT) -> tuple[str, ...]:
    return tuple(name for name in HISTORICAL_INPUTS if not (root / name).is_file())


def pytest_addoption(parser):
    parser.addoption("--require-historical-data", action="store_true", default=False,
                     help="选中历史语料测试时，缺少真实输入直接失败，禁止跳过。")


def pytest_configure(config):
    config.addinivalue_line("markers", "historical_data: 依赖未提交的冻结真人语料")


def pytest_collection_modifyitems(config, items):
    selected = [item for item in items if item.nodeid.split("[", 1)[0] in HISTORICAL_DATA_TESTS]
    missing = missing_historical_inputs()
    if selected and missing and config.getoption("--require-historical-data"):
        raise pytest.UsageError("历史语料复核要求真实文件，缺少：" + ", ".join(missing))
    for item in selected:
        item.add_marker(pytest.mark.historical_data)
        if missing:
            item.add_marker(pytest.mark.skip(reason="冻结真人语料未入库：" + ", ".join(missing)))


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    missing = missing_historical_inputs()
    if missing:
        terminalreporter.write_line(
            "历史语料缺失：相关测试明确 SKIP；这不是完整历史实证复现。"
            "准备真实语料后使用 --require-historical-data 严格验收。"
        )


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("unit tests must not access the network")
    monkeypatch.setattr(socket.socket, "connect", fail)
    monkeypatch.setattr(socket, "create_connection", fail)
