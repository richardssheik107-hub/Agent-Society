"""Q6.2 离线回放与投影审计；没有真实模型或网络执行入口。"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .action_projection import FEASIBLE, RAW, project_actions, projected_prompt
from .benchmark import seed_demo
from .context import parse_proposal
from .engine import ContinuityWorld
from .models import canonical_json, digest
from .q6_1 import observation_fingerprint, project_state
from .validation import validate_world

EXECUTION_BASE = "54ed48f93f452718e59bda1368e15737f173084c"
REPORT_BASE = "a338f0b3171bf1692032bfd6818f47620fba3fdb"
# 来自该提交中文报告的行为序列，不是本轮模型生成或原始 artifact。
REPORT_SEQUENCE = (
    {"activity": "TRAVEL", "target": "restaurant"},
    {"activity": "MEAL", "target": "food_meal"},
    {"activity": "MEAL", "target": "food_meal"},
    {"activity": "PLAY", "target": "game_a"},
)
ALLOWED_TARGETS = frozenset({None, "home", "restaurant", "office", "park", "food_bread",
                             "food_meal", "game_a", "series_a"})
COMPARE_KEYS = (
    "simulation_minute_before", "simulation_minute_after", "state_version_before",
    "state_version_after", "money_before", "money_after", "hunger_before", "hunger_after",
    "energy_before", "energy_after", "location_before", "location_after",
    "observation_digest_before", "observation_digest_after", "decision_status",
)
INT_KEYS = frozenset(COMPARE_KEYS[:10])
KNOWN_STATUSES = frozenset({"DECISION_ACCEPTED", "RULE_REJECTED", "COMMITMENT_FAILED"})


def _read_json(path: Path) -> object:
    if path.stat().st_size > 1_000_000:
        raise ValueError("SOURCE_FILE_TOO_LARGE")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise ValueError("INVALID_SOURCE_JSON") from error


def load_source(directory: Path) -> tuple[list[dict], list[dict], dict]:
    """只读明确给定的本地 Attempt 3 文件，白名单取字段，不复制 provider 原文。"""
    root = directory / "attempt_3" if (directory / "attempt_3").is_dir() else directory
    summary = _read_json(root / "summary.json")
    if (not isinstance(summary, dict) or summary.get("source_commit") != EXECUTION_BASE
            or summary.get("attempt_id") != "attempt_3"
            or summary.get("mode") != "REAL_PROVIDER_PILOT"):
        raise ValueError("SOURCE_PROVENANCE_MISMATCH")
    path = root / "decisions.jsonl"
    if path.stat().st_size > 1_000_000:
        raise ValueError("SOURCE_FILE_TOO_LARGE")
    proposals, expected = [], []
    lines = path.read_text(encoding="utf-8").splitlines()
    if not 1 <= len(lines) <= 4:
        raise ValueError("SOURCE_ROW_COUNT_MISMATCH")
    for index, line in enumerate(lines, 1):
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError
            if row.get("decision_index") != index or row.get("request_id") != f"q6_1:{index}":
                raise ValueError
            proposal = parse_proposal(canonical_json({"activity": row.get("proposal_activity"),
                                                     "target": row.get("proposal_target")}))
            if proposal["target"] not in ALLOWED_TARGETS:
                raise ValueError
            comparable = {key: row[key] for key in COMPARE_KEYS}
            for key, value in comparable.items():
                if key in INT_KEYS:
                    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                        raise ValueError
                elif key.startswith("observation_digest"):
                    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                        raise ValueError
                elif key.startswith("location"):
                    if value not in {"home", "restaurant", "office", "park"}:
                        raise ValueError
                elif value not in KNOWN_STATUSES:
                    raise ValueError
        except (ValueError, TypeError, KeyError) as error:
            raise ValueError("SOURCE_ROW_NOT_SUPPORTED") from error
        proposals.append(proposal)
        expected.append(comparable)
    final_state = _read_json(root / "final_state.json")
    files = ("summary.json", "decisions.jsonl", "final_state.json")
    hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files}
    return proposals, expected, {"source_commit": EXECUTION_BASE, "file_sha256": hashes,
                                 "final_state_digest": digest(final_state)}


def replay(output: Path, *, source_artifact: Path | None = None) -> dict:
    """脚本回放相同意图，不生成/补跑模型动作。A/B 是提示差异审计，不是效果实验。"""
    output = output.resolve()
    expected = None
    if source_artifact is not None:
        source_artifact = source_artifact.resolve()
        if output == source_artifact or output.is_relative_to(source_artifact):
            raise ValueError("OUTPUT_INSIDE_SOURCE_FORBIDDEN")
        proposals, expected, provenance = load_source(source_artifact)
        mode = "ARTIFACT_DRIVEN_DETERMINISTIC_REPLAY"
    else:
        proposals = list(REPORT_SEQUENCE)
        provenance = {"report_commit": REPORT_BASE, "source_commit": EXECUTION_BASE}
        mode = "SCRIPTED_REPORT_SEQUENCE_REPLAY"
    output.mkdir(parents=True, exist_ok=False)
    rows, mismatches = [], []
    with ContinuityWorld(output / "replay.sqlite3") as world:
        seed_demo(world)
        for index, proposal in enumerate(proposals, 1):
            request_id = f"q6_1:{index}"
            before = project_state(world)
            before_digest, _ = observation_fingerprint(world)
            projection = project_actions(world)
            a_system, a_user = projected_prompt(world, mode=RAW)
            b_system, b_user = projected_prompt(world, mode=FEASIBLE)
            preview = world.preview_activity(1, **proposal)
            result = world.start(request_id, 1, **proposal, expected_version=before["state_version"])
            status = "DECISION_ACCEPTED" if result["accepted"] else "RULE_REJECTED"
            if result["accepted"]:
                while (c := world.store.commitment(1)) and c["status"] == "ACTIVE":
                    until = world.minute + min(c["remaining_min"], 15)
                    tick = world.advance(f"{request_id}:t{until}", until)
                    if not tick["accepted"]:
                        raise RuntimeError("REPLAY_TICK_FAILED")
                if world.store.get_commitment(request_id)["status"] != "COMPLETED":
                    status = "COMMITMENT_FAILED"
            after = project_state(world)
            after_digest, _ = observation_fingerprint(world)
            row = {
                "decision_index": index, "request_id": request_id,
                "proposal_activity": proposal["activity"], "proposal_target": proposal["target"],
                "decision_status": status, "rule_reason": result["reason"],
                "simulation_minute_before": before["minute"],
                "simulation_minute_after": after["minute"],
                "state_version_before": before["state_version"],
                "state_version_after": after["state_version"],
                "observation_digest_before": before_digest, "observation_digest_after": after_digest,
                "state_before": before, "state_after": after,
                "projection": projection, "chosen_preview": preview,
                "choice_in_projected_options": proposal in projection["executable_options"],
                "a_prompt_chars": len(a_system + a_user), "b_prompt_chars": len(b_system + b_user),
                "a_prompt_digest": digest([a_system, a_user]),
                "b_prompt_digest": digest([b_system, b_user]),
                "provider_requests": 0,
            }
            for name, field in (("money", "money_cents"), ("hunger", "hunger_milli"),
                                ("energy", "energy_milli"), ("location", "location")):
                row[name + "_before"] = before[field]
                row[name + "_after"] = after[field]
            row["immediate_meal_repeat"] = (index > 1 and proposal["activity"] == "MEAL"
                                            and rows[-1]["proposal_activity"] == "MEAL")
            if expected is not None:
                differences = [key for key in COMPARE_KEYS if row[key] != expected[index - 1][key]]
                if differences:
                    mismatches.append({"decision_index": index, "fields": differences})
            rows.append(row)
            with (output / "replay_rows.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(canonical_json(row) + "\n")
            validate_world(world)
            print(f"replay={index} status={status} projected={row['choice_in_projected_options']}",
                  flush=True)
            if status != "DECISION_ACCEPTED":
                break
        if len(rows) != len(proposals):
            mismatches.append({"fields": ["REPLAY_STOPPED_BEFORE_SOURCE_END"]})
        final = world.store.snapshot()
        if expected is not None and digest(final) != provenance["final_state_digest"]:
            mismatches.append({"fields": ["FINAL_STATE_MISMATCH"]})
        final_validation = validate_world(world)
        source_verified = expected is not None and not mismatches
        summary = {
            "experiment": "Q6_2_EXECUTABLE_ACTION_PROJECTION_OFFLINE", "mode": mode,
            "source_artifact_verified": source_verified, "provenance": provenance,
            "comparison_mismatches": mismatches,
            "replayed_decisions": len(rows),
            "choices_excluded_by_projection": sum(not row["choice_in_projected_options"] for row in rows),
            "repeat_meal_is_hard_banned": False,
            "game_acquisition_path_in_high_level_action_set": False,
            "provider_requests": 0, "llm_calls": 0, "live_ab_executed": False,
            "state_utilization_causal_effect": "NOT_TESTED",
            "short_horizon_state_continuity": "NOT_RETESTED",
            "final_validation": final_validation,
            "result": "PASS" if not mismatches else "SOURCE_REPLAY_MISMATCH",
        }
        (output / "final_state.json").write_text(canonical_json(final) + "\n", encoding="utf-8")
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "report_zh.md").write_text(render_report(summary, rows), encoding="utf-8")
    return summary


def render_report(summary: dict, rows: list[dict]) -> str:
    lines = ["# Q6.2 可执行活动投影：离线审计", "",
             f"模式：`{summary['mode']}`。原始本地 artifact 已核对：`{summary['source_artifact_verified']}`。",
             "本轮模型调用为 0；回放意图来自既有报告或明确传入的历史文件，不是新的模型样本。",
             "A/B 只比较同一状态的提示与候选；不报告虚构的模型效果提升。", "",
             "| 步骤 | 固定意图 | 饥饿值前→后 | 金额前→后（分） | 投影保留 | 旧执行结果 |",
             "|---|---|---|---|---|---|"]
    for row in rows:
        lines.append(f"| {row['decision_index']} | {row['proposal_activity']} / {row['proposal_target']} | "
                     f"{row['hunger_before']}→{row['hunger_after']} | "
                     f"{row['money_before']}→{row['money_after']} | "
                     f"{row['choice_in_projected_options']} | {row['decision_status']} |")
    lines += ["", "## 解释边界",
              "可执行性不等于行为合理性：刚吃过饭不自动禁止再吃。",
              "在冻结参数的报告序列回放中，第一次餐食后饥饿为 245/1000，尚未归零；不能仅凭连吃两次认定模型遗忘。",
              "PLAY 依然要求拥有游戏；投影不会送游戏、代购或添加 BUY 动作。原高层动作集缺少游戏获取路径，仍需独立研究。",
              "不读取未来事件或场景答案，不预执行并回滚动作；只读检查与真实执行共享规则。",
              "候选仅在当前快照下成立；后续执行必须重新检查库存、权限和状态版本。",
              "没有验证真实 A/B、人类相似性、多日自主行为或千万对象检索性能。", "",
              f"最终状态约束：`{summary['final_validation']['invariants']}`；结果：`{summary['result']}`。"]
    return "\n".join(lines) + "\n"
