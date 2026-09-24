"""补充契约边界：混合响应、冻结版本交接和历史文档保护。"""
from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

import httpx
import pytest

from social_sim.decision import OpenAICompatibleDecisionClient
from social_sim.provider_runtime.workflow import execute_session, run_preflight

CONFIG = {
    "base_url": "https://ark.cn-beijing.volces.com/api/coding/v3",
    "model": "ark-code-latest",
    "api_key": "offline-private-value",
}


def factory(extra):
    def build(config):
        def handler(request):
            return httpx.Response(
                200,
                json={
                    "model": "test-model",
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {
                                "role": "assistant",
                                "content": '{"activity":"SLEEP","target":null}',
                                **extra,
                            },
                        }
                    ],
                },
            )

        return OpenAICompatibleDecisionClient(
            **config,
            minimal_request=True,
            transport=httpx.MockTransport(handler),
        )

    return build


@pytest.mark.parametrize("extra", [{"tool_calls": [{}]}, {"refusal": "test-refusal"}])
def test_valid_json_with_tool_or_refusal_still_fails(tmp_path, extra):
    summary = asyncio.run(run_preflight(tmp_path / "pre", CONFIG, factory=factory(extra)))
    assert summary["result"] == "FAIL"
    assert summary["failure_stage"] == "PROVIDER_CONTRACT"
    assert summary["provider_requests"] == 1


def test_code_change_between_preflight_and_pilot_prevents_second_request(tmp_path):
    session = tmp_path / "s"
    session.mkdir()
    summary = asyncio.run(
        execute_session(
            session,
            CONFIG,
            {"repository": {"git_commit": "frozen"}},
            with_pilot=True,
            factory=factory({}),
            mode="OFFLINE",
            before_pilot=lambda: False,
        )
    )
    assert summary["preflight"] == "PASS"
    assert summary["termination_reason"] == "EXECUTION_FINGERPRINT_CHANGED"
    assert summary["total_provider_request_attempts"] == 1
    assert summary["attempt_3_executed"] is False
    assert not (session / "attempt_3").exists()


def test_retired_research_docs_remain_recoverable_from_pinned_git_history():
    """文档清理后不要求旧副本留在工作树，但冻结原文必须仍可从 Git 恢复。"""
    root = Path(__file__).resolve().parents[1]
    data = json.loads((root / "docs/current/cleanup_manifest.json").read_text(encoding="utf-8"))
    policy = data["document_retirement"]
    assert policy["policy"] == "PINNED_GIT_HISTORY_FOR_DOCS_ONLY"

    mapping_path = root / policy["mapping"]
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    expected = {
        "research_q3_object_set_necessity_real_attempt2.md": "docs/studies/q3_object_set.md",
        "research_q4_resource_set_size.md": "docs/studies/q4_resource_visibility.md",
        "research_q5_rule_engine_scaling.md": "docs/studies/q5_rule_scaling.md",
    }
    for name, replacement in expected.items():
        assert mapping["by_basename"][name] == replacement
        assert (root / replacement).is_file()
        frozen = subprocess.check_output(
            ["git", "show", f'{data["research_base"]}:docs/{name}'],
            cwd=root,
        )
        assert frozen
        assert not (root / "docs/archive/2026-09-20" / name).exists()
