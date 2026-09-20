#!/usr/bin/env python3
"""执行 7/30 天工程验证并生成中文报告；默认零网络、零模型调用。"""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def source_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                       stderr=subprocess.DEVNULL, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main() -> int:
    from social_sim.continuity.benchmark import run_days
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", nargs="+", type=int, default=[7, 30], choices=[1, 7, 30])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if len(set(args.days)) != len(args.days):
        parser.error("同一次运行不要重复指定同一天数")
    output = args.output or ROOT / "run/evaluation/continuity" / datetime.now(UTC).strftime("q6_%Y%m%dT%H%M%S%fZ")
    output.mkdir(parents=True, exist_ok=False)
    results = []
    for days in args.days:
        plain = run_days(output / f"day{days}_plain.sqlite3", days)
        recovered = run_days(output / f"day{days}_restart.sqlite3", days,
                             restart=True, duplicate_commands=True)
        same = plain["state_hash"] == recovered["state_hash"] and plain["events"] == recovered["events"]
        result = {"days": days, "uninterrupted": plain, "restarted": recovered,
                  "recovery_equivalent": same}
        results.append(result)
        with (output / "progress.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(result, ensure_ascii=False) + "\n")
            stream.flush()
        print("CONTINUITY_RESULT=" + json.dumps({
            "days": days, "completed_days": recovered["completed_days"],
            "invariants": recovered["invariants"], "recovery_equivalent": same,
            "restarts": recovered["restarts"],
            "duplicate_commands_checked": recovered["duplicate_commands_checked"],
            "max_observation_chars": recovered["max_observation_chars"],
            "state_hash": recovered["state_hash"], "events": recovered["events"],
            "provider_calls": 0, "model_behavior_proven": False,
        }, ensure_ascii=False), flush=True)
        if not same:
            raise AssertionError("recovery state mismatch")
    payload = {"experiment": "Q6_CONTINUITY_CONTRACT", "mode": "SCRIPTED",
               "source_commit": source_commit(),
               "python": platform.python_version(), "platform": platform.platform(),
               "results": results, "provider_calls": 0, "behavioral_realism_proven": False}
    (output / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Q6 长期一致性实测报告", "", "本次为脚本驱动工程验证，不是真实模型自主生活实验。",
             f"代码提交：`{payload['source_commit']}`。", ""]
    for result in results:
        row = result["restarted"]
        lines += [f"## {result['days']} 天", f"运行完成：{row['completed_days']} 天；状态约束：{row['invariants']}。",
                  f"重启：{row['restarts']} 次；重复命令：{row['duplicate_commands_checked']} 次。",
                  f"与不中断运行状态一致：{result['recovery_equivalent']}。",
                  f"上下文观察最大字符数：{row['max_observation_chars']}。", ""]
    lines += ["## 边界", "模型调用为 0；不能据此声称小模型已能自主正常生活 7/30 天。",
              "本报告仅证明已实现的状态、进度、活动生命周期与重复提交防护通过受测场景。"]
    (output / "报告.md").write_text("\n".join(lines), encoding="utf-8")
    print("CONTINUITY_CONTRACT_PASS")
    print(f"ARTIFACT_DIR={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
