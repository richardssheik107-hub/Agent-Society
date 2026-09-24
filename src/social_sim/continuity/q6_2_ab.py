"""Q6.2 bounded A_RAW/B_FEASIBLE session, with a zero-request dry run."""
from __future__ import annotations

import json
import re
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from .action_projection import (
    FEASIBLE,
    RAW,
    project_actions,
    projected_prompt,
    proposal_in_feasible_set,
)
from .benchmark import seed_demo
from .decision import ActivityDecisionRunner
from .engine import ContinuityWorld
from .models import canonical_json, digest
from .q6_1 import PROVIDER_FAILURE_STATUSES, Q61PilotRunner, project_state

MAX_DECISIONS_PER_ARM = 4
MAX_SESSION_REQUESTS = 8
ARM_MODES = {"arm_a": RAW, "arm_b": FEASIBLE}
GLOBAL_STOP_STATUSES = PROVIDER_FAILURE_STATUSES | {
    "ARCHITECTURE_ERROR", "INVALID_MODEL_OUTPUT", "OUTSIDE_CATALOG", "REQUEST_CANCELLED",
}
METRIC_NAMES = (
    "provider_success_rate", "strict_json_valid_rate", "proposal_in_feasible_set_rate",
    "rule_rejection_rate", "commitment_failure_rate", "accepted_decision_rate",
    "completed_decision_rate", "state_feedback_visible_rate",
    "immediate_activity_repeat_rate", "immediate_meal_repeat_rate",
    "immediate_watch_repeat_rate", "provider_requests", "input_tokens", "output_tokens",
    "latency_seconds", "candidate_count", "prompt_chars",
)


def validate_session_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value):
        raise ValueError("INVALID_SESSION_ID")
    return value


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _average(values: list[int | float]) -> float | None:
    return sum(values) / len(values) if values else None


def _metrics(rows: list[dict]) -> dict:
    calls = sum(int(row.get("application_calls") or 0) for row in rows)
    proposals = [row for row in rows if isinstance(row.get("proposal_activity"), str)]
    pairs = [(a, b) for a, b in zip(proposals, proposals[1:], strict=False)]
    provider_failures = sum(row.get("decision_status") in PROVIDER_FAILURE_STATUSES
                            or str(row.get("decision_status", "")).startswith("PROVIDER_")
                            for row in rows)
    succeeded = max(0, calls - provider_failures)
    visible = [row["STATE_FEEDBACK_VISIBLE"] for row in rows
               if isinstance(row.get("STATE_FEEDBACK_VISIBLE"), bool)]
    def token_sum(key: str) -> int:
        return sum(value for row in rows
                   if isinstance((value := row.get(key)), int) and not isinstance(value, bool))
    return {
        "provider_success_rate": _rate(succeeded, calls),
        "strict_json_valid_rate": _rate(len(proposals), succeeded),
        "proposal_in_feasible_set_rate": _rate(sum(r["PROPOSAL_IN_FEASIBLE_SET"] for r in proposals),
                                               len(proposals)),
        "rule_rejection_rate": _rate(sum(r["decision_status"] == "RULE_REJECTED" for r in proposals),
                                     len(proposals)),
        "commitment_failure_rate": _rate(sum(r.get("commitment_status") == "FAILED" for r in proposals),
                                          len(proposals)),
        "accepted_decision_rate": _rate(sum(r["decision_status"] == "DECISION_ACCEPTED" for r in proposals),
                                        len(proposals)),
        "completed_decision_rate": _rate(sum(r.get("commitment_status") == "COMPLETED" for r in proposals),
                                         len(proposals)),
        "state_feedback_visible_rate": _rate(sum(visible), len(visible)),
        "immediate_activity_repeat_rate": _rate(sum(a["proposal_activity"] == b["proposal_activity"]
                                                    for a, b in pairs), len(pairs)),
        "immediate_meal_repeat_rate": _rate(sum(a["proposal_activity"] == b["proposal_activity"] == "MEAL"
                                                for a, b in pairs), len(pairs)),
        "immediate_watch_repeat_rate": _rate(sum(a["proposal_activity"] == b["proposal_activity"] == "WATCH"
                                                 for a, b in pairs), len(pairs)),
        "provider_requests": sum(int(r.get("provider_requests") or 0) for r in rows),
        "input_tokens": token_sum("input_tokens"),
        "output_tokens": token_sum("output_tokens"),
        "latency_seconds": round(sum(float(r.get("latency_seconds") or 0) for r in rows), 6),
        "candidate_count": _average([r["candidate_count"] for r in rows if r.get("candidate_count") is not None]),
        "prompt_chars": _average([r["prompt_chars"] for r in rows if r.get("prompt_chars") is not None]),
    }


