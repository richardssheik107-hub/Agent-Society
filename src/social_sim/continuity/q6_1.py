"""Q6.1 短链真实决策 pilot 的审计运行层。

该模块只负责把既有 ContinuityWorld、单请求 decision client 和确定性活动
执行编排成一个有界实验。它不改变 Q6 的状态机，也不把模型输出当成事实。
"""
from __future__ import annotations

import json
import platform
import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .context import observe
from .decision import ActivityDecisionRunner
from .engine import ContinuityWorld
from .models import canonical_json, digest
from .validation import validate_world

EXPERIMENT_NAME = "Q6_1_REAL_SHORT_HORIZON_CONTINUITY"
MAX_REAL_DECISIONS = 4
MAX_EXTENDED_DECISIONS = 12
DEFAULT_TIMEOUT_SECONDS = 60.0

PROVIDER_FAILURE_STATUSES = frozenset({
    "PROVIDER_TIMEOUT",
    "PROVIDER_ERROR",
    "PROVIDER_CONTRACT_ERROR",
    "PROVIDER_REFUSAL",
    "PROVIDER_SCHEMA_MISMATCH",
    "NO_CHOICES",
    "EMPTY_FINAL_CONTENT",
    "EMPTY_FINAL_CONTENT_WITH_REASONING",
    "TOOL_CALL_INSTEAD_OF_TEXT",
    "OUTPUT_BUDGET_EXHAUSTED",
})


def validate_decision_budget(max_decisions: int, *, extended_pilot: bool = False) -> None:
    """Enforce the Q6.1 four-call default and explicit twelve-call extension."""
    if isinstance(max_decisions, bool) or not isinstance(max_decisions, int):
        raise ValueError("max_decisions must be an integer")
    if max_decisions < 1:
        raise ValueError("max_decisions must be positive")
    if max_decisions > MAX_EXTENDED_DECISIONS:
        raise ValueError("max_decisions cannot exceed 12")
    if max_decisions > MAX_REAL_DECISIONS and not extended_pilot:
        raise ValueError("more than 4 decisions requires --extended-pilot")


def _safe_counter(client: object, name: str) -> int:
    value = getattr(client, name, 0)
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _safe_metadata_value(value: object, *, pattern: str = r"[A-Za-z0-9_.:/-]{1,80}") -> str | None:
    if (
        isinstance(value, str)
        and not value.startswith(("sk-", "ark-"))
        and re.fullmatch(pattern, value)
    ):
        return value
    return None


def _metadata(client: object, row: Mapping[str, Any], name: str) -> object:
    if name in row:
        return row[name]
    source = getattr(client, "last_metadata", None)
    return getattr(source, name, None) if source is not None else None


def _object_media_state(world: ContinuityWorld, actor_id: int) -> dict[str, dict[str, Any]]:
    media: dict[str, dict[str, Any]] = {}
    for result in world.store.db.execute("SELECT id FROM objects ORDER BY id"):
        obj = world.store.object(result[0])
        if "watchable" not in obj["capabilities"]:
            continue
        link = world.store.link(actor_id, obj["object_id"])
        watched = sorted(int(value) for value in link["watched"])
        next_episode = next(
            (episode for episode in range(1, obj["episodes"] + 1) if episode not in watched),
            None,
        )
        media[obj["object_id"]] = {
            "watched": watched,
            "offsets": {str(key): int(value) for key, value in link["offsets"].items()},
            "view_counts": {str(key): int(value) for key, value in link["view_counts"].items()},
            "next_episode": next_episode,
            "total_episodes": obj["episodes"],
        }
    return media


