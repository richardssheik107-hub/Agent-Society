"""Safe M5 exports from committed facts; no raw completions or credentials."""
from __future__ import annotations

import json
from pathlib import Path

from social_sim.continuity.models import canonical_json

from .config import LongRunConfig, WarningThresholds
from .evaluation import (InvariantViolation, activities_from_facts, check_invariants_full,
                         daily_metrics, evaluate)
from .policy import FIXTURE_SOURCE, POLICY_SOURCE

REQUEST_FIELDS = (
    "request_id", "ordinal", "actor_id", "minute", "phase", "status", "request_send_status",
    "expected_version", "proposal", "result", "context", "input_tokens", "output_tokens",
    "reasoning_tokens", "provider_model", "request_alias", "actual_response_backend", "http_status",
    "http_response_observed", "service_contract_valid", "strict_json_valid", "catalog_valid",
    "application_calls", "provider_requests", "provider_requests_reserved", "micro_steps",
    "latency_seconds", "exception_type", "failure_category", "finish_reason", "interruption_reason",
    "recovered_world_result", "before_state", "after_state", "invariants",
)


def _cost(rows, field):
    values = [r.get(field) for r in rows]
    known = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0]
    return {"known_subtotal": sum(known) if known else None, "known_rows": len(known),
            "missing_rows": len(rows) - len(known), "eligible_rows": len(rows),
            "missing_rate": (len(rows) - len(known)) / len(rows) if rows else None}


