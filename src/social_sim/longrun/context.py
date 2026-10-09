"""M5 bounded context; summaries are deterministic committed world facts."""
from __future__ import annotations

import json

from social_sim.continuity.context import decision_prompt
from social_sim.continuity.m2_acquire import m2_decision_prompt
from social_sim.continuity.models import canonical_json


class ContextBudgetExceeded(ValueError):
    """Critical state never disappears to make an oversized prompt fit."""


def build_context(world, config, actor_id: int = 1) -> tuple[str, str, dict]:
    """Extend (without editing) the frozen M2 prompt, or legacy opt-out prompt.

    UTF-8 bytes are a deliberately conservative *content* token upper bound,
    not measured provider tokens. A fixed 32-token envelope reserve is declared
    separately; provider-specific wire token accounting remains unknown.
    """
    with world.store.read_snapshot():
        prompt = m2_decision_prompt if world.acquire_enabled else decision_prompt
        system, base = prompt(world, actor_id, max_chars=config.max_context_chars)
        system += (
            " M5_LONG_CONTEXT_V1: simulation time and all resource values are committed facts."
            " Experiment goals are externally supplied, not inferred personal preferences."
            " Older history is a deterministic aggregate, not a complete autobiographical memory."
        )
        limit = config.recent_activity_limit
        rows = world.store.db.execute(
            "SELECT data FROM commitments WHERE actor_id=? AND status NOT IN ('ACTIVE','PAUSED') "
            "ORDER BY json_extract(data,'$.started_minute') DESC,id DESC LIMIT ?",
            (actor_id, limit),
        ).fetchall()
        recent = [json.loads(row[0]) for row in reversed(rows)]
        recent_ids = [item["id"] for item in recent]
        older = {}
        # Grouped totals have a fixed number of activity types, not one entry per day.
        exclusion = " AND id NOT IN (" + ",".join("?" for _ in recent_ids) + ")" if recent_ids else ""
        for row in world.store.db.execute(
            "SELECT json_extract(data,'$.activity') activity,status,count(*) count,"
            "sum(json_extract(data,'$.elapsed_min')) minutes FROM commitments "
            "WHERE actor_id=? AND status NOT IN ('ACTIVE','PAUSED')" + exclusion
            + " GROUP BY activity,status ORDER BY activity,status", (actor_id, *recent_ids),
        ):
            older.setdefault(row["activity"], {})[row["status"]] = {
                "activities": row["count"], "executed_minutes": row["minutes"],
            }
        ownership, media = [], []
        for row in world.store.db.execute("SELECT id FROM objects ORDER BY id"):
            obj = world.store.object(row[0])
            link = world.store.link(actor_id, obj["object_id"])
            if link["quantity"]:
                ownership.append({"object_id": obj["object_id"], "quantity": link["quantity"],
                                  "available": obj["available"], "capabilities": obj["capabilities"]})
            if "watchable" in obj["capabilities"]:
                watched = set(link["watched"])
                next_ep = next((i for i in range(1, obj["episodes"] + 1) if i not in watched), None)
                media.append({"object_id": obj["object_id"], "completed_episodes": len(watched),
                              "total_episodes": obj["episodes"], "next_episode": next_ep,
                              "next_offset_min": link["offsets"].get(str(next_ep), 0),
                              "cumulative_watch_minutes": sum(link["offsets"].values())})
        minute = world.minute
        extension = {
            "schema": "M5_LONG_CONTEXT_V1", "source": "COMMITTED_SQLITE_FACTS_NO_LLM_SUMMARY",
            "clock": {"simulation_day": minute // 1440 + 1, "minute_of_day": minute % 1440,
                      "hour": minute % 1440 // 60, "day_minutes": 1440},
            "all_owned_objects": ownership, "all_media_progress": media,
            "current_task": world.store.commitment(actor_id),
            "recent_committed_activities": [
                {key: item[key] for key in ("id", "activity", "target", "status", "started_minute",
                                          "elapsed_min", "failure_reason")} for item in recent],
            "older_committed_activity_totals": older,
            "history_scope": "RECENT_TERMINAL_ACTIVITIES_PLUS_CUMULATIVE_OLDER_TOTALS",
            "goals": {"mode": config.goal_mode, "source": "EXPLICIT_EXPERIMENT_CONFIGURATION",
                      "declared": list(config.goals)},
        }
        user = canonical_json({**json.loads(base), "m5": extension})
    chars = len(system) + len(user)
    content_bytes = len(system.encode("utf-8")) + len(user.encode("utf-8"))
    bound = content_bytes + 32
    metrics = {"prompt_chars": chars, "context_chars": chars, "utf8_content_bytes": content_bytes,
               "token_upper_bound": bound, "context_token_upper_bound": bound,
               "token_accounting": "UTF8_CONTENT_BYTE_UPPER_BOUND_WITH_32_ENVELOPE_RESERVE",
               "actual_input_tokens": None, "provider_wire_tokens_known": False,
               "recent_activities": len(recent), "history_source": extension["source"]}
    if chars > config.max_context_chars or bound > config.max_context_tokens:
        raise ContextBudgetExceeded("CONTEXT_BUDGET_EXCEEDED_CRITICAL_FACTS_PRESERVED")
    return system, user, metrics
