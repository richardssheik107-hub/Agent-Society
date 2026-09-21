"""一次预检，条件通过后最多四次高层决策；不改提示、场景或状态规则。"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from .safety import append_event, atom, counter, exception_type, failure_stage, metadata, write_json

PREFLIGHT_SYSTEM = "Return only strict JSON. Do not include markdown."
PREFLIGHT_USER = 'Return exactly one valid proposal: {"activity":"SLEEP","target":null}'


def real_client(config: dict):
    from social_sim.decision import OpenAICompatibleDecisionClient
    return OpenAICompatibleDecisionClient(**config, minimal_request=True, timeout_seconds=60)


async def close_client(client, timeout: float = 5) -> str | None:
    if client is None:
        return None
    try:
        await asyncio.wait_for(client.aclose(), timeout=timeout)
    except Exception as error:
        return exception_type(error)
    return None


def report(path: Path, title: str, summary: dict) -> None:
    path.write_text(
        f"# {title}\n\n以下是本次执行生成的安全字段，不包含凭据、原始提示或原始响应。\n\n"
        + "```json\n" + json.dumps(summary, ensure_ascii=False, indent=2) + "\n```\n\n"
        + "请求计数表示客户端尝试，不保证服务端已收到；没有响应时不能推断模型身份。"
        + "预检不是连续行为实验，离线传输测试不是火山实测。\n",
        encoding="utf-8",
    )


async def run_preflight(directory: Path, config: dict, *, factory=real_client,
                        timeout: float = 60, mode: str = "REAL_PROVIDER_PREFLIGHT") -> dict:
    """调用者必须先完成授权、运行时、独占锁与全新目录检查。"""
    directory.mkdir(parents=True, exist_ok=False)
    client = None
    summary = {"experiment": "Q6_1_PROVIDER_RUNTIME_PREFLIGHT", "mode": mode,
               "result": "FAIL", "request_result": "NOT_RUN", "failure_stage": None,
               "exception_type": None, "cleanup_exception_type": None,
               "application_calls": 0, "provider_requests": 0, "http_status": None,
               "provider_model": None, "finish_reason": None, "input_tokens": None,
               "output_tokens": None, "reasoning_tokens": None,
               "requested_model": atom(config["model"], config["api_key"]),
               "strict_json_contract": "NOT_RUN", "server_receipt": "UNKNOWN"}
    write_json(directory / "summary.json", summary)
    phase = "CLIENT_CONSTRUCTION"
    started = time.monotonic()
    try:
        client = factory(config)
        phase = "REQUEST"
        append_event(directory / "progress.jsonl", {"stage": "REQUEST_STARTED", "attempt": 1})
        reply = await asyncio.wait_for(client.complete(PREFLIGHT_SYSTEM, PREFLIGHT_USER), timeout=timeout)
        summary.update(metadata(client))
        phase = "MODEL_OUTPUT"
        from social_sim.continuity.context import parse_proposal
        proposal = parse_proposal(reply.raw_text)
        if proposal != {"activity": "SLEEP", "target": None}:
            raise ValueError("PREFLIGHT_PROPOSAL_MISMATCH")
        summary["strict_json_contract"] = "PASS"
        if summary["http_status"] != 200:
            summary["failure_stage"] = "PROVIDER_CONTRACT"
        else:
            summary["request_result"] = "PASS"
    except Exception as error:
        summary["request_result"] = "FAIL"
        summary["exception_type"] = exception_type(error)
        summary.update(metadata(client))
        summary["failure_stage"] = ("MODEL_OUTPUT" if phase == "MODEL_OUTPUT" else
                                    "CLIENT_CONSTRUCTION" if phase == "CLIENT_CONSTRUCTION" and
                                    not isinstance(error, ImportError) else failure_stage(error, client))
        if phase == "MODEL_OUTPUT":
            summary["strict_json_contract"] = "FAIL"
    finally:
        summary["latency_seconds"] = round(time.monotonic() - started, 6)
        summary["application_calls"] = counter(getattr(client, "call_count", 0)) or 0
        summary["provider_requests"] = counter(getattr(client, "provider_request_count", 0)) or 0
        # 先保存首次失败/响应；关闭客户端的第二次异常不能覆盖它。
        write_json(directory / "summary.json", summary)
        summary["cleanup_exception_type"] = await close_client(client)
    if summary["http_status"] is not None:
        summary["server_receipt"] = "HTTP_RESPONSE_OBSERVED"
    if summary["cleanup_exception_type"] and summary["failure_stage"] is None:
        summary["failure_stage"] = "CLIENT_CLEANUP"
    passed = (summary["request_result"] == "PASS" and summary["provider_requests"] == 1
              and summary["application_calls"] == 1 and summary["cleanup_exception_type"] is None)
    summary["result"] = "PASS" if passed else "FAIL"
    summary["real_provider_attempted"] = mode == "REAL_PROVIDER_PREFLIGHT" and summary["provider_requests"] > 0
    append_event(directory / "progress.jsonl", {"stage": "PREFLIGHT_FINISHED", **summary})
    write_json(directory / "summary.json", summary)
    report(directory / "report_zh.md", "Q6.1 独立运行时预检", summary)
    return summary


def continuity_result(summary: dict, rows: list[dict], *, cleanup_error: str | None) -> str:
    """保守的本轮门槛；不改旧报告或旧指标，只拒绝无链路的假 PASS。"""
    if summary.get("final_invariants", {}).get("invariants") == "FAIL":
        return "NOT_SUPPORTED"
    if any(row.get("STATE_FEEDBACK_VISIBLE") is False for row in rows):
        return "NOT_SUPPORTED"
    complete = (len(rows) == 4 and summary.get("termination_reason") == "BUDGET_COMPLETED"
                and summary.get("completed_decisions") == 4 and cleanup_error is None)
    complete = complete and all(row.get("decision_status") == "DECISION_ACCEPTED" and
                                row.get("commitment_status") == "COMPLETED" for row in rows)
    feedback = len(rows) >= 2 and all(row.get("STATE_FEEDBACK_VISIBLE") is True for row in rows[:-1])
    changed = any(row.get("STATE_FEEDBACK_CHANGED") is True for row in rows[:-1])
    valid = summary.get("final_invariants", {}).get("invariants") == "PASS"
    return "SUPPORTED" if complete and feedback and changed and valid else "INSUFFICIENT_EVIDENCE"


async def run_pilot(directory: Path, config: dict, environment: dict, *, factory=real_client,
                    mode: str = "REAL_PROVIDER_PILOT") -> dict:
    """复用 Q61PilotRunner；重置的是新实验世界，不是四个决策之间的状态。"""
    from social_sim.continuity import ContinuityWorld
    from social_sim.continuity.benchmark import seed_demo
    from social_sim.continuity.q6_1 import Q61PilotRunner, write_artifacts
    directory.mkdir(parents=True, exist_ok=False)
    client = None
    rows = []
    summary = {"experiment": "Q6_1_REAL_SHORT_HORIZON_CONTINUITY", "mode": mode,
               "attempt_id": "attempt_3", "planned_decisions": 4,
               "termination_reason": "ARCHITECTURE_ERROR", "completed_decisions": 0,
               "application_calls": 0, "provider_requests": 0,
               "short_horizon_state_continuity": "INSUFFICIENT_EVIDENCE"}

    class ObservedRunner(Q61PilotRunner):
        def _row_base(self, *args, **kwargs):
            row = super()._row_base(*args, **kwargs)
            current = next((item for item in reversed(self.decision_runner.records)
                            if item.get("request_id") == row["request_id"]), {})
            row["exception_type"] = current.get("exception_type")
            # success Reply 不含 HTTP 状态/finish_reason；从同一请求的 envelope 获取。
            row.update(metadata(self.client))
            append_event(directory / "progress.jsonl", {"stage": "DECISION_FINISHED", **row})
            print(f"decision={row['decision_index']} status={row['decision_status']} "
                  f"minutes={row['simulation_minute_before']}->{row['simulation_minute_after']}", flush=True)
            return row

    with ContinuityWorld(directory / "world.sqlite3") as world:
        seed_demo(world)
        runner = None
        try:
            client = factory(config)
            runner = ObservedRunner(world, client, max_decisions=4, hard_timeout_seconds=60)
            runner.decision_runner.journal = directory / "request_progress.jsonl"
            summary, rows = await runner.run()
        except Exception as error:
            summary.update(termination_reason="ARCHITECTURE_ERROR", exception_type=exception_type(error))
        finally:
            summary["application_calls"] = counter(getattr(client, "call_count", 0)) or 0
            summary["provider_requests"] = counter(getattr(client, "provider_request_count", 0)) or 0
            # 状态/请求已另存 SQLite；先落停止摘要，再处理 close。
            write_json(directory / "execution_status.json", summary)
            cleanup = await close_client(client)
        summary.update(mode=mode, attempt_id="attempt_3", source_commit=environment["repository"]["git_commit"],
                       requested_model=atom(config["model"], config["api_key"]),
                       observed_backend_models=sorted({r["provider_model"] for r in rows if r.get("provider_model")}),
                       cleanup_exception_type=cleanup,
                       real_provider_executed=mode == "REAL_PROVIDER_PILOT" and summary["provider_requests"] > 0,
                       provider_count_semantics="CLIENT_POST_ATTEMPTS_NOT_CONFIRMED_SERVER_RECEIPT")
        summary["short_horizon_state_continuity"] = continuity_result(summary, rows, cleanup_error=cleanup)
        write_artifacts(directory, world, summary, rows, environment)
        write_json(directory / "execution_status.json", summary)
        report(directory / "report_zh.md", "Q6.1 Attempt 3 有界短链结果", summary)
    return summary


async def execute_session(directory: Path, config: dict, environment: dict, *, with_pilot: bool,
                          factory=real_client, mode: str = "REAL") -> dict:
    """directory 必须由 CLI 独占创建；先验收 close，再允许正式 4-call。"""
    write_json(directory / "environment.json", environment)
    summary = {"session_id": directory.name, "mode": mode, "preflight": "NOT_RUN",
               "attempt_3_executed": False, "total_provider_request_attempts": 0}
    write_json(directory / "session.json", summary)
    preflight = await run_preflight(directory / "preflight", config, factory=factory,
        mode="REAL_PROVIDER_PREFLIGHT" if mode == "REAL" else "OFFLINE_TRANSPORT_CONTRACT")
    summary.update(preflight=preflight["result"], total_provider_request_attempts=preflight["provider_requests"])
    write_json(directory / "session.json", summary)
    if preflight["result"] == "PASS" and with_pilot:
        summary["attempt_3_invoked"] = True
        write_json(directory / "session.json", summary)
        pilot = await run_pilot(directory / "attempt_3", config, environment, factory=factory,
            mode="REAL_PROVIDER_PILOT" if mode == "REAL" else "OFFLINE_TRANSPORT_CONTRACT")
        summary.update(attempt_3_executed=pilot["provider_requests"] > 0,
                       short_horizon_state_continuity=pilot["short_horizon_state_continuity"],
                       termination_reason=pilot["termination_reason"],
                       total_provider_request_attempts=preflight["provider_requests"] + pilot["provider_requests"])
    write_json(directory / "session.json", summary)
    report(directory / "report_zh.md", "运行时预检与短链实验会话", summary)
    return summary
