#!/usr/bin/env python3
"""M2 零请求工程验证：仅 offline、fake 提案与排他创建的新 world。"""
from __future__ import annotations

import argparse
import asyncio
import json
import socket
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("offline",), default="offline")
    parser.add_argument("--session", help="新的安全短标识，不覆盖任何已有 session")
    parser.add_argument("--output-root", type=Path,
                        default=ROOT / "run/evaluation/m2_acquire")
    args = parser.parse_args(argv)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    session = (f"m2-offline-{stamp}-{uuid4().hex[:8]}"
               if args.session is None else args.session)

    def deny_network(*_args, **_kwargs):
        raise RuntimeError("M2_OFFLINE_NETWORK_FORBIDDEN")

    original_create = socket.create_connection
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    socket.create_connection = deny_network
    socket.socket.connect = deny_network
    socket.socket.connect_ex = deny_network
    try:
        from social_sim.continuity.m2_validation import run_m2_validation
        summary = asyncio.run(run_m2_validation(args.output_root, session))
    except (OSError, ValueError, RuntimeError) as error:
        print(json.dumps({"result": "FAIL", "exception_type": type(error).__name__,
                          "provider_requests": 0, "llm_calls": 0}))
        return 1
    finally:
        socket.create_connection = original_create
        socket.socket.connect = original_connect
        socket.socket.connect_ex = original_connect_ex
    print(f"M2_OFFLINE_RESULT={summary['result']}")
    print(f"M2_CASES_PASSED={summary['passed']}/{summary['total']}")
    print(f"FAKE_DECISION_CALLS={summary['fake_decision_calls']}")
    print("LLM_CALLS=0")
    print("PROVIDER_REQUESTS=0")
    print(f"ARTIFACT_DIR={args.output_root.resolve() / session}")
    return 0 if summary["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
