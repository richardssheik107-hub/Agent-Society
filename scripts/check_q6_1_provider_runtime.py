#!/usr/bin/env python3
"""默认零请求；显式授权后一次预检，可另授权通过后最多四次 pilot。"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from social_sim.provider_runtime.environment import (  # noqa: E402
    code_fingerprint, inspect_runtime, load_provider_config, repository_info,
)
from social_sim.provider_runtime.safety import exception_type, write_json  # noqa: E402


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check-only", action="store_true", help="环境导入与关闭路径检查，零网络")
    p.add_argument("--allow-provider", action="store_true", help="授权一次 provider 预检")
    p.add_argument("--with-pilot", action="store_true", help="额外授权预检通过后一次 4-call Attempt 3")
    p.add_argument("--session-id", help="唯一人工命名的会话 ID；已有 ID 一律不重跑")
    p.add_argument("--env-file", type=Path, help="只读本地受保护 .env，不执行 shell 内容")
    args = p.parse_args(argv)
    if args.check_only and (args.allow_provider or args.with_pilot):
        p.error("--check-only 不可与真实运行授权混用")
    if not args.check_only and not args.allow_provider:
        print("Q6_1_REAL_PROVIDER_NOT_AUTHORIZED\nPROVIDER_REQUESTS=0")
        return 0
    runtime = inspect_runtime()
    if args.check_only:
        print(json.dumps(runtime, ensure_ascii=False, indent=2))
        return 0 if runtime["result"] == "PASS" else 1
    if not args.session_id or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,47}", args.session_id):
        p.error("真实运行要求 --session-id，限 1..48 位小写字母、数字、下划线或横线")
    info = repository_info(ROOT)
    output_root = ROOT / "run/evaluation/q6_1_provider_runtime"
    output_root.mkdir(parents=True, exist_ok=True)
    # 不同 ID 也不能并发跑；同 ID 的目录在失败/中断后不删除、不自动恢复。
    import fcntl
    with (output_root / ".runtime.lock").open("a", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("RUNTIME_ALREADY_RUNNING\nPROVIDER_REQUESTS=0")
            return 1
        directory = output_root / args.session_id
        try:
            directory.mkdir(mode=0o700, exist_ok=False)
        except FileExistsError:
            print("SESSION_ALREADY_EXISTS_DO_NOT_RERUN\nNEW_PROVIDER_REQUESTS=0")
            return 1
        os.chmod(directory, 0o700)
        environment = {"repository": info, "runtime": runtime, "contains_secret": False}
        if runtime["result"] != "PASS" or not all(info[k] for k in
                                                   ("parent_repository", "worktree_clean", "upstream_matches")):
            write_json(directory / "environment.json", environment)
            write_json(directory / "session.json", {"preflight": "FAIL", "failure_stage":
                "PYTHON_ENVIRONMENT" if runtime["result"] != "PASS" else "REPOSITORY",
                "attempt_3_executed": False, "provider_requests": 0})
            print("RUNTIME_OR_REPOSITORY_GATE_FAILED\nPROVIDER_REQUESTS=0")
            return 1
        try:
            config = load_provider_config(args.env_file)
            environment["code_fingerprint"] = code_fingerprint(ROOT)
            environment["configured_model"] = config["model"]
            write_json(directory / "environment.json", environment)
        except Exception as error:
            write_json(directory / "session.json", {"preflight": "FAIL", "failure_stage": "CONFIGURATION",
                "exception_type": exception_type(error), "provider_requests": 0, "attempt_3_executed": False})
            print("PROVIDER_CONFIG_FAILED\nPROVIDER_REQUESTS=0")
            return 1
        # 不回显配置值或开启 httpx DEBUG 日志。
        for name in ("httpx", "httpcore", "anyio"):
            logging.getLogger(name).setLevel(logging.CRITICAL)
        try:
            from social_sim.provider_runtime.workflow import execute_session
            summary = asyncio.run(execute_session(directory, config, environment, with_pilot=args.with_pilot))
        except Exception as error:
            # 不覆盖已保存的首次异常和部分结果。客户端计数未知时保留 UNKNOWN。
            write_json(directory / "orchestration_failure.json", {"exception_type": exception_type(error),
                "provider_requests": None, "request_receipt": "UNKNOWN", "automatic_retry": False})
            print("ORCHESTRATION_ERROR_REVIEW_EXISTING_ARTIFACTS")
            return 1
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"ARTIFACT_DIR={directory}")
        passed = summary["preflight"] == "PASS"
        if args.with_pilot:
            passed = passed and summary.get("short_horizon_state_continuity") == "SUPPORTED"
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
