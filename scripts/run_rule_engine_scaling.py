#!/usr/bin/env python3
"""Run Research Q5 rule-graph scaling through 10M catalog ids."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import resource

from social_sim.rule_scaling.benchmark import (
    ScaleBenchmarkConfig,
    run_scale_benchmark,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", type=int, default=1000)
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--explicit-max", type=int, default=100000)
    args = parser.parse_args()

    result = run_scale_benchmark(
        ScaleBenchmarkConfig(
            top_k=args.top_k,
            queries_per_size=args.queries,
            explicit_materialize_max_objects=args.explicit_max,
        )
    )
    result["process_peak_rss_kib"] = int(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    )

    root = Path(__file__).resolve().parents[1]
    output = (
        root
        / "run/evaluation/rule_engine_scaling"
        / f"q5_{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}"
    )
    output.mkdir(parents=True, exist_ok=False)
    (output / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print("RULE_ENGINE_SCALING_OK")
    print("NOTE=RULE_GRAPH_SCALING_NOT_OBJECT_PAYLOAD_STORAGE")
    for row in result["rows"]:
        print(
            "SIZE={object_count} RELATIONS={explicit_relation_estimate} "
            "PACKED_LOWER_BOUND_BYTES={explicit_packed_lower_bound_bytes} "
            "P95_US={p95_query_us} SCAN={object_scan_count} "
            "TARGET_EDGES={target_per_object_rule_edges}".format(**row)
        )
    print(f"SCALING_RESULT={result['decision']['status']}")
    print(f"ARTIFACT_DIR={output}")


if __name__ == "__main__":
    main()
