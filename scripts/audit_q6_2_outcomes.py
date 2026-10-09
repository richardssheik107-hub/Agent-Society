#!/usr/bin/env python3
"""只读、零模型的 M1.5 真实来源审计；不提供执行/重试入口。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from social_sim.continuity.q6_2_outcome_audit import (  # noqa: E402
    build_human_review_packet, build_outcome_audit, render_report, safe_delivery_summary,
)
from social_sim.continuity.q6_2_outcome_prompt import audit_prompt_intervention  # noqa: E402
from social_sim.continuity.q6_2_outcome_source import (  # noqa: E402
    SourceEvidenceError, load_verified_session, verify_source_unchanged,
)


def _json(path: Path, value):
    # Output is new and contains only validated/whitelisted audit values.
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def audit_to_directory(source_session, output, *, recovery=None, analysis=None):
    source, destination = Path(source_session).resolve(), Path(output).resolve()
    if destination.exists():
        raise ValueError("OUTCOME_OUTPUT_ALREADY_EXISTS")
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("OUTCOME_SOURCE_OUTPUT_OVERLAP")
    verified = load_verified_session(source, recovery=recovery, analysis=analysis)
    rows = verified["sanitized_cells"]
    prompt = audit_prompt_intervention(verified["protocol"], verified["frozen_scenarios"],
                                       verified["allocated_cells"], rows)
    resources = {item["scenario_id"]: item["initial_resource_facts"] for item in prompt["scenarios"]}
    rows = [{**row, "initial_resources": resources[row["scenario_id"]]} for row in rows]
    audit = build_outcome_audit(rows, prompt)
    if (len(audit["cells"]) != 48 or audit["paired_effects"]["planned_pairs"] != 24
            or audit["paired_effects"]["complete_pairs"] != 22):
        raise ValueError("OUTCOME_SOURCE_DIMENSIONS_MISMATCH")
    integrity = verify_source_unchanged(source, verified["source_integrity"]["before"])
    integrity.update({key: value for key, value in verified["source_integrity"].items()
                      if key not in {"before", "after"}})
    audit["markers"].update(SOURCE_SESSION_VERIFIED="PASS", SOURCE_FILES_UNCHANGED="PASS",
                            PLANNED_CELLS=48, PLANNED_PAIRS=24, FULLY_SCORED_PAIRS=22,
                            OBJECTIVE_DELTA_AUDIT="PASS", ACTION_GRANULARITY_AUDIT="PASS",
                            PROMPT_INTERVENTION_AUDIT="PASS")
    packet, private_key = build_human_review_packet(rows)
    report = render_report(audit, prompt, integrity)
    destination.mkdir(parents=True, exist_ok=False)
    _json(destination / "source_integrity.json", integrity)
    with (destination / "state_deltas.jsonl").open("x", encoding="utf-8") as stream:
        for cell in audit["cells"]:
            stream.write(json.dumps(cell, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
    _json(destination / "paired_effects.json", audit["paired_effects"])
    _json(destination / "prompt_intervention_audit.json", prompt)
    _json(destination / "summary.json", {key: value for key, value in audit.items()
                                          if key not in {"cells", "paired_effects"}})
    _json(destination / "provenance.json", verified["provenance"])
    _json(destination / "safe_delivery.json",
          safe_delivery_summary(audit, prompt, integrity, verified["provenance"]))
    _json(destination / "human_review_key.json", private_key)
    with (destination / "human_review_packet_zh.md").open("x", encoding="utf-8") as stream:
        stream.write(packet)
    with (destination / "report_zh.md").open("x", encoding="utf-8") as stream:
        stream.write(report)
    # This verification includes export time. On failure, retain new evidence and
    # flag FAIL; never remove output or try to repair the source/session.
    try:
        verify_source_unchanged(source, integrity["before"])
    except SourceEvidenceError:
        _json(destination / "INTEGRITY_FAILED.json", {"SOURCE_FILES_UNCHANGED": "FAIL",
                                                       "NEW_REAL_PROVIDER_REQUESTS": 0})
        raise
    return audit


def main(argv=None):
    parser = argparse.ArgumentParser(description="Q6.2真实行为后果只读离线审计（零模型）")
    parser.add_argument("--source-session", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-integrity", action="store_true",
                        help="显式请求SHA256核验；为安全起见默认也始终核验")
    parser.add_argument("--recovery", type=Path, help="既有只读恢复目录，不创建或更新")
    parser.add_argument("--analysis", type=Path, help="既有确定性分析目录，不创建或更新")
    args = parser.parse_args(argv)
    try:
        audit = audit_to_directory(args.source_session, args.output,
                                   recovery=args.recovery, analysis=args.analysis)
    except SourceEvidenceError as error:
        print("AUDIT_STATUS=FAIL", file=sys.stderr)
        print(str(error), file=sys.stderr)
        print("NEW_REAL_PROVIDER_REQUESTS=0", file=sys.stderr)
        return 2
    except (ValueError, OSError, TypeError, KeyError, RuntimeError):
        # Never print supplied paths, exception bodies, input content or secrets.
        print("AUDIT_STATUS=FAIL:OFFLINE_AUDIT_CONTRACT_OR_OUTPUT_ERROR", file=sys.stderr)
        print("NEW_REAL_PROVIDER_REQUESTS=0", file=sys.stderr)
        return 2
    print("AUDIT_STATUS=PASS")
    for key, value in audit["markers"].items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