class _ProjectionCapture(ActivityDecisionRunner):
    def __init__(self, world: ContinuityWorld, client: object, mode: str):
        self.mode = mode
        self.current_request_id: str | None = None
        self.audit: dict[str, dict] = {}
        super().__init__(world, client, max_calls=MAX_DECISIONS_PER_ARM,
                         hard_timeout_seconds=60, prompt_builder=self._build_prompt)

    def _build_prompt(self, world: ContinuityWorld, actor_id: int) -> tuple[str, str]:
        projection = project_actions(world, actor_id)
        system, user = projected_prompt(world, actor_id, mode=self.mode)
        if self.current_request_id is None:
            raise RuntimeError("MISSING_REQUEST_ID")
        self.audit[self.current_request_id] = {
            "candidate_count": projection["candidate_count"],
            "candidate_digest": projection["candidate_digest"],
            "observation_digest": projection["observation_digest"],
            "state_version": projection["state_version"],
            "prompt_chars": len(system) + len(user),
            "projection": projection,
        }
        return system, user

    async def decide(self, request_id: str, actor_id: int = 1) -> dict:
        self.current_request_id = request_id
        try:
            return await super().decide(request_id, actor_id)
        finally:
            self.current_request_id = None


class ABArmRunner(Q61PilotRunner):
    def __init__(self, world: ContinuityWorld, client: object, mode: str):
        super().__init__(world, client, max_decisions=MAX_DECISIONS_PER_ARM)
        self.mode = mode
        self.decision_runner = _ProjectionCapture(world, client, mode)

    def _row_base(self, index: int, request_id: str, before: dict, after: dict,
                  observation_before: str, observation_after: str, observation_chars: int,
                  before_events: int, raw: dict, provider_requests: int) -> dict:
        row = super()._row_base(index, request_id, before, after, observation_before,
                                observation_after, observation_chars, before_events,
                                raw, provider_requests)
        audit = self.decision_runner.audit.get(request_id)
        if audit is None:
            row.update(candidate_count=None, candidate_digest=None, prompt_chars=None,
                       PROPOSAL_IN_FEASIBLE_SET=None)
        else:
            if (audit["state_version"] != before["state_version"]
                    or audit["observation_digest"] != observation_before):
                raise RuntimeError("PROJECTION_SNAPSHOT_MISMATCH")
            proposal = {"activity": row["proposal_activity"], "target": row["proposal_target"]}
            row.update(candidate_count=audit["candidate_count"],
                       candidate_digest=audit["candidate_digest"],
                       prompt_chars=audit["prompt_chars"],
                       PROPOSAL_IN_FEASIBLE_SET=(proposal_in_feasible_set(
                           proposal, audit["projection"]) if proposal["activity"] else None))
        row["context_mode"] = self.mode
        return row


def _write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def _write_arm(directory: Path, summary: dict, rows: list[dict], world: ContinuityWorld) -> None:
    _write_json(directory / "summary.json", summary)
    with (directory / "decisions.jsonl").open("x", encoding="utf-8") as stream:
        for row in rows:
            stream.write(canonical_json(row) + "\n")
    _write_json(directory / "final_state.json", world.store.snapshot())


def _configuration(session_id: str, schedule: str, initial_digest: str) -> dict:
    return {
        "experiment": "Q6_2_FEASIBLE_ACTION_REAL_AB", "session_id": session_id,
        "schedule": schedule, "arms": ARM_MODES,
        "initial_state_digest": initial_digest,
        "same_fixture_and_provider_contract": True,
        "provider_contract": "Q6_1_MINIMAL_CHAT_COMPLETIONS",
        "thinking_disabled_explicitly": False,
        "max_decisions_per_arm": MAX_DECISIONS_PER_ARM,
        "max_application_requests_total": MAX_SESSION_REQUESTS,
        "transport_retries": 0, "json_repair": False, "fallback_action": False,
        "primary_metric": "rule_rejection_rate",
        "secondary_metric": "proposal_in_feasible_set_rate",
        "metric_names": METRIC_NAMES,
        "provider_or_architecture_failure": "STOP_SESSION",
        "rule_rejection": "STOP_ARM_THEN_CONTINUE_OTHER_ARM",
        "repeated_meal_is_rule_failure": False,
        "contains_secret": False,
    }


def _prepare_worlds(output: Path, stack: ExitStack) -> dict[str, ContinuityWorld]:
    worlds = {}
    for name in ARM_MODES:
        directory = output / name
        directory.mkdir()
        world = stack.enter_context(ContinuityWorld(directory / "world.sqlite3"))
        seed_demo(world)
        worlds[name] = world
    if digest(worlds["arm_a"].store.snapshot()) != digest(worlds["arm_b"].store.snapshot()):
        raise RuntimeError("INITIAL_WORLDS_DIFFER")
    return worlds


