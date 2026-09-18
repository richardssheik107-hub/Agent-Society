#!/usr/bin/env python3
"""Run the no-LLM systems-capability gate for Object Set Necessity."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from social_sim.object_benchmark import build_offline_probe_rows, build_synthetic_catalog, summarize_rows


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output = root / "run/evaluation/object_set_necessity" / f"offline_{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}"
    output.mkdir(parents=True, exist_ok=False)
    catalog = build_synthetic_catalog()
    rows = build_offline_probe_rows(catalog, repetitions=2)
    summary = summarize_rows(rows)
    (output / "rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("OBJECT_SET_NECESSITY_OFFLINE_OK")
    print(f"CATALOG_OBJECTS={len(catalog.objects)}")
    print(f"ROWS={len(rows)}")
    print("NOTE=SYSTEM_CAPABILITY_PROBE_NOT_MODEL_BEHAVIOR")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    print(f"ARTIFACT_DIR={output}")


if __name__ == "__main__":
    main()
