#!/usr/bin/env python3
"""执行 7/30 天工程验证并生成中文报告；默认零网络、零模型调用。"""
from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from social_sim.continuity.benchmark import run_days  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", nargs="+", type=int, default=[7, 30], choices=[1, 7, 30])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or ROOT / "run/evaluation/continuity" / datetime.now(timezone.utc).strftime("q6_%Y%m%dT%H%M%S%fZ")
    output.mkdir(parents=True, exist_ok=False)
    results = []
    for days in args.days:
        plain = run_days(output / f"day{days}_plain.sqlite3", days)
        recovered = run_days(output / f"day{days}_restart.sqlite3", days,
                             restart=True, duplicate_commands=True)
        same = plain["state_hash"] == recovered["state_hash"] and plain["events"] == recovered["events"]
        results.append({"days": days, "uninterrupted": plain, "restarted": recovered,
                        "recovery_equivalent": same})
        with (output / "progress.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(results[-1], ensure_ascii=False) + "\n")
        if not same:
            raise AssertionError("recovery state mismatch")
    payload = {"experiment": "Q6_CONTINUITY_CONTRACT", "mode": "SCRIPTED",
               "python": platform.python_version(), "platform": platform.platform(),
               "results": results, "provider_calls": 0, "behavioral_realism_proven": False}
    (output / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Q6 长期一致性实测报告", "", "本次为脚本驱动工程验证，不是真实模型自主生活实验。", ""]
    for result in results:
        r = result["restarted"]
        lines += [f"## {result['days']} 天", f"运行完成：{r['completed_days']} 天；状态约束：{r['invariants']}。",
                  f"重启：{r['restarts']} 次；重复命令：{r['duplicate_commands_checked']} 次。",
                  f"与不中断运行状态一致：{result['recovery_equivalent']}。",
                  f"上下文观察最大字符数：{r['max_observation_chars']}。", ""]
    lines += ["## 边界", "模型调用为 0；不能据此声称小模型已能自主正常生活 7/30 天。",
              "本报告仅证明已实现的状态、进度、活动生命周期与重复提交防护通过受测场景。"]
    (output / "报告.md").write_text("\n".join(lines), encoding="utf-8")
    print("CONTINUITY_CONTRACT_PASS")
    print(f"ARTIFACT_DIR={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