def _comparison(summaries: dict[str, dict], *, executed: bool) -> dict:
    a, b = summaries["arm_a"], summaries["arm_b"]
    differences = {}
    for key in ("rule_rejection_rate", "proposal_in_feasible_set_rate"):
        av, bv = a.get("metrics", {}).get(key), b.get("metrics", {}).get(key)
        differences[key + "_B_minus_A"] = bv - av if av is not None and bv is not None else None
    return {
        "real_ab_executed": executed,
        "provider_requests": sum(s.get("provider_requests", 0) for s in summaries.values()),
        "both_arms_ran": all(s.get("status") == "EXECUTED" for s in summaries.values()),
        "causal_effect_proven": False,
        "differences": differences,
    }


def _report(config: dict, summaries: dict[str, dict], comparison: dict) -> str:
    return "\n".join((
        "# Q6.2 小预算 A/B 运行记录", "",
        f"Session: `{config['session_id']}`；顺序：`{config['schedule']}`。",
        f"A_RAW: `{summaries['arm_a']['status']}`；B_FEASIBLE: `{summaries['arm_b']['status']}`。",
        f"Provider requests: `{comparison['provider_requests']}`。",
        "主要比较是规则拒绝率与提案在当前可执行候选中的比例。",
        "重复进食只作为描述指标；单次小样本不证明人类相似性或稳定因果效果。",
        "A/B 使用相同初始状态的独立 world，失败不重试、不修复 JSON、不替换提案。", "",
    ))


def prepare_dry_run(output: Path, *, session_id: str, schedule: str = "AB") -> dict:
    """Create reviewable, secret-free artifacts without reading provider configuration."""
    validate_session_id(session_id)
    if schedule not in ("AB", "BA"):
        raise ValueError("INVALID_SCHEDULE")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    with ExitStack() as stack:
        worlds = _prepare_worlds(output, stack)
        config = _configuration(session_id, schedule, digest(worlds["arm_a"].store.snapshot()))
        config["mode"] = "DRY_RUN"
        _write_json(output / "config.json", config)
        summaries = {}
        for name, mode in ARM_MODES.items():
            projection = project_actions(worlds[name])
            system, user = projected_prompt(worlds[name], mode=mode)
            summary = {
                "status": "NOT_RUN", "context_mode": mode,
                "provider_requests": 0, "application_calls": 0,
                "candidate_count_initial": projection["candidate_count"],
                "candidate_digest_initial": projection["candidate_digest"],
                "prompt_chars_initial": len(system) + len(user),
                "initial_state": project_state(worlds[name]),
                "metrics": {key: None for key in METRIC_NAMES},
            }
            summaries[name] = summary
            _write_arm(output / name, summary, [], worlds[name])
        comparison = _comparison(summaries, executed=False)
        _write_json(output / "comparison.json", comparison)
        (output / "report_zh.md").write_text(_report(config, summaries, comparison), encoding="utf-8")
    return comparison


async def run_ab_session(output: Path, *, session_id: str, client: object,
                         schedule: str = "AB", real_provider: bool = False) -> dict:
    """Future opt-in real session; one client, two isolated worlds, eight calls maximum."""
    validate_session_id(session_id)
    if schedule not in ("AB", "BA"):
        raise ValueError("INVALID_SCHEDULE")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    order = ("arm_a", "arm_b") if schedule == "AB" else ("arm_b", "arm_a")
    with ExitStack() as stack:
        worlds = _prepare_worlds(output, stack)
        config = _configuration(session_id, schedule, digest(worlds["arm_a"].store.snapshot()))
        config["mode"] = "REAL_PROVIDER_AB" if real_provider else "SYNTHETIC_PROVIDER_AB_TEST"
        _write_json(output / "config.json", config)
        summaries: dict[str, dict[str, Any]] = {}
        stop_session = False
        for name in order:
            if stop_session:
                summary = {"status": "NOT_RUN", "context_mode": ARM_MODES[name],
                           "provider_requests": 0, "application_calls": 0,
                           "termination_reason": "OTHER_ARM_FATAL",
                           "metrics": {key: None for key in METRIC_NAMES}}
                rows = []
            else:
                runner = ABArmRunner(worlds[name], client, ARM_MODES[name])
                summary, rows = await runner.run()
                summary.update(status="EXECUTED", context_mode=ARM_MODES[name],
                               metrics=_metrics(rows))
                stop_session = summary["termination_reason"] in GLOBAL_STOP_STATUSES or (
                    str(summary["termination_reason"]).startswith("PROVIDER_"))
            summaries[name] = summary
            _write_arm(output / name, summary, rows, worlds[name])
        requests = sum(s["provider_requests"] for s in summaries.values())
        if requests > MAX_SESSION_REQUESTS:
            raise RuntimeError("SESSION_REQUEST_BUDGET_EXCEEDED")
        comparison = _comparison(summaries, executed=real_provider and requests > 0)
        _write_json(output / "comparison.json", comparison)
        (output / "report_zh.md").write_text(_report(config, summaries, comparison), encoding="utf-8")
    return comparison