def build_summary(data: dict, *, database_bytes: int | None = None) -> dict:
    config = data.get("manifest", {}).get("config", {})
    thresholds = WarningThresholds(**config.get("warnings", {}))
    evaluation = evaluate(data, thresholds)
    session, world = data.get("session", {}), data["world"]
    requests = data.get("requests", [])
    activities = activities_from_facts(data)
    initial_minute = session.get("initial_minute", 0)
    minutes = world["minute"] - initial_minute
    contexts = [r.get("context", {}) for r in requests]
    mode = config.get("mode", "offline")
    return {
        "schema": "M5_LONGRUN_SAFE_SUMMARY_V1", "session_id": session.get("session_id"),
        "state": session.get("state"), "stop_reason": session.get("stop_reason"),
        "result_class": "REAL_MODEL_AUTONOMOUS_LONG_RUN" if mode == "real" else "SCRIPTED_OR_FAKE_LONG_RUN",
        "simulation_minutes": minutes, "simulation_days": minutes / 1440,
        "minute": world["minute"], "horizon_minute": session.get("horizon_minute"),
        "horizon_reached": world["minute"] >= session.get("horizon_minute", world["minute"] + 1),
        "decisions": session.get("decisions", len(requests)),
        "activities_completed": sum(c["status"] == "COMPLETED" for c in activities),
        "activities_started": len(activities), "micro_steps": session.get("micro_steps"),
        "rule_rejections": evaluation["L2"]["rule_rejections"],
        "events": len(data.get("events", [])), "world_database_bytes": database_bytes,
        "wall_seconds": session.get("wall_seconds"), "resume_count": session.get("resume_count", 0),
        "memory_observation": {"peak_rss_bytes": None, "status": "NOT_MEASURED_BY_REPORT_EXPORT"},
        "max_context_chars": max((c.get("prompt_chars", 0) for c in contexts), default=0),
        "max_context_token_upper_bound": max((c.get("token_upper_bound", 0) for c in contexts), default=0),
        "context_token_accounting": "UTF8_CONTENT_BYTE_UPPER_BOUND_NOT_ACTUAL_PROVIDER_TOKENS",
        "costs": {f: _cost(requests, f) for f in
                  ("input_tokens", "output_tokens", "reasoning_tokens", "latency_seconds", "provider_requests")},
        "provider_requests_reserved": session.get("provider_requests_reserved", 0),
        "actual_provider_requests": 0 if mode == "offline" else _cost(requests, "provider_requests"),
        "active_commitment": next((c for c in world["commitments"] if c["status"] in {"ACTIVE", "PAUSED"}), None),
        "cross_day_activities": [{"activity": c["activity"], "started_minute": c["started_minute"],
                                  "end_minute": c["end_minute"], "status": c["status"]}
                                 for c in activities if c["elapsed_min"] > 0 and
                                 c["started_minute"] // 1440 !=
                                 (c["end_minute"] if c["end_minute"] is not None else world["minute"]) // 1440],
        "synthetic_provenance": {"fixture": FIXTURE_SOURCE, "policy": POLICY_SOURCE,
                                 "initial_cash_and_stock_source": "EXISTING_Q6_SYNTHETIC_DEMO_GENESIS",
                                 "fixed_daily_schedule": False, "human_preferences_claimed": False}
                                if mode == "offline" else None,
        "initial_state": session.get("initial_state"), "final_state": world,
        "evaluation": evaluation, "daily": daily_metrics(data, thresholds),
        "HUMAN_LIKENESS_PROVEN": False, "REAL_MODEL_SEVEN_DAY_VALIDATED": False,
    }


def render_report(summary: dict) -> str:
    evaluation, l2 = summary["evaluation"], summary["evaluation"]["L2"]
    lines = ["# M5 长周期运行与行为评价", "",
             f"实验类别：{summary['result_class']}。终止：{summary['stop_reason']}。",
             f"实际推进 {summary['simulation_minutes']} 模拟分钟（{summary['simulation_days']:.6f} 天）；"
             f"高层决策 {summary['decisions']} 次，完成活动 {summary['activities_completed']} 次，"
             f"规则拒绝 {summary['rule_rejections']} 次。", "",
             "模拟时钟只由合法世界活动推进；API 延迟和墙钟秒独立记录。",
             "离线驱动器按需求、钱、地点、所有权和媒体进度选择合法活动，含明确的合成工程覆盖目标；"
             "它不能证明真实大模型的长周期自主行为或真人偏好。", "",
             f"L1 工程一致性：{evaluation['L1']['status']}；任务连续性：{evaluation['TASK_CONTINUITY']}。",
             "L2 为分开的描述指标，不合成生活总分。L3：UNRESOLVED／未审核；真人相似性未证明。",
             "饥饿和精力为 0..1000 合成 milli 状态，预警阈值仅作工程观测，不是医学或行为规范；预警不干预决策。", "",
             f"饥饿 {l2['hunger']['initial']}→{l2['hunger']['final']}，精力 {l2['energy']['initial']}→{l2['energy']['final']}。",
             f"资金 {l2['money']['initial_cents']}→{l2['money']['final_cents']} cents；"
             f"工作收入 {l2['money']['work_income_cents']}，购买支出 {l2['money']['purchase_spending_cents']}。",
             f"工作 {l2['work_minutes']} 分钟，进食 {l2['meal_events']} 次；"
             f"获取后使用：{l2['goal_progress']['acquire_to_play']}。", "",
             f"最大上下文 {summary['max_context_chars']} 字符；保守 token 上界 {summary['max_context_token_upper_bound']}。"
             "此上界基于 UTF-8 内容字节，另加声明的消息封装预留，不是实际 provider token 数。",
             f"墙钟 {summary['wall_seconds']} 秒；数据库 {summary['world_database_bytes']} 字节；"
             f"恢复 {summary['resume_count']} 次；预留 provider 请求 {summary['provider_requests_reserved']}。",
             "token 缺失保存 null 并报告缺失率；不推算费用、不将 input/output/reasoning 相加。", "",
             "## 逐日提交事实", "",
             "跨午夜活动按 [开始,结束) 的实际重叠分钟分配；购买和进食记于真实事件分钟。"
             "起止状态仅来自该分钟实际快照，缺失保留 null；最后活动仍在进行时保留真实承诺。", "",
             "|模拟日|分钟|活动阶段分钟|工作收入 cents|购买支出 cents|进食次数|饥饿起→止|精力起→止|资金起→止|",
             "|---|---:|---|---:|---:|---:|---|---|---|"]
    for day in summary["daily"]:
        def actor(state):
            return next((a for a in (state or {}).get("actors", []) if a["actor_id"] == 1), {})
        a, b = actor(day["initial_state"]), actor(day["final_state"])
        transitions = [f"{a.get(k, 'UNKNOWN')}→{b.get(k, 'UNKNOWN')}" for k in
                       ("hunger_milli", "energy_milli", "money_cents")]
        lines.append(f"|{day['day']}|{day['simulation_minutes']}|{canonical_json(day['activity_phase_minutes'])}"
                     f"|{day['work_income_cents']}|{day['purchase_spending_cents']}|{day['meal_events']}|"
                     + "|".join(transitions) + "|")
    lines.extend(["", "## 实际覆盖与观测预警", "",
                  canonical_json(l2["goal_progress"]["observed_coverage"]), "",
                  f"跨日活动 {len(summary['cross_day_activities'])}；"
                  f"预警 {len(evaluation['warnings'])} 条，全部 intervention=NONE。",
                  "预警详情见 summary.json；完整请求、活动、精确状态检查点分别见相邻 JSONL。", "",
                  "未审核的行为合理性不能填 PASS。真实接口能力需由 mock 合同验收；"
                  "本报告不把离线七天或三十天称为真实模型长期行为验证。", ""])
    return "\n".join(lines)


def export_reports(session_or_data, output_dir=None) -> dict:
    """Export sanitized report files; a dict path never opens a writable world."""
    if isinstance(session_or_data, dict):
        data = session_or_data
        if output_dir is None:
            raise ValueError("EXPORT_DATA_REQUIRES_EXPLICIT_OUTPUT_DIRECTORY")
    else:
        data = session_or_data.export_data()
        try:
            data["session"]["invariants"] = check_invariants_full(session_or_data.world)
        except InvariantViolation:
            data["session"]["invariants"] = {"invariants": "FAIL", "L1": "FAIL",
                                             "failure_category": "WORLD_FACT_INVARIANT_FAILED"}
        output_dir = session_or_data.dir if output_dir is None else output_dir
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    database = destination / "world.sqlite3"
    try:
        summary = build_summary(data, database_bytes=database.stat().st_size if database.is_file() else None)
    except (InvariantViolation, KeyError, ValueError, TypeError, StopIteration):
        summary = {"schema": "M5_LONGRUN_SAFE_SUMMARY_V1", "session_id": data.get("session", {}).get("session_id"),
                   "state": data.get("session", {}).get("state"),
                   "stop_reason": data.get("session", {}).get("stop_reason"),
                   "evaluation": {"L1": {"status": "FAIL", "failure_category": "REPORT_SOURCE_FACTS_INVALID"},
                                  "L2": {"evidence_status": "UNAVAILABLE_CORRUPT_SOURCE", "aggregate_score": None},
                                  "L3": {"status": "UNRESOLVED", "human_review": "未审核"}},
                   "final_state": data.get("world"), "daily": [], "HUMAN_LIKENESS_PROVEN": False,
                   "REAL_MODEL_SEVEN_DAY_VALIDATED": False}
    # The config constructor verifies bounded goals and known fields before export.
    try:
        config = LongRunConfig.from_dict(data["manifest"]["config"])
        manifest = {**data["manifest"], "config": config.to_dict(),
                    "source": "COMMITTED_M5_SESSION_METADATA", "session_id": data["session"].get("session_id")}
    except (KeyError, ValueError, TypeError):
        manifest = {"configuration_status": "INVALID_UNVERIFIED",
                    "source": "COMMITTED_M5_SESSION_METADATA", "session_id": data.get("session", {}).get("session_id")}
    for name, value in (("summary.json", summary), ("manifest.json", manifest)):
        (destination / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    requests = [{k: r.get(k) for k in REQUEST_FIELDS} for r in data.get("requests", [])]
    try:
        activities = activities_from_facts(data)
    except (KeyError, ValueError, TypeError):
        activities = []
    for name, rows in (("daily.jsonl", summary["daily"]), ("requests.jsonl", requests),
                       ("activities.jsonl", activities),
                       ("checkpoints.jsonl", data.get("checkpoints", []))):
        (destination / name).write_text("".join(canonical_json(row) + "\n" for row in rows), encoding="utf-8")
    report = (render_report(summary) if "L2" in summary["evaluation"] and "hunger" in summary["evaluation"]["L2"] else
              "# M5 运行事实审计失败\n\nL1：FAIL。事实来源缺失或损坏；不得据此宣布工程通过。\n"
              "L2：不可可靠评价。L3：UNRESOLVED／未审核。\n")
    (destination / "report.md").write_text(report, encoding="utf-8")
    # Read-only export may target a separate directory. It writes report files
    # only and does not change source SQLite or execute missing world actions.
    for day in summary["daily"]:
        try:
            _write_daily(day, destination)
        except ValueError:
            if summary["evaluation"]["L1"]["status"] != "FAIL":
                raise
            summary.setdefault("daily_report_export_conflicts", []).append({
                "day": day["day"], "category": "EXISTING_REPORT_PRESERVED_AFTER_FACT_AUDIT_FAILURE"})
    if summary.get("daily_report_export_conflicts"):
        (destination / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def _compact_snapshot(state):
    return {**state, "commitments": [c for c in state.get("commitments", [])
                                     if c["status"] in {"ACTIVE", "PAUSED"}]}


def _daily_report(row):
    return (f"# M5 第 {row['day']} 模拟日报\n\n"
            f"实际区间 [{row['from_minute']}, {row['to_minute']})；模拟分钟 {row['simulation_minutes']}。\n\n"
            f"活动阶段分钟：{canonical_json(row['activity_phase_minutes'])}。\n"
            f"工作 {row['work_minutes']} 分钟，收入 {row['work_income_cents']} cents；"
            f"购买支出 {row['purchase_spending_cents']} cents，进食 {row['meal_events']} 次。\n\n"
            f"高层选择：{canonical_json(row.get('proposal_activity_counts', {}))}；"
            f"合法性/请求结果：{canonical_json(row.get('request_status_counts', {}))}。\n\n"
            f"需求与资源变化：{canonical_json(row.get('need_and_resource_changes', {}))}。\n\n"
            f"观测预警 {len(row.get('warnings', []))} 条，仅记录，不干预。\n"
            "跨午夜按真实分钟分配，起止状态仅用实际检查点；缺失状态和token保留null。\n"
            "行为合理性：UNRESOLVED／未审核；未自动合成总分或真人相似度。\n")


def _write_daily(row, destination):
    folder = Path(destination) / "daily"
    folder.mkdir(parents=True, exist_ok=True)
    item = {**row, "initial_state": _compact_snapshot(row["initial_state"]) if row["initial_state"] else None,
            "final_state": _compact_snapshot(row["final_state"]) if row["final_state"] else None,
            "state_checkpoints": [{**c, "state": _compact_snapshot(c["state"])}
                                  for c in row.get("state_checkpoints", [])]}
    json_path, report_path = folder / f"day{row['day']:03d}.json", folder / f"day{row['day']:03d}.md"
    created = False
    for path, text in ((json_path, canonical_json(item) + "\n"), (report_path, _daily_report(item))):
        if path.exists():
            if path.read_text(encoding="utf-8") != text:
                raise ValueError("DAILY_REPORT_CONTENT_MISMATCH")
        else:
            path.write_text(text, encoding="utf-8")
            created = True
    return {"day": row["day"], "json_path": str(json_path), "report_path": str(report_path), "created": created}


def export_daily_checkpoint(session, checkpoint) -> dict:
    """Export one completed simulation day from a bounded read-only SQL window.

    Existing identical files are no-ops; a mismatch is never overwritten. Missing
    files after a crash can be reconstructed without another model or action.
    """
    minute = checkpoint["minute"]
    if minute <= 0 or minute % 1440:
        raise ValueError("DAILY_REPORT_REQUIRES_EXACT_MIDNIGHT_CHECKPOINT")
    start = minute - 1440
    db = session.db
    with session.world.store.read_snapshot():
        previous = db.execute("SELECT data FROM m5_checkpoints WHERE minute=?", (start,)).fetchone()
        if previous is None:
            raise ValueError("DAILY_REPORT_MISSING_START_CHECKPOINT")
        first = json.loads(previous[0])
        steps = [{"status": r[0], **json.loads(r[1])} for r in db.execute(
            "SELECT status,data FROM m5_steps WHERE status='COMMITTED' "
            "AND json_extract(data,'$.from_minute')>=? AND json_extract(data,'$.from_minute')<? ORDER BY ordinal",
            (start, minute))]
        requests = [{"request_id": r[0], "phase": r[1], **json.loads(r[2])} for r in db.execute(
            "SELECT id,phase,data FROM m5_requests WHERE json_extract(data,'$.minute')>=? "
            "AND json_extract(data,'$.minute')<? ORDER BY ordinal", (start, minute))]
        events = [{**dict(r), "payload": json.loads(r["payload"])} for r in db.execute(
            "SELECT * FROM events WHERE minute>=? AND minute<=? ORDER BY seq", (start, minute))]
        data = {"window_initial_state": _compact_snapshot(first["state"]),
                "world": _compact_snapshot(checkpoint["state"]), "steps": steps, "requests": requests,
                "events": events, "checkpoints": [first, checkpoint],
                "manifest": {"config": session.config.to_dict()}}
    rows = daily_metrics(data, session.config.warnings)
    row = next(r for r in rows if r["day"] == minute // 1440)
    return _write_daily(row, session.dir)
