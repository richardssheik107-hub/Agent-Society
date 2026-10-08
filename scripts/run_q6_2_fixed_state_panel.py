#!/usr/bin/env python3
"""固定状态配对面板：默认零请求，offline 为脚本模拟，real 需独立授权。"""
# ruff: noqa: E402 -- standalone source path
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from social_sim.continuity.models import digest
from social_sim.continuity.q6_2_panel import (
    ScriptedPanelClient, export_only, prepare_session, run_session,
)
from social_sim.continuity.q6_2_panel_fixtures import load_protocol
from social_sim.provider_runtime.environment import inspect_runtime, repository_info
from social_sim.provider_runtime.safety import exception_type

REGISTRY = ROOT / "run/evaluation/q6_2_fixed_state_panel"


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    modes = p.add_mutually_exclusive_group()
    modes.add_argument("--mode", choices=("dry-run", "offline", "real"), default="dry-run")
    modes.add_argument("--export-only", type=Path, metavar="SOURCE_SESSION",
                       help="只读恢复；不读凭据、不创建 client、不补跑")
    p.add_argument("--session-id", help="排他创建的本机唯一 ID；不可重用")
    p.add_argument("--output", type=Path, help="仅 export-only 的新恢复目录；不能改运行注册根")
    p.add_argument("--allow-provider", action="store_true", help="未来 real 的独立授权，本轮禁止")
    p.add_argument("--execution-commit", help="real 必须与干净工作树 HEAD 完全一致")
    p.add_argument("--protocol-hash", help="real 必须与冻结配置规范 JSON SHA256 完全一致")
    p.add_argument("--max-requests", type=int, default=48, help="固定容量48，不能扩大")
    p.add_argument("--env-file", type=Path, help="仅获授权 real 可显式只读解析；不 source")
    p.add_argument("--offline-case", default="a-illegal-b-legal",
                   choices=("a-illegal-b-legal", "both-legal", "b-worse", "no-valid-proposal"),
                   help="仅脚本案例，不是模型行为或研究答案")
    return p


async def _execute(args, protocol):
    with prepare_session(REGISTRY, args.session_id, mode=args.mode, protocol=protocol, root=ROOT) as ledger:
        if args.mode != "real":
            client = ScriptedPanelClient(args.offline_case) if args.mode == "offline" else None
            result = await run_session(ledger, mode=args.mode, client=client)
        else:
            # Credentials are reached only after explicit opt-in, environment and all-cell gates.
            from social_sim.provider_runtime.environment import load_provider_config
            from social_sim.decision import OpenAICompatibleDecisionClient
            env_file = args.env_file
            if env_file is not None and not env_file.is_absolute():
                env_file = ROOT / env_file
            config = load_provider_config(env_file)
            for name in ("httpx", "httpcore", "anyio"):
                logging.getLogger(name).setLevel(logging.CRITICAL)
            client = OpenAICompatibleDecisionClient(**config, minimal_request=True,
                                                     timeout_seconds=protocol["timeout_seconds"])
            try:
                result = await run_session(ledger, mode="real", client=client)
            finally:
                await asyncio.wait_for(client.aclose(), timeout=5)
        print(f"ARTIFACT_DIR={ledger.dir}")
        return result


def main(argv=None) -> int:
    p = parser()
    args = p.parse_args(argv)
    if args.export_only is not None:
        if (args.output is None or args.session_id or args.allow_provider or args.env_file
                or args.execution_commit or args.protocol_hash):
            p.error("export-only 仅接受 source 与新的 output，不接受真实配置/授权/session")
        result = export_only(args.export_only, args.output)
        print("READ_ONLY_RECOVERY=PASS\nNEW_PROVIDER_REQUESTS=0")
        print(f"ARTIFACT_DIR={args.output.resolve()}")
    else:
        if not args.session_id or args.output is not None:
            p.error("运行需要唯一 session-id；output 只用于只读恢复")
        if args.max_requests != 48:
            p.error("固定计划为48个单元，预算不可更改")
        if args.mode != "real" and (args.allow_provider or args.env_file or args.execution_commit or args.protocol_hash):
            p.error("默认/offline 不接受凭据或真实授权")
        if args.mode == "real" and not args.allow_provider:
            print("REAL_PROVIDER_NOT_AUTHORIZED\nREAL_PROVIDER_REQUESTS_THIS_TASK=0")
            return 1
        protocol = load_protocol()
        if args.mode == "real":
            info = repository_info(ROOT)
            runtime = inspect_runtime()
            if (not args.execution_commit or info["git_commit"] != args.execution_commit
                    or args.protocol_hash != digest(protocol)
                    or not all(info[k] for k in ("parent_repository", "worktree_clean", "upstream_matches"))
                    or runtime["result"] != "PASS"):
                print("REAL_VERSION_OR_ENVIRONMENT_GATE_FAILED\nREAL_PROVIDER_REQUESTS_THIS_TASK=0")
                return 1
        result = asyncio.run(_execute(args, protocol))
    print(json.dumps({k: result[k] for k in ("schema_version", "mode", "session_status", "counts", "real_provider_requests")}, ensure_ascii=False, indent=2))
    print("MODEL_BENEFIT=NOT_TESTED")
    if args.mode != "real":
        print("REAL_PROVIDER_REQUESTS_THIS_TASK=0")
    return 0 if result.get("session_status") in {"PANEL_COMPLETED", "NOT_RUN", "STOPPED_READ_ONLY_RECOVERY"} else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"PANEL_STOPPED_EXCEPTION_TYPE={exception_type(error)}; REVIEW_EXISTING_SESSION", file=sys.stderr)
        raise SystemExit(1) from None
