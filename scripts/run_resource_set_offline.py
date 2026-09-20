#!/usr/bin/env python3
"""Run the no-network Q4 pipeline capability probe."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from social_sim.resource_benchmark import build_offline_rows, build_scenarios, capability_summary


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output = root / "run/evaluation/resource_set_size" / f"offline_{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}"
    output.mkdir(parents=True, exist_ok=False)
    scenarios = build_scenarios()
    rows = build_offline_rows(scenarios, repetitions=2)
    summary = capability_summary(rows)
    (output / "rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RESOURCE_SET_OFFLINE_OK")
    print("SYSTEM_CAPABILITY_PROBE_NOT_MODEL_BEHAVIOR")
    print(f"SCENARIOS={len(scenarios)}")
    print(f"ROWS={len(rows)}")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    print(f"ARTIFACT_DIR={output}")


if __name__ == "__main__":
    main()
