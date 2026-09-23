"""Q6.2 可执行活动投影：只读规则条件，不替模型制定日程。"""
from __future__ import annotations

import json

from .context import decision_prompt, observe
from .engine import ContinuityWorld
from .models import TIMED_ACTIVITIES, canonical_json, digest, integer

RAW = "A_RAW"
FEASIBLE = "B_FEASIBLE"
OBJECT_ACTIVITIES = ("MEAL", "WATCH", "PLAY")
# 与冻结 Q6.1 提示中的目的地一致；未增加 action 或 target。
DESTINATIONS = ("home", "restaurant", "office", "park")


def canonical_options(options: list[dict]) -> list[dict]:
    """Stable activity/target ordering; order is not a preference ranking."""
    pairs = []
    for option in options:
        if not isinstance(option, dict):
            raise ValueError("invalid candidate")
        activity, target = option.get("activity"), option.get("target")
        if not isinstance(activity, str) or (target is not None and not isinstance(target, str)):
            raise ValueError("invalid candidate")
        pairs.append({"activity": activity, "target": target})
    return sorted(pairs, key=lambda pair: (pair["activity"], pair["target"] or ""))


def candidate_fingerprint(options: list[dict]) -> str:
    """Digest of the current feasible set, independent of discovery order."""
    return digest(canonical_options(options))


def proposal_in_feasible_set(proposal: object, projection: dict) -> bool:
    """Audit membership without substituting a model proposal."""
    if not isinstance(proposal, dict):
        return False
    activity, target = proposal.get("activity"), proposal.get("target")
    if not isinstance(activity, str) or (target is not None and not isinstance(target, str)):
        return False
    return {"activity": activity, "target": target} in projection["executable_options"]


def project_actions(world: ContinuityWorld, actor_id: int = 1, *, limit: int = 5) -> dict:
    """仅检查与原 observation 相同的有限对象候选，不扫描所有对象×规则。

    executable_options 是当前状态下的规则可行性，不是偏好排序。blocked
    用于审计，不放入 B 提示，以免同时引入“答案解释”这一额外变量。
    """
    integer(limit, "limit", 1, 10)
    with world.store.read_snapshot():
        observation = observe(world, actor_id, limit=limit)
        candidates = [{"activity": name, "target": None} for name in TIMED_ACTIVITIES]
        candidates.extend({"activity": "TRAVEL", "target": place} for place in DESTINATIONS)
        candidates.extend({"activity": activity, "target": item["id"]}
                          for item in observation["objects"] for activity in OBJECT_ACTIVITIES)
        assessments = [world.preview_activity(actor_id, **candidate) for candidate in candidates]
        options = [candidate for candidate, check in zip(candidates, assessments, strict=True)
                   if check["executable_now"]]
        options = canonical_options(options)
        return {
            "schema": "Q62_ACTION_PROJECTION_V1",
            "observation_digest": digest(observation),
            "state_version": observation["actor"]["version"],
            "simulation_minute": observation["minute"],
            "object_candidates": len(observation["objects"]),
            "pairs_checked": len(candidates),
            "executable_options": options,
            "candidate_count": len(options),
            "candidate_digest": candidate_fingerprint(options),
            "assessments": assessments,
            "scope": "CURRENT_SNAPSHOT_NO_EXTERNAL_CHANGES",
            "preference_ranking": False,
            "guarantees_future_success": False,
            "provider_requests": 0,
        }


def projected_prompt(world: ContinuityWorld, actor_id: int = 1, *,
                     mode: str = FEASIBLE, max_chars: int = 5000) -> tuple[str, str]:
    """A 字节级复用旧提示；B 只追加当前可执行的 activity/target 对。

    该入口是 opt-in。Q6.1 默认 decision_prompt 及旧实验不会自动改用 B。
    """
    if mode not in (RAW, FEASIBLE):
        raise ValueError("unknown Q6.2 context mode")
    integer(max_chars, "max_chars", 1, 100_000)
    with world.store.read_snapshot():
        system, user = decision_prompt(world, actor_id)
        if mode == FEASIBLE:
            projection = project_actions(world, actor_id)
            if not projection["executable_options"]:
                raise ValueError("NO_EXECUTABLE_OPTIONS")
            body = json.loads(user)
            if digest(body["observation"]) != projection["observation_digest"]:
                raise RuntimeError("INCONSISTENT_PROJECTION_SNAPSHOT")
            body["executable_options"] = projection["executable_options"]
            user = canonical_json(body)
            system += (" Choose one activity/target pair from executable_options. "
                       "These are rule-feasible options, not a preference ranking.")
        if len(system) + len(user) > max_chars:
            raise ValueError("Q62_CONTEXT_BUDGET_EXCEEDED")
        return system, user
