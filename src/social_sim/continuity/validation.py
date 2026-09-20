"""从事件账本独立核对事实；查出缺失关联、进度回退和无依据的完成。"""
from __future__ import annotations

from collections import Counter

from .engine import ContinuityWorld
from .models import digest, initial_link


def validate_world(world: ContinuityWorld) -> dict:
    state = world.store.snapshot()
    events = world.store.events()
    errors = []
    if not events or events[0]["kind"] != "WORLD_CREATED":
        raise AssertionError("missing genesis event")
    initial = events[0]["payload"]["initial"]
    money = {a["actor_id"]: a["money_cents"] for a in initial["actors"]}
    kcal = {a["actor_id"]: a["calories_kcal"] for a in initial["actors"]}
    work = {a["actor_id"]: a["work_minutes"] for a in initial["actors"]}
    location = {a["actor_id"]: a["location"] for a in initial["actors"]}
    stock = {o["object_id"]: o["stock"] for o in initial["objects"]}
    available = {o["object_id"]: o["available"] for o in initial["objects"]}
    quantities, completed, plays, views, offsets = (Counter() for _ in range(5))
    touched = set()
    prev_minute, clock = -1, initial["minute"]
    for event in events:
        if event["minute"] < prev_minute:
            errors.append("EVENT_TIME_REVERSAL")
        prev_minute = event["minute"]
        p, kind = event["payload"], event["kind"]
        if "actor_id" in p and "object_id" in p:
            touched.add((p["actor_id"], p["object_id"]))
        if kind == "TIME_ADVANCED":
            if p["from_minute"] != clock or p["to_minute"] <= clock:
                errors.append("TIME_LEDGER_MISMATCH")
            clock = p["to_minute"]
        if kind == "MOVED":
            location[p["actor_id"]] = p["destination"]
        if kind == "AVAILABILITY_CHANGED":
            available[p["object_id"]] = p["available"]
        if kind == "PURCHASED":
            money[p["actor_id"]] -= p["cost_cents"]
            stock[p["object_id"]] -= p["quantity"]
            quantities[(p["actor_id"], p["object_id"])] += p["quantity"]
        if kind == "ATE":
            quantities[(p["actor_id"], p["object_id"])] -= p["quantity"]
            kcal[p["actor_id"]] += p["calories_kcal"]
        if kind == "WORKED":
            money[p["actor_id"]] += p["income_cents"]
            work[p["actor_id"]] += p["minutes"]
        if kind in ("EPISODE_COMPLETED", "REWATCH_COMPLETED"):
            key = (p["actor_id"], p["object_id"], p["episode"])
            views[key] += 1
            if kind == "EPISODE_COMPLETED":
                completed[key] += 1
        if kind == "MEDIA_PROGRESS":
            key = (p["actor_id"], p["object_id"])
            if p["episode"] is None:
                plays[key] += p["minutes"]
            elif not p["rewatch"]:
                offsets[(*key, p["episode"])] += p["minutes"]
    if clock != state["minute"]:
        errors.append("TIME_LEDGER_MISMATCH")
    for actor in state["actors"]:
        actor_id = actor["actor_id"]
        world._validate_actor(actor)
        if actor["money_cents"] != money[actor_id]:
            errors.append("MONEY_LEDGER_MISMATCH")
        if actor["calories_kcal"] != kcal[actor_id]:
            errors.append("CALORIE_LEDGER_MISMATCH")
        if actor["work_minutes"] != work[actor_id]:
            errors.append("WORK_LEDGER_MISMATCH")
        if actor["location"] != location[actor_id]:
            errors.append("LOCATION_LEDGER_MISMATCH")
    objects = {o["object_id"]: o for o in state["objects"]}
    for obj in objects.values():
        if obj["stock"] != stock[obj["object_id"]]:
            errors.append("STOCK_LEDGER_MISMATCH")
        if obj["available"] != available[obj["object_id"]]:
            errors.append("AVAILABILITY_LEDGER_MISMATCH")
    links = {(r["actor_id"], r["object_id"]): r["state"] for r in state["links"]}
    for key in set(links) | touched:
        link, obj = links.get(key, initial_link()), objects[key[1]]
        if link["quantity"] != quantities[key] or link["quantity"] < 0:
            errors.append("INVENTORY_LEDGER_MISMATCH")
        if link["play_minutes"] != plays[key]:
            errors.append("PLAY_LEDGER_MISMATCH")
        expected_watched = sorted(ep for aid, oid, ep in completed if (aid, oid) == key)
        expected_offsets = {str(ep): value for (aid, oid, ep), value in offsets.items()
                            if (aid, oid) == key}
        expected_views = {str(ep): value for (aid, oid, ep), value in views.items()
                          if (aid, oid) == key}
        if link["watched"] != expected_watched:
            errors.append("COMPLETION_LEDGER_MISMATCH")
        if link["offsets"] != expected_offsets:
            errors.append("MEDIA_OFFSET_LEDGER_MISMATCH")
        if link["view_counts"] != expected_views:
            errors.append("REWATCH_LEDGER_MISMATCH")
        for ep in link["watched"]:
            if completed[(*key, ep)] != 1 or link["offsets"].get(str(ep)) != obj["duration_min"]:
                errors.append("UNBACKED_EPISODE_COMPLETION")
        for ep, offset in link["offsets"].items():
            if not 1 <= int(ep) <= obj["episodes"] or not 0 <= offset <= obj["duration_min"]:
                errors.append("INVALID_MEDIA_OFFSET")
    active = Counter(c["actor_id"] for c in state["commitments"]
                     if c["status"] in ("ACTIVE", "PAUSED"))
    if any(count > 1 for count in active.values()):
        errors.append("OVERLAPPING_ACTIVITIES")
    if any(count > 1 for count in completed.values()):
        errors.append("UNINTENDED_REPEAT_COMPLETION")
    if errors:
        raise AssertionError(sorted(set(errors)))
    return {"invariants": "PASS", "events": len(events), "state_hash": digest(state),
            "minute": world.minute, "human_behavior_validated": False}
