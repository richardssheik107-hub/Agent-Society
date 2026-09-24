#!/usr/bin/env python3
"""Q6.2 只读来源/新世界离线回放。没有 --allow-provider，不接收或读取凭据。"""
from __future__ import annotations

import argparse
import json
import socket
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-artifact", type=Path,
                        help="可选：原始 q61-runtime-01 或其 attempt_3 目录；只读验证")
    parser.add_argument("--output", type=Path, help="必须是新的输出目录，不覆盖历史")
    args = parser.parse_args(argv)

    def deny_network(*_args, **_kwargs):
        raise RuntimeError("Q62_OFFLINE_NETWORK_FORBIDDEN")

    socket.create_connection = deny_network
    socket.socket.connect = deny_network
    from social_sim.continuity.q6_2 import replay
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    output = args.output or ROOT / "run/evaluation/q6_2_projection" / stamp
    try:
        summary = replay(output, source_artifact=args.source_artifact)
    except (OSError, ValueError, RuntimeError) as error:
        # 不回显未知源文件内容或完整异常。
        print(json.dumps({"result": "FAIL", "exception_type": type(error).__name__,
                          "provider_requests": 0}))
        return 1
    print(f"Q62_OFFLINE_RESULT={summary['result']}")
    print("PROVIDER_REQUESTS=0")
    print(f"SOURCE_ARTIFACT_VERIFIED={summary['source_artifact_verified']}")
    print(f"ARTIFACT_DIR={output}")
    return 0 if summary["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