def project_state(world: ContinuityWorld, actor_id: int = 1) -> dict[str, Any]:
    """Return only the auditable state fields needed by Q6.1 markers."""
    actor = world.store.actor(actor_id)
    inventory: dict[str, int] = {}
    play_minutes: dict[str, int] = {}
    for result in world.store.db.execute("SELECT id FROM objects ORDER BY id"):
        obj = world.store.object(result[0])
        link = world.store.link(actor_id, obj["object_id"])
        inventory[obj["object_id"]] = int(link["quantity"])
        if "playable" in obj["capabilities"]:
            play_minutes[obj["object_id"]] = int(link["play_minutes"])
    commitment = world.store.commitment(actor_id)
    safe_commitment = None
    if commitment is not None:
        safe_commitment = {
            key: commitment.get(key)
            for key in ("id", "activity", "target", "episode", "phase", "status", "remaining_min")
        }
    return {
        "minute": world.minute,
        "state_version": actor["version"],
        "money_cents": actor["money_cents"],
        "hunger_milli": actor["hunger_milli"],
        "energy_milli": actor["energy_milli"],
        "location": actor["location"],
        "inventory": inventory,
        "media_progress": _object_media_state(world, actor_id),
        "play_minutes": play_minutes,
        "commitment": safe_commitment,
    }


def observation_fingerprint(world: ContinuityWorld, actor_id: int = 1) -> tuple[str, int]:
    """Hash and size the next bounded observation without retaining its text."""
    value = observe(world, actor_id)
    encoded = canonical_json(value)
    return digest(value), len(encoded)


def _delta(before: Mapping[str, int], after: Mapping[str, int]) -> dict[str, int]:
    keys = sorted(set(before) | set(after))
    return {key: int(after.get(key, 0)) - int(before.get(key, 0))
            for key in keys if after.get(key, 0) != before.get(key, 0)}


def _media_monotonic(before: Mapping[str, Any], after: Mapping[str, Any]) -> bool:
    for object_id, old in before.items():
        new = after.get(object_id)
        if not isinstance(new, Mapping):
            return False
        if not set(old.get("watched", ())).issubset(set(new.get("watched", ()))):
            return False
        old_offsets = old.get("offsets", {})
        new_offsets = new.get("offsets", {})
        for episode, value in old_offsets.items():
            if int(new_offsets.get(episode, -1)) < int(value):
                return False
    return True


def _normalize_status(row: Mapping[str, Any]) -> str:
    status = row.get("status")
    if status == "PROVIDER_CONTRACT_ERROR":
        category = row.get("failure_category")
        if isinstance(category, str) and category:
            return category
    return status if isinstance(status, str) else "ARCHITECTURE_ERROR"


def _is_provider_failure(status: str) -> bool:
    return status in PROVIDER_FAILURE_STATUSES or status.startswith("PROVIDER_")


def _safe_request_status(status: str) -> str:
    return status if re.fullmatch(r"[A-Z0-9_]{1,64}", status) else "ARCHITECTURE_ERROR"


class Q61PilotRunner:
    """Run a bounded sequence of high-level decisions against one persistent world."""

    def __init__(
        self,
        world: ContinuityWorld,
        client: object,
        *,
        max_decisions: int = MAX_REAL_DECISIONS,
        extended_pilot: bool = False,
        actor_id: int = 1,
        hard_timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        validate_decision_budget(max_decisions, extended_pilot=extended_pilot)
        self.world = world
        self.client = client
        self.max_decisions = max_decisions
        self.actor_id = actor_id
        self.decision_runner = ActivityDecisionRunner(
            world,
            client,
            max_calls=max_decisions,
            hard_timeout_seconds=hard_timeout_seconds,
        )

    def _execute_commitment(self, request_id: str) -> dict[str, Any]:
        micro_steps = 0
        while commitment := self.world.store.commitment(self.actor_id):
            if commitment["status"] != "ACTIVE" or commitment["remaining_min"] <= 0:
                raise RuntimeError("invalid active commitment phase")
            target = self.world.minute + min(commitment["remaining_min"], 15)
            result = self.world.advance(f"{request_id}:t{target}", target)
            if not result["accepted"]:
                raise RuntimeError(result["reason"])
            micro_steps += 1
        final = self.world.store.get_commitment(request_id)
        return {
            "commitment_id": request_id,
            "commitment_status": final["status"],
            "commitment_activity": final["activity"],
            "micro_steps": micro_steps,
            "elapsed_simulation_minutes": final["elapsed_min"],
            "execution_failure_reason": final["failure_reason"],
        }

    def _row_base(
        self,
        index: int,
        request_id: str,
        before: Mapping[str, Any],
        after: Mapping[str, Any],
        observation_before: str,
        observation_after: str,
        observation_chars: int,
        before_events: int,
        raw: Mapping[str, Any],
        provider_requests: int,
    ) -> dict[str, Any]:
        proposal = raw.get("proposal") if isinstance(raw.get("proposal"), Mapping) else {}
        metadata_model = _metadata(self.client, raw, "provider_model")
        finish_reason = _metadata(self.client, raw, "finish_reason")
        http_status = _metadata(self.client, raw, "http_status")
        row = {
            "decision_index": index,
            "request_id": request_id,
            "simulation_minute_before": before["minute"],
            "simulation_minute_after": after["minute"],
            "state_version_before": before["state_version"],
            "state_version_after": after["state_version"],
            "application_calls": raw.get("application_calls", 0),
            "provider_requests": provider_requests,
            "provider_model": _safe_metadata_value(metadata_model),
            "http_status": http_status if isinstance(http_status, int) else None,
            "finish_reason": _safe_metadata_value(finish_reason, pattern=r"[A-Za-z0-9_.:-]{1,64}"),
            "input_tokens": raw.get("input_tokens"),
            "output_tokens": raw.get("output_tokens"),
            "reasoning_tokens": raw.get("reasoning_tokens"),
            "latency_seconds": raw.get("latency_seconds"),
            "observation_chars": observation_chars,
            "observation_digest_before": observation_before,
            "observation_digest_after": observation_after,
            "proposal_activity": proposal.get("activity"),
            "proposal_target": proposal.get("target"),
            "decision_status": _safe_request_status(_normalize_status(raw)),
            "rule_reason": (raw.get("result") or {}).get("reason") if isinstance(raw.get("result"), Mapping) else None,
            "commitment_id": None,
            "commitment_status": None,
            "commitment_activity": None,
            "micro_steps": 0,
            "elapsed_simulation_minutes": after["minute"] - before["minute"],
            "events_generated": len(self.world.store.events()) - before_events,
            "money_before": before["money_cents"],
            "money_after": after["money_cents"],
            "hunger_before": before["hunger_milli"],
            "hunger_after": after["hunger_milli"],
            "energy_before": before["energy_milli"],
            "energy_after": after["energy_milli"],
            "location_before": before["location"],
            "location_after": after["location"],
            "inventory_delta": _delta(before["inventory"], after["inventory"]),
            "media_progress_before": before["media_progress"],
            "media_progress_after": after["media_progress"],
            "play_minutes_before": before["play_minutes"],
            "play_minutes_after": after["play_minutes"],
        }
        row["MEDIA_PROGRESS_MONOTONIC"] = _media_monotonic(
            before["media_progress"], after["media_progress"]
        )
        row["INVENTORY_CONSISTENT"] = all(value >= 0 for value in after["inventory"].values())
        row["MONEY_CONSISTENT"] = after["money_cents"] >= 0
        row["NO_TIME_REVERSAL"] = after["minute"] >= before["minute"]
        row["REPEATED_OWNERSHIP_CONFLICT"] = (
            row["proposal_activity"] == "BUY"
            and isinstance(row["proposal_target"], str)
            and before["inventory"].get(row["proposal_target"], 0) > 0
        )
        row["STATE_FEEDBACK_CHANGED"] = observation_before != observation_after
        row["state_feedback_changed"] = row["STATE_FEEDBACK_CHANGED"]
        return row

    async def run(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        rows: list[dict[str, Any]] = []
        termination_reason = "BUDGET_COMPLETED"
        for index in range(1, self.max_decisions + 1):
            request_id = f"q6_1:{index}"
            before = project_state(self.world, self.actor_id)
            observation_before, observation_chars = observation_fingerprint(self.world, self.actor_id)
            before_events = len(self.world.store.events())
            provider_before = _safe_counter(self.client, "provider_request_count")
            if provider_before == 0:
                provider_before = _safe_counter(self.client, "call_count")
            try:
                raw = await self.decision_runner.decide(request_id, self.actor_id)
                if not isinstance(raw, Mapping):
                    raise RuntimeError("decision runner returned non-mapping")
                normalized = _normalize_status(raw)
                if normalized == "DECISION_ACCEPTED":
                    execution = self._execute_commitment(request_id)
                    raw = {**raw, **execution}
                    if execution["commitment_status"] != "COMPLETED":
                        termination_reason = "COMMITMENT_FAILED"
                elif normalized != "DECISION_ACCEPTED":
                    termination_reason = normalized
            except Exception:
                raw = {"status": "ARCHITECTURE_ERROR", "application_calls": 0}
                termination_reason = "ARCHITECTURE_ERROR"
            after = project_state(self.world, self.actor_id)
            observation_after, _ = observation_fingerprint(self.world, self.actor_id)
            provider_after = _safe_counter(self.client, "provider_request_count")
            if provider_after == 0:
                provider_after = _safe_counter(self.client, "call_count")
            provider_requests = max(0, provider_after - provider_before)
            row = self._row_base(
                index,
                request_id,
                before,
                after,
                observation_before,
                observation_after,
                observation_chars,
                before_events,
                raw,
                provider_requests,
            )
            if isinstance(raw.get("commitment_id"), str):
                row["commitment_id"] = raw["commitment_id"]
            for key in (
                "commitment_status",
                "commitment_activity",
                "micro_steps",
                "elapsed_simulation_minutes",
                "execution_failure_reason",
            ):
                if key in raw:
                    row[key] = raw[key]
            rows.append(row)
            if termination_reason != "BUDGET_COMPLETED":
                break

        for index, row in enumerate(rows):
            if index + 1 < len(rows):
                visible = row["observation_digest_after"] == rows[index + 1]["observation_digest_before"]
                row["STATE_FEEDBACK_VISIBLE"] = visible
                row["state_feedback_visible"] = visible
            else:
                row["STATE_FEEDBACK_VISIBLE"] = None
                row["state_feedback_visible"] = None
        analysis = analyze_rows(rows)
        try:
            final_invariants = validate_world(self.world)
        except Exception:
            final_invariants = {"invariants": "FAIL"}
            termination_reason = "ARCHITECTURE_ERROR"
        summary = {
            "experiment": EXPERIMENT_NAME,
            "mode": "REAL_PROVIDER_PILOT",
            "planned_decisions": self.max_decisions,
            "application_calls": sum(int(row.get("application_calls") or 0) for row in rows),
            "provider_requests": sum(int(row.get("provider_requests") or 0) for row in rows),
            "completed_decisions": sum(row.get("commitment_status") == "COMPLETED" for row in rows),
            "accepted_decisions": sum(row.get("decision_status") == "DECISION_ACCEPTED" for row in rows),
            "rule_rejections": sum(row.get("decision_status") == "RULE_REJECTED" for row in rows),
            "provider_failures": sum(_is_provider_failure(row.get("decision_status", "")) for row in rows),
            "invalid_outputs": sum(row.get("decision_status") in {"INVALID_MODEL_OUTPUT", "OUTSIDE_CATALOG"}
                                   for row in rows),
            "commitment_failures": sum(row.get("commitment_status") == "FAILED" or
                                        row.get("decision_status") == "COMMITMENT_FAILED" for row in rows),
            "state_feedback_visible_rate": analysis["state_feedback_visible_rate"],
            "state_feedback_changed_rate": analysis["state_feedback_changed_rate"],
            "media_continuity_exercised": analysis["media_continuity_exercised"],
            "ownership_continuity_exercised": analysis["ownership_continuity_exercised"],
            "final_invariants": final_invariants,
            "autonomous_full_day_proven": False,
            "human_likeness_proven": False,
            "termination_reason": termination_reason,
            **analysis,
        }
        return summary, rows


def analyze_rows(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Compute objective markers from recorded transitions only.

    The analyzer intentionally accepts no answer labels, acceptable-action sets,
    future state, or model-judge output.
    """
    transitions = [row for row in rows if isinstance(row.get("STATE_FEEDBACK_VISIBLE"), bool)]
    visible_rate = (
        sum(row["STATE_FEEDBACK_VISIBLE"] for row in transitions) / len(transitions)
        if transitions else None
    )
    changed = [row for row in rows if isinstance(row.get("STATE_FEEDBACK_CHANGED"), bool)]
    changed_rate = (
        sum(row["STATE_FEEDBACK_CHANGED"] for row in changed) / len(changed)
        if changed else None
    )
    activities = [row.get("proposal_activity") for row in rows]
    media_exercised = any(
        activity == "WATCH"
        and any(
            value.get("watched") or value.get("offsets")
            for value in row.get("media_progress_before", {}).values()
        )
        for activity, row in zip(activities, rows, strict=True)
    )
    ownership_exercised = any(
        any(value > 0 for value in row.get("inventory_delta", {}).values())
        and row.get("proposal_activity") in {"MEAL", "PLAY"}
        for row in rows
    )
    immediate_repeat = any(
        activities[index] is not None and activities[index] == activities[index - 1]
        for index in range(1, len(activities))
    )
    immediate_meal = any(activities[index] == activities[index - 1] == "MEAL"
                         for index in range(1, len(activities)))
    immediate_watch = any(activities[index] == activities[index - 1] == "WATCH"
                          for index in range(1, len(activities)))
    repeated_ownership = any(row.get("REPEATED_OWNERSHIP_CONFLICT") is True for row in rows)
    no_duplicate_effect = len({row.get("request_id") for row in rows}) == len(rows)
    no_time_reversal = all(row.get("NO_TIME_REVERSAL") is True for row in rows)
    inventory_consistent = all(row.get("INVENTORY_CONSISTENT") is True for row in rows)
    money_consistent = all(row.get("MONEY_CONSISTENT") is True for row in rows)
    media_monotonic = all(row.get("MEDIA_PROGRESS_MONOTONIC") is True for row in rows)
    rule_rejections = sum(row.get("decision_status") == "RULE_REJECTED" for row in rows)
    commitment_failures = sum(row.get("commitment_status") == "FAILED" for row in rows)
    provider_failures = sum(_is_provider_failure(row.get("decision_status", "")) for row in rows)
    invalid_outputs = sum(row.get("decision_status") in {"INVALID_MODEL_OUTPUT", "OUTSIDE_CATALOG"}
                          for row in rows)
    return {
        "STATE_FEEDBACK_VISIBLE": all(row["STATE_FEEDBACK_VISIBLE"] for row in transitions)
        if transitions else None,
        "STATE_FEEDBACK_CHANGED": any(row["STATE_FEEDBACK_CHANGED"] for row in changed),
        "MEDIA_CONTINUITY_EXERCISED": media_exercised,
        "MEDIA_PROGRESS_MONOTONIC": media_monotonic,
        "OWNERSHIP_CONTINUITY_EXERCISED": ownership_exercised,
        "OWNERSHIP_CONSISTENT": inventory_consistent,
        "INVENTORY_CONSISTENT": inventory_consistent,
        "MONEY_CONSISTENT": money_consistent,
        "NO_DUPLICATE_EFFECT": no_duplicate_effect,
        "NO_TIME_REVERSAL": no_time_reversal,
        "IMMEDIATE_ACTIVITY_REPEAT": immediate_repeat,
        "IMMEDIATE_MEAL_REPEAT": immediate_meal,
        "IMMEDIATE_WATCH_REPEAT": immediate_watch,
        "REPEATED_OWNERSHIP_CONFLICT": repeated_ownership,
        "RULE_REJECTION_COUNT": rule_rejections,
        "COMMITMENT_FAILURE_COUNT": commitment_failures,
        "PROVIDER_FAILURE_COUNT": provider_failures,
        "INVALID_OUTPUT_COUNT": invalid_outputs,
        "state_feedback_visible_rate": visible_rate,
        "state_feedback_changed_rate": changed_rate,
        "media_continuity_exercised": media_exercised,
        "ownership_continuity_exercised": ownership_exercised,
    }


def _git_value(args: list[str], root: Path) -> str | None:
    try:
        return subprocess.check_output(args, cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def environment_record(root: Path, *, provider_model: str | None, real_provider: bool) -> dict[str, Any]:
    """Build a secret-free environment record for an artifact directory."""
    model = _safe_metadata_value(provider_model)
    upstream = _git_value(["git", "rev-parse", "HEAD:third_party/AgentSociety"], root)
    return {
        "git_commit": _git_value(["git", "rev-parse", "HEAD"], root),
        "branch": _git_value(["git", "branch", "--show-current"], root),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "agentsociety_submodule_commit": upstream,
        "provider_model": model,
        "real_provider_executed": bool(real_provider),
        "contains_secret": False,
    }


def render_report(summary: Mapping[str, Any]) -> str:
    """Render a concise Chinese artifact report without raw provider text."""
    return "\n".join([
        "# Q6.1 真实模型短链连续性 Pilot 实验报告",
        "",
        f"实验：`{summary.get('experiment')}`；模式：`{summary.get('mode')}`。",
        f"计划高层决策：{summary.get('planned_decisions')}；实际 application calls：{summary.get('application_calls')}；"
        f"provider requests：{summary.get('provider_requests')}。",
        "",
        "本报告只记录模型提案、确定性规则执行、持久状态反馈和客观失败分类。"
        "它不证明全天自主生活或人类相似性。",
        "",
        f"终止原因：`{summary.get('termination_reason')}`。",
        f"状态反馈可见率：`{summary.get('state_feedback_visible_rate')}`；"
        f"状态反馈变化率：`{summary.get('state_feedback_changed_rate')}`。",
        f"媒体连续性：`{summary.get('media_continuity_exercised')}`；"
        f"所有权连续性：`{summary.get('ownership_continuity_exercised')}`。",
        f"最终不变量：`{summary.get('final_invariants')}`。",
        "",
        "边界：本实验最多四次真实高层请求（扩展预算需额外显式授权），活动微步骤不调用模型。"
        "若 provider、输出契约、规则或 commitment 失败，后续请求停止；不自动重试、修复或伪造 WAIT。",
        "",
        "结论字段：`SHORT_HORIZON_STATE_CONTINUITY` 只有在真实 pilot 的状态反馈和确定性执行均可复核时才可标记为 SUPPORTED。",
        "",
    ])


def write_artifacts(
    output: str | Path,
    world: ContinuityWorld,
    summary: Mapping[str, Any],
    rows: list[Mapping[str, Any]],
    environment: Mapping[str, Any],
) -> Path:
    """Write the Q6.1 artifact contract with no raw prompts or completions."""
    directory = Path(output)
    directory.mkdir(parents=True, exist_ok=True)
    protected = (
        "summary.json",
        "decisions.jsonl",
        "events.jsonl",
        "final_state.json",
        "environment.json",
        "report_zh.md",
    )
    if any((directory / name).exists() for name in protected):
        raise FileExistsError(f"artifact files already exist in {directory}")
    (directory / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    with (directory / "decisions.jsonl").open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(dict(row), ensure_ascii=False, allow_nan=False) + "\n")
    with (directory / "events.jsonl").open("w", encoding="utf-8") as stream:
        for event in world.store.events():
            stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")
    (directory / "final_state.json").write_text(
        json.dumps(world.store.snapshot(), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    (directory / "environment.json").write_text(
        json.dumps(dict(environment), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    (directory / "report_zh.md").write_text(render_report(summary), encoding="utf-8")
    return directory
