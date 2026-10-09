"""D-09: strict engineering facts, separate descriptive metrics, human L3."""
from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy

from social_sim.continuity.models import TIMED_ACTIVITIES, digest
from social_sim.continuity.validation import validate_world

from .behavior_audit import behavior_warnings
from .config import WarningThresholds


class InvariantViolation(AssertionError):
    """Confirmed ledger/state inconsistency must stop the runtime."""


def check_invariants_full(world, initial_state=None) -> dict:
    """Reuse the existing ledger validator, then check needs and commitments.

    Unlike behavior warnings these checks only concern deterministic rules and
    committed transactions; no preference or human-likeness score is inferred.
    """
    try:
        with world.store.read_snapshot():
            base = validate_world(world)
            state, events = world.store.snapshot(), world.store.events()
            genesis = events[0]["payload"]["initial"]
            needs = {a["actor_id"]: {k: a[k] for k in ("hunger_milli", "energy_milli")}
                     for a in genesis["actors"]}
            active, starts, elapsed, terminal = {}, {}, Counter(), Counter()
            commands = {r["id"]: json.loads(r["result"]) for r in
                        world.store.db.execute("SELECT id,result FROM commands")}
            failures = []
            for event in events:
                kind, p = event["kind"], event["payload"]
                command = commands.get(event["command_id"])
                if kind != "WORLD_CREATED":
                    if command is None:
                        failures.append("EVENT_WITHOUT_COMMITTED_COMMAND")
                    elif command.get("accepted") is False and kind != "ACTION_REJECTED":
                        failures.append("REJECTED_COMMAND_HAS_PARTIAL_EFFECTS")
                if kind == "COMMITMENT_STARTED":
                    if p["id"] in starts or p["actor_id"] in active:
                        failures.append("DUPLICATE_OR_OVERLAPPING_COMMITMENT_START")
                    starts[p["id"]] = p
                    active[p["actor_id"]] = p["id"]
                elif kind in {"COMMITMENT_PAUSED", "COMMITMENT_CANCELLED", "COMMITMENT_COMPLETED", "COMMITMENT_FAILED"}:
                    cid = p["id"]
                    aid = starts.get(cid, {}).get("actor_id")
                    if cid not in starts:
                        failures.append("COMMITMENT_TRANSITION_WITHOUT_START")
                    active.pop(aid, None)
                    if kind != "COMMITMENT_PAUSED":
                        terminal[cid] += 1
                elif kind == "COMMITMENT_ACTIVE":
                    if p["id"] not in starts:
                        failures.append("COMMITMENT_RESUME_WITHOUT_START")
                    else:
                        active[starts[p["id"]]["actor_id"]] = p["id"]
                elif kind == "TIME_ADVANCED":
                    dt = p["to_minute"] - p["from_minute"]
                    for aid, need in needs.items():
                        cid = active.get(aid)
                        sleeping = cid is not None and starts[cid]["activity"] == "SLEEP"
                        need["hunger_milli"] = min(1000, need["hunger_milli"] + dt * world.parameters.hunger_per_minute)
                        rate = (world.parameters.sleep_energy_gain_per_minute if sleeping
                                else -world.parameters.awake_energy_cost_per_minute)
                        need["energy_milli"] = max(0, min(1000, need["energy_milli"] + dt * rate))
                        if cid:
                            elapsed[cid] += dt
                elif kind == "ATE":
                    aid = p["actor_id"]
                    expected = max(0, needs[aid]["hunger_milli"] - world.store.object(p["object_id"])["satiety_milli"])
                    if p["hunger_before"] != needs[aid]["hunger_milli"] or p["hunger_after"] != expected:
                        failures.append("HUNGER_EVENT_RULE_MISMATCH")
                    needs[aid]["hunger_milli"] = expected
            for actor in state["actors"]:
                if any(actor[k] != needs[actor["actor_id"]][k] for k in needs[actor["actor_id"]]):
                    failures.append("NEEDS_LEDGER_MISMATCH")
            for commitment in state["commitments"]:
                cid, activity = commitment["id"], commitment["activity"]
                if cid not in starts or commitment["elapsed_min"] != elapsed[cid]:
                    failures.append("COMMITMENT_PROGRESS_LEDGER_MISMATCH")
                if terminal[cid] > 1:
                    failures.append("DUPLICATE_TERMINAL_COMMITMENT_EVENT")
                if commitment["status"] == "ACTIVE" and active.get(commitment["actor_id"]) != cid:
                    failures.append("ACTIVE_COMMITMENT_LEDGER_MISMATCH")
                if cid in starts:
                    for key in ("actor_id", "activity", "target", "episode", "rewatch", "started_minute", "destination"):
                        if commitment.get(key) != starts[cid].get(key):
                            failures.append("COMMITMENT_IDENTITY_FACT_CHANGED")
                    _check_duration(commitment, _total_duration(starts[cid],
                        {o["object_id"]: o for o in state["objects"]}, world.parameters), world.parameters)
                if commitment["status"] == "COMPLETED":
                    expected = TIMED_ACTIVITIES.get(activity)
                    if activity == "TRAVEL":
                        expected = world.parameters.travel_minutes
                    elif activity in {"MEAL", "PLAY", "WATCH"}:
                        obj = world.store.object(commitment["target"])
                        expected = obj["duration_min"]
                        if activity == "MEAL" and starts[cid].get("destination"):
                            expected += world.parameters.travel_minutes
                        if activity == "WATCH" and not commitment["rewatch"]:
                            expected = starts[cid]["remaining_min"]
                    elif activity == "ACQUIRE":
                        expected = world.parameters.travel_minutes if starts[cid].get("destination") else 0
                    if elapsed[cid] != expected or terminal[cid] != 1:
                        failures.append("UNBACKED_COMMITMENT_COMPLETION")
            if world.store.db.execute("PRAGMA foreign_key_check").fetchone():
                failures.append("SQLITE_FOREIGN_KEY_VIOLATION")
            if world.store.db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                failures.append("SQLITE_INTEGRITY_FAILED")
            if initial_state and state["minute"] < initial_state["minute"]:
                failures.append("RESTORED_TIME_REGRESSION")
            if failures:
                raise InvariantViolation(sorted(set(failures)))
            # Also use the exact incremental event checks from genesis, so the
            # restart/full path is no weaker than any later microstep path.
            genesis_cache = {"state": genesis, "seq": events[0]["seq"], "active": {},
                             "last_full_minute": genesis["minute"]}
            _incremental_invariants(world, genesis_cache, initial_state)
            return {**base, "L1": "PASS", "ENGINEERING_CONSISTENCY": "PASS",
                    "needs_rule_ledger": "PASS", "commitment_rule_ledger": "PASS",
                    "HUMAN_BEHAVIOR_APPROPRIATENESS": "UNRESOLVED"}
    except (AssertionError, KeyError, ValueError, TypeError) as error:
        if isinstance(error, InvariantViolation):
            raise
        raise InvariantViolation("WORLD_FACT_INVARIANT_FAILED") from error


def compact_fact_state(world) -> dict:
    """Current actor/object/link facts and active commitments; no historical list."""
    store = world.store
    return {"minute": world.minute, "rules": json.loads(store.meta("rule_parameters")),
            "actors": [store.actor(aid) for aid in store.actor_ids()],
            "objects": [store.object(r[0]) for r in store.db.execute("SELECT id FROM objects ORDER BY id")],
            "links": [{"actor_id": r[0], "object_id": r[1], "state": json.loads(r[2])}
                      for r in store.db.execute("SELECT * FROM links ORDER BY actor_id,object_id")],
            "commitments": [json.loads(r[0]) for r in store.db.execute(
                "SELECT data FROM commitments WHERE status IN ('ACTIVE','PAUSED') ORDER BY id")]}


def _total_duration(c, objects, parameters):
    activity = c["activity"]
    if activity in TIMED_ACTIVITIES:
        return TIMED_ACTIVITIES[activity]
    if activity in {"TRAVEL", "ACQUIRE"}:
        return parameters.travel_minutes if c.get("destination") else 0
    if activity == "MEAL":
        return objects[c["target"]]["duration_min"] + (parameters.travel_minutes if c.get("destination") else 0)
    return c["elapsed_min"] + c["remaining_min"]


def _check_duration(c, total, parameters):
    allowed = {"MEAL": {"MOVE", "BUY", "EAT"}, "ACQUIRE": {"MOVE", "BUY"},
               "TRAVEL": {"MOVE"}, "WATCH": {"WATCH"}, "PLAY": {"PLAY"}}
    phase, elapsed, remaining = c["phase"], c["elapsed_min"], c["remaining_min"]
    valid = phase in allowed.get(c["activity"], {c["activity"]})
    valid = valid and type(elapsed) is int and type(remaining) is int and elapsed >= 0 and remaining >= 0
    if phase == "MOVE":
        valid = valid and bool(c.get("destination")) and elapsed + remaining == parameters.travel_minutes
    elif phase == "BUY":
        valid = valid and remaining == 0 and elapsed == (parameters.travel_minutes if c.get("destination") else 0)
    else:
        valid = valid and elapsed + remaining == total
    if c["status"] == "COMPLETED":
        valid = valid and remaining == 0 and elapsed == total
    if not valid:
        raise InvariantViolation("COMMITMENT_DURATION_OR_PHASE_FACT_MISMATCH")


def _make_cache(world, state):
    objects = {o["object_id"]: o for o in state["objects"]}
    return {"state": state, "seq": world.store.db.execute("SELECT coalesce(max(seq),0) FROM events").fetchone()[0],
            "active": {c["actor_id"]: {**c, "_total": _total_duration(c, objects, world.parameters)}
                       for c in state["commitments"]}, "last_full_minute": world.minute}


def _incremental_invariants(world, cache, initial_state=None):
    """Validate new ledger facts against last verified state, without old history.

    This is a validator, not a controller: it never submits actions or updates
    world rows. Terminal rows are cross-checked immediately, then discarded.
    Daily/final full audits independently reconstruct the whole historical ledger.
    """
    from social_sim.continuity.models import initial_link

    previous = cache["state"]
    actors = {a["actor_id"]: dict(a) for a in previous["actors"]}
    objects = {o["object_id"]: dict(o) for o in previous["objects"]}
    links = {(r["actor_id"], r["object_id"]): deepcopy(r["state"]) for r in previous["links"]}
    active = deepcopy(cache["active"])
    clock = previous["minute"]
    events = world.store.events(cache["seq"])
    owed_work, owed_media = Counter(), Counter()
    parameters = world.parameters

    def require(flag, code):
        if not flag:
            raise InvariantViolation(code)

    def link(aid, oid):
        return links.setdefault((aid, oid), initial_link())

    for event in events:
        p, kind = event["payload"], event["kind"]
        row = world.store.db.execute("SELECT result FROM commands WHERE id=?", (event["command_id"],)).fetchone()
        require(row is not None, "EVENT_WITHOUT_COMMITTED_COMMAND")
        result = json.loads(row[0])
        require(result.get("accepted") is True or kind == "ACTION_REJECTED", "REJECTED_COMMAND_HAS_PARTIAL_EFFECTS")
        if kind != "TIME_ADVANCED":
            require(event["minute"] == clock, "EVENT_TIME_LEDGER_MISMATCH")
        if kind == "COMMITMENT_STARTED":
            aid = p["actor_id"]
            require(aid not in active and p["elapsed_min"] == 0 and p["started_minute"] == clock,
                    "DUPLICATE_OR_INVALID_COMMITMENT_START")
            require(world.store.get_commitment(p["id"])["actor_id"] == aid, "COMMITMENT_ACTOR_MISMATCH")
            active[aid] = {**p, "_total": _total_duration(p, objects, parameters)}
        elif kind == "TIME_ADVANCED":
            require(p["from_minute"] == clock and p["to_minute"] > clock
                    and event["minute"] == p["to_minute"], "TIME_LEDGER_MISMATCH")
            dt = p["to_minute"] - clock
            for aid, actor in actors.items():
                c = active.get(aid)
                running = c is not None and c["status"] == "ACTIVE"
                sleeping = running and c["activity"] == "SLEEP"
                actor["hunger_milli"] = min(1000, actor["hunger_milli"] + dt * parameters.hunger_per_minute)
                rate = parameters.sleep_energy_gain_per_minute if sleeping else -parameters.awake_energy_cost_per_minute
                actor["energy_milli"] = max(0, min(1000, actor["energy_milli"] + dt * rate))
                if running:
                    c["elapsed_min"] += dt
                    require(c["elapsed_min"] <= c["_total"], "COMMITMENT_OVERRAN_DURATION")
                    if c["activity"] == "WORK":
                        owed_work[aid] += dt
                    elif c["activity"] in {"WATCH", "PLAY"}:
                        owed_media[c["id"]] += dt
            clock = p["to_minute"]
        elif kind == "MOVED":
            actors[p["actor_id"]]["location"] = p["destination"]
        elif kind == "AVAILABILITY_CHANGED":
            objects[p["object_id"]]["available"] = p["available"]
        elif kind == "PURCHASED":
            aid, oid = p["actor_id"], p["object_id"]
            actor, obj, owned = actors[aid], objects[oid], link(aid, oid)
            require(p["quantity"] == 1 and p["cost_cents"] == obj["price_cents"]
                    and actor["location"] == obj["seller"] and obj["available"]
                    and obj["stock"] >= 1 and actor["money_cents"] >= p["cost_cents"]
                    and "purchasable" in obj["capabilities"], "PURCHASE_RULE_LEDGER_MISMATCH")
            require("edible" in obj["capabilities"] or owned["quantity"] == 0, "REPEATED_NONCONSUMABLE_PURCHASE")
            actor["money_cents"] -= p["cost_cents"]
            obj["stock"] -= p["quantity"]
            owned["quantity"] += p["quantity"]
        elif kind == "ATE":
            aid, oid = p["actor_id"], p["object_id"]
            actor, obj, owned = actors[aid], objects[oid], link(aid, oid)
            after = max(0, actor["hunger_milli"] - obj["satiety_milli"])
            require(owned["quantity"] >= p["quantity"] and p["quantity"] == 1
                    and "edible" in obj["capabilities"] and p["calories_kcal"] == obj["calories_kcal"]
                    and p["hunger_before"] == actor["hunger_milli"] and p["hunger_after"] == after,
                    "CONSUMPTION_RULE_LEDGER_MISMATCH")
            owned["quantity"] -= p["quantity"]
            actor["hunger_milli"] = after
            actor["calories_kcal"] += p["calories_kcal"]
        elif kind == "WORKED":
            aid, minutes = p["actor_id"], p["minutes"]
            require(minutes > 0 and owed_work[aid] >= minutes
                    and p["income_cents"] == minutes * parameters.work_pay_cents_per_minute,
                    "WORK_RULE_LEDGER_MISMATCH")
            owed_work[aid] -= minutes
            actors[aid]["work_minutes"] += minutes
            actors[aid]["money_cents"] += p["income_cents"]
        elif kind == "MEDIA_PROGRESS":
            aid, oid, minutes = p["actor_id"], p["object_id"], p["minutes"]
            c = active.get(aid)
            require(c is not None and c["id"] == p["id"] and c["target"] == oid
                    and minutes > 0 and owed_media[p["id"]] >= minutes,
                    "MEDIA_RULE_LEDGER_MISMATCH")
            owed_media[p["id"]] -= minutes
            owned = link(aid, oid)
            if p["episode"] is None:
                require(c["activity"] == "PLAY" and owned["quantity"] > 0, "UNOWNED_PLAY_PROGRESS")
                owned["play_minutes"] += minutes
            else:
                require(c["activity"] == "WATCH" and c["episode"] == p["episode"]
                        and c["rewatch"] == p["rewatch"], "WATCH_PROGRESS_ARGUMENT_MISMATCH")
                if not p["rewatch"]:
                    key = str(p["episode"])
                    owned["offsets"][key] = owned["offsets"].get(key, 0) + minutes
                    require(owned["offsets"][key] <= objects[oid]["duration_min"], "MEDIA_OFFSET_OVERFLOW")
        elif kind in {"EPISODE_COMPLETED", "REWATCH_COMPLETED"}:
            aid, oid, ep = p["actor_id"], p["object_id"], p["episode"]
            c, owned = active.get(aid), link(aid, oid)
            require(c is not None and c["activity"] == "WATCH" and c["target"] == oid
                    and c["episode"] == ep and c["elapsed_min"] == c["_total"]
                    and owned["offsets"].get(str(ep)) == objects[oid]["duration_min"],
                    "UNBACKED_EPISODE_COMPLETION")
            require((ep in owned["watched"]) == (kind == "REWATCH_COMPLETED"), "DUPLICATE_EPISODE_COMPLETION")
            owned["watched"] = sorted(set([*owned["watched"], ep]))
            key = str(ep)
            owned["view_counts"][key] = owned["view_counts"].get(key, 0) + 1
        elif kind.startswith("COMMITMENT_"):
            cid = p["id"]
            aid = next((a for a, c in active.items() if c["id"] == cid), None)
            require(aid is not None, "COMMITMENT_TRANSITION_WITHOUT_ACTIVE_FACT")
            c = active[aid]
            statuses = {"COMMITMENT_PAUSED": "PAUSED", "COMMITMENT_ACTIVE": "ACTIVE",
                        "COMMITMENT_CANCELLED": "CANCELLED", "COMMITMENT_FAILED": "FAILED",
                        "COMMITMENT_COMPLETED": "COMPLETED"}
            require(kind in statuses, "UNKNOWN_COMMITMENT_EVENT")
            status = statuses[kind]
            if status == "COMPLETED":
                require(c["elapsed_min"] == c["_total"], "UNBACKED_COMMITMENT_COMPLETION")
            if status in {"ACTIVE", "PAUSED"}:
                require(c["status"] != status, "INVALID_COMMITMENT_CONTROL_TRANSITION")
                c["status"] = status
            else:
                persisted = world.store.get_commitment(cid)
                require(persisted["status"] == status and persisted["elapsed_min"] == c["elapsed_min"],
                        "COMMITMENT_PROGRESS_LEDGER_MISMATCH")
                active.pop(aid)
        elif kind == "WORLD_CREATED":
            require(False, "DUPLICATE_WORLD_GENESIS")
    require(not any(owed_work.values()) and not any(owed_media.values()), "MISSING_COMMITTED_PROGRESS_EVENTS")
    current = compact_fact_state(world)
    require(current["minute"] == clock, "TIME_LEDGER_MISMATCH")
    require(current["rules"] == previous["rules"], "RULE_PARAMETERS_CHANGED")
    for actor in current["actors"]:
        world._validate_actor(actor)
        expected = actors.get(actor["actor_id"])
        require(expected is not None and actor["version"] >= expected["version"], "ACTOR_ID_OR_VERSION_REGRESSION")
        require({k: v for k, v in actor.items() if k != "version"}
                == {k: v for k, v in expected.items() if k != "version"}, "ACTOR_FACT_LEDGER_MISMATCH")
    require(len(current["actors"]) == len(actors), "UNLEDGERED_ACTOR_CHANGE")
    require(current["objects"] == [objects[k] for k in sorted(objects)], "OBJECT_FACT_LEDGER_MISMATCH")
    observed_links = {(r["actor_id"], r["object_id"]): r["state"] for r in current["links"]}
    require(observed_links == links, "OWNERSHIP_OR_MEDIA_LEDGER_MISMATCH")
    observed_active = {c["actor_id"]: c for c in current["commitments"]}
    require(set(observed_active) == set(active), "ACTIVE_COMMITMENT_LEDGER_MISMATCH")
    for aid, c in observed_active.items():
        require(all(c[k] == active[aid][k] for k in
                    ("id", "activity", "target", "episode", "rewatch", "status", "elapsed_min", "started_minute")),
                "COMMITMENT_PROGRESS_LEDGER_MISMATCH")
        require(c["remaining_min"] >= 0 and c["elapsed_min"] <= active[aid]["_total"], "INVALID_COMMITMENT_DURATION")
        _check_duration(c, active[aid]["_total"], parameters)
        # The next batch uses the actual validated phase/duration from storage;
        # it does not attempt to execute or synthesize a controller transition.
        active[aid] = {**c, "_total": active[aid]["_total"]}
    require(not initial_state or clock >= initial_state["minute"], "RESTORED_TIME_REGRESSION")
    require(world.store.db.execute("PRAGMA foreign_key_check").fetchone() is None, "SQLITE_FOREIGN_KEY_VIOLATION")
    cache.update(state=current, active=active, seq=events[-1]["seq"] if events else cache["seq"])
    return {"invariants": "PASS", "L1": "PASS", "ENGINEERING_CONSISTENCY": "PASS",
            "events": cache["seq"], "minute": clock, "state_hash": digest(current),
            "state_hash_scope": "CURRENT_FACTS_AND_ACTIVE_COMMITMENTS",
            "validation_mode": "INCREMENTAL_NEW_COMMITTED_EVENTS_WITH_DAILY_FULL_AUDIT",
            "needs_rule_ledger": "PASS", "commitment_rule_ledger": "PASS",
            "HUMAN_BEHAVIOR_APPROPRIATENESS": "UNRESOLVED"}


def check_invariants(world, initial_state=None) -> dict:
    """Full on open/day boundary; bounded current-fact replay on every microstep."""
    cache = getattr(world, "_m5_invariant_cache", None)
    try:
        with world.store.read_snapshot():
            if cache is None:
                result = check_invariants_full(world, initial_state)
                world._m5_invariant_cache = _make_cache(world, compact_fact_state(world))
                return result
            result = _incremental_invariants(world, cache, initial_state)
            if world.minute // 1440 > cache["last_full_minute"] // 1440:
                result = check_invariants_full(world, initial_state)
                cache["last_full_minute"] = world.minute
            return result
    except (KeyError, ValueError, TypeError, AssertionError) as error:
        if isinstance(error, InvariantViolation):
            raise
        raise InvariantViolation("INCREMENTAL_WORLD_FACT_INVARIANT_FAILED") from error


audit_world = check_invariants


def split_interval(start: int, end: int):
    """Yield exact [start,end) overlaps with simulation-day boundaries."""
    if end < start:
        raise InvariantViolation("REPORT_TIME_REVERSAL")
    while start < end:
        day = start // 1440 + 1
        boundary = min(end, day * 1440)
        yield day, start, boundary
        start = boundary


def _actor(state, actor_id=1):
    if not isinstance(state, dict):
        return None
    if "actors" in state:
        return next((a for a in state["actors"] if a["actor_id"] == actor_id), None)
    return state.get("actor", state)


def activities_from_facts(data: dict) -> list[dict]:
    """Committed world commitments are authoritative, including partial work."""
    terminal_minutes = {}
    for event in data.get("events", []):
        if event["kind"] in {"COMMITMENT_COMPLETED", "COMMITMENT_FAILED", "COMMITMENT_CANCELLED"}:
            terminal_minutes[event["payload"]["id"]] = event["minute"]
    return [{**c, "end_minute": terminal_minutes.get(c["id"]),
             "source": "COMMITTED_WORLD_COMMITMENT_AND_EVENT_LEDGER"}
            for c in sorted(data.get("world", {}).get("commitments", []),
                            key=lambda c: (c["started_minute"], c["id"]))]


def observed_requests(data):
    """Attach committed activity outcomes, rather than just start-command state."""
    last_steps = {}
    for step in data.get("steps", []):
        if step.get("status", "COMMITTED") == "COMMITTED" and step.get("after_state"):
            last_steps[step.get("commitment_id")] = step
    requests = []
    for original in data.get("requests", []):
        row = dict(original)
        step = last_steps.get(row.get("request_id"))
        if step:
            row["after_state"] = step["after_state"]
            row["outcome_minute"] = step.get("actual_to_minute", step["to_minute"])
        requests.append(row)
    return requests


def evaluate(data: dict, warning_config: WarningThresholds | None = None) -> dict:
    """L2 dimensions have separate units and never become a combined score."""
    world, events = data["world"], data.get("events", [])
    genesis = next((e["payload"]["initial"] for e in events if e["kind"] == "WORLD_CREATED"), None)
    if genesis is None:
        raise InvariantViolation("EVALUATION_MISSING_GENESIS")
    steps, requests = data.get("steps", []), observed_requests(data)
    first, final = _actor(genesis), _actor(world)
    durations = Counter()
    for step in steps:
        if step.get("status", "COMMITTED") != "COMMITTED":
            continue
        dt = step.get("actual_to_minute", step["to_minute"]) - step["from_minute"]
        if dt < 0:
            raise InvariantViolation("EVALUATION_NEGATIVE_STEP")
        durations[step.get("phase") or step.get("activity") or "UNKNOWN"] += dt
    purchases, consumption = Counter(), Counter()
    income, spending, work_minutes, meals = 0, 0, 0, 0
    for event in events:
        p = event["payload"]
        if event["kind"] == "PURCHASED":
            spending += p["cost_cents"]
            purchases[p["object_id"]] += p["quantity"]
        elif event["kind"] == "ATE":
            meals += 1
            consumption[p["object_id"]] += p["quantity"]
        elif event["kind"] == "WORKED":
            income += p["income_cents"]
            work_minutes += p["minutes"]
    commitments = activities_from_facts(data)
    statuses = Counter(c["status"] for c in commitments)
    exercised = {c["activity"] for c in commitments if c["status"] == "COMPLETED"}
    coverage = {a: "EXERCISED" if a in exercised else "NOT_EXERCISED" for a in
                ("WORK", "MEAL", "SLEEP", "TRAVEL", "LEISURE", "ACQUIRE", "PLAY", "WATCH")}
    bought = {e["payload"]["object_id"]: e["minute"] for e in events
              if e["kind"] == "PURCHASED"}
    acquire_to_play = any(c["activity"] == "PLAY" and c["elapsed_min"] > 0
                          and c["target"] in bought and c["started_minute"] >= bought[c["target"]]
                          for c in commitments)
    warnings = behavior_warnings(requests, steps, warning_config)
    invariants = data.get("session", {}).get("invariants", {})
    if not isinstance(invariants, dict):
        invariants = {}
    if not invariants:
        evidence = [r["invariants"] for r in [*requests, *steps]
                    if isinstance(r.get("invariants"), dict)]
        compact = {**world, "commitments": [c for c in world["commitments"]
                                           if c["status"] in {"ACTIVE", "PAUSED"}]}
        if (evidence and all(r.get("invariants") == "PASS" for r in evidence)
                and any(r.get("state_hash") == digest(world) or (
                    r.get("state_hash_scope") == "CURRENT_FACTS_AND_ACTIVE_COMMITMENTS"
                    and r.get("state_hash") == digest(compact)) for r in evidence)):
            invariants = {"invariants": "PASS"}
    failed = (data.get("session", {}).get("stop_reason") == "INVARIANT_FAILED"
              or any(invariants.get(k) == "FAIL" for k in ("invariants", "L1", "ENGINEERING_CONSISTENCY")))
    engineering = "FAIL" if failed else (
        "PASS" if invariants.get("invariants") == "PASS" or invariants.get("L1") == "PASS" else "UNVERIFIED")
    return {
        "schema": "M5_MULTIDIMENSIONAL_EVALUATION_V1",
        "L1": {"status": engineering, "meaning": "DETERMINISTIC_FACTS_NOT_BEHAVIORAL_SUCCESS"},
        "L2": {"evidence_status": "UNTRUSTED_ENGINEERING_FAILURE" if failed else "OBSERVED_COMMITTED_FACTS",
               "hunger": {"initial": first["hunger_milli"], "final": final["hunger_milli"],
                           "net_change": final["hunger_milli"] - first["hunger_milli"]},
               "energy": {"initial": first["energy_milli"], "final": final["energy_milli"],
                           "net_change": final["energy_milli"] - first["energy_milli"]},
               "money": {"initial_cents": first["money_cents"], "final_cents": final["money_cents"],
                         "net_change_cents": final["money_cents"] - first["money_cents"],
                         "work_income_cents": income, "purchase_spending_cents": spending},
               "simulation_minutes": world["minute"] - genesis["minute"],
               "activity_phase_minutes": dict(sorted(durations.items())),
               "work_minutes": work_minutes, "meal_events": meals,
               "purchased_quantities": dict(purchases), "consumed_quantities": dict(consumption),
               "ownership_and_media": world["links"], "activity_status_counts": dict(statuses),
               "rule_rejections": sum(e["kind"] == "ACTION_REJECTED" for e in events),
               "goal_progress": {"source": "EXPLICIT_EXPERIMENT_CONFIGURATION",
                                 "goals": data.get("manifest", {}).get("config", {}).get("goals", []),
                                 "observed_coverage": coverage, "acquire_to_play": acquire_to_play},
               "aggregate_score": None},
        "L3": {"status": "UNRESOLVED", "human_review": "未审核", "reasons": [],
               "dissenting_views": [], "human_likeness_proven": False},
        "warnings": warnings, "ENGINEERING_CONSISTENCY": engineering,
        "TASK_CONTINUITY": "EXERCISED" if all(v == "EXERCISED" for v in coverage.values()) else "PARTIAL_COVERAGE",
        "BEHAVIOR_APPROPRIATENESS": "UNRESOLVED", "HUMAN_BEHAVIOR_APPROPRIATENESS": "UNRESOLVED",
    }


def daily_metrics(data: dict, warning_config: WarningThresholds | None = None) -> list[dict]:
    """Exact time slices and event dates; missing midnight state remains null."""
    world, events = data["world"], data.get("events", [])
    genesis = data.get("window_initial_state") or next(
        e["payload"]["initial"] for e in events if e["kind"] == "WORLD_CREATED")
    start, end = genesis["minute"], world["minute"]
    max_day = max(1, (max(start + 1, end) - 1) // 1440 + 1)
    daily = {day: {"day": day, "from_minute": max(start, (day - 1) * 1440),
                   "to_minute": min(end, day * 1440), "activity_phase_minutes": Counter(),
                   "work_minutes": 0, "work_income_cents": 0, "purchase_spending_cents": 0,
                   "meal_events": 0, "purchased_quantities": Counter(), "consumed_quantities": Counter(),
                   "activities_started": 0, "activities_completed": 0,
                   "initial_state": None, "final_state": None, "state_checkpoints": []}
             for day in range(start // 1440 + 1, max_day + 1)}
    for step in data.get("steps", []):
        if step.get("status", "COMMITTED") != "COMMITTED":
            continue
        for day, a, b in split_interval(step["from_minute"], step.get("actual_to_minute", step["to_minute"])):
            daily[day]["activity_phase_minutes"][step.get("phase") or step.get("activity") or "UNKNOWN"] += b - a
    for event in events:
        p, kind = event["payload"], event["kind"]
        if kind == "WORKED":
            for day, a, b in split_interval(event["minute"] - p["minutes"], event["minute"]):
                if day not in daily:
                    continue
                daily[day]["work_minutes"] += b - a
                # Existing rules pay an integer rate; validate exact divisibility.
                if p["income_cents"] % p["minutes"]:
                    raise InvariantViolation("WORK_INCOME_CANNOT_BE_EXACTLY_DAILY_ALLOCATED")
                daily[day]["work_income_cents"] += (b - a) * (p["income_cents"] // p["minutes"])
        day = event["minute"] // 1440 + 1
        # A zero-duration event at the exact horizon belongs to the new day;
        # retain it rather than silently moving it to the previous day.
        if day not in daily and kind in {"PURCHASED", "ATE", "COMMITMENT_STARTED", "COMMITMENT_COMPLETED"}:
            daily[day] = {"day": day, "from_minute": event["minute"], "to_minute": event["minute"],
                          "activity_phase_minutes": Counter(), "work_minutes": 0, "work_income_cents": 0,
                          "purchase_spending_cents": 0, "meal_events": 0, "purchased_quantities": Counter(),
                          "consumed_quantities": Counter(), "activities_started": 0, "activities_completed": 0,
                          "initial_state": None, "final_state": None, "state_checkpoints": []}
        if day not in daily:
            continue
        row = daily[day]
        if kind == "PURCHASED":
            row["purchase_spending_cents"] += p["cost_cents"]
            row["purchased_quantities"][p["object_id"]] += p["quantity"]
        elif kind == "ATE":
            row["meal_events"] += 1
            row["consumed_quantities"][p["object_id"]] += p["quantity"]
        elif kind == "COMMITMENT_STARTED":
            row["activities_started"] += 1
        elif kind == "COMMITMENT_COMPLETED":
            row["activities_completed"] += 1
    states = {start: genesis, end: world}
    checkpoints = list(data.get("checkpoints", []))
    for step in data.get("steps", []):
        if step.get("status", "COMMITTED") != "COMMITTED":
            continue
        for label, minute_key in (("before_state", "from_minute"), ("after_state", "to_minute")):
            if step.get(label):
                states[step[minute_key]] = step[label]
    for checkpoint in checkpoints:
        state = checkpoint.get("state", checkpoint.get("snapshot"))
        minute = checkpoint.get("minute", checkpoint.get("simulation_minute"))
        if state and minute is not None:
            states[minute] = state
            for row in daily.values():
                if row["from_minute"] <= minute <= row["to_minute"]:
                    row["state_checkpoints"].append({"minute": minute, "state": state,
                                                     "kind": checkpoint.get("kind")})
    states[start], states[end] = genesis, world
    requests = data.get("requests", [])
    for row in daily.values():
        row["initial_state"], row["final_state"] = states.get(row["from_minute"]), states.get(row["to_minute"])
        row["state_boundary_policy"] = "EXACT_OBSERVED_MINUTE_ONLY_NO_FABRICATED_MIDNIGHT"
        row["simulation_minutes"] = row["to_minute"] - row["from_minute"]
        for key in ("activity_phase_minutes", "purchased_quantities", "consumed_quantities"):
            row[key] = dict(sorted(row[key].items()))
        row["human_behavior_appropriateness"] = "UNRESOLVED"
        a, b = _actor(row["initial_state"]), _actor(row["final_state"])
        row["need_and_resource_changes"] = {
            field: {"initial": a.get(field) if a else None, "final": b.get(field) if b else None,
                    "net_change": b[field] - a[field] if a and b else None}
            for field in ("hunger_milli", "energy_milli", "money_cents")}
        day_requests = [r for r in requests if r.get("minute", -1) // 1440 + 1 == row["day"]]
        row["decisions"] = len(day_requests)
        row["proposal_activity_counts"] = dict(Counter((r.get("proposal") or {}).get("activity", "UNKNOWN")
                                                       for r in day_requests))
        row["request_status_counts"] = dict(Counter(r.get("status", "UNKNOWN") for r in day_requests))
        day_steps = [s for s in data.get("steps", [])
                     if row["from_minute"] <= s.get("from_minute", -1) < row["to_minute"]]
        day_observed = observed_requests({"requests": day_requests, "steps": day_steps})
        row["warnings"] = behavior_warnings(day_observed, day_steps, warning_config)
        row["warning_scope"] = "OBSERVED_WITHIN_THIS_DAY_NO_FUTURE_ACTIVITY_OUTCOMES"
        row["costs"] = {}
        for field in ("input_tokens", "output_tokens", "reasoning_tokens", "latency_seconds", "provider_requests"):
            values = [r.get(field) for r in day_requests]
            known = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0]
            row["costs"][field] = {"known_subtotal": sum(known) if known else None,
                                   "known_rows": len(known), "missing_rows": len(values) - len(known),
                                   "eligible_rows": len(values),
                                   "missing_rate": (len(values) - len(known)) / len(values) if values else None}
        row["goal_configuration"] = {
            "mode": data.get("manifest", {}).get("config", {}).get("goal_mode"),
            "source": "EXPLICIT_EXPERIMENT_CONFIGURATION",
            "goals": data.get("manifest", {}).get("config", {}).get("goals", []),
        }
    return [daily[day] for day in sorted(daily)]


def semantic_state_and_ledger(data: dict) -> dict:
    """Resume comparison ignores session IDs/command names/run cost only.

    Different behavior inputs are still visible in commitments and event order;
    unequal outputs from different policies must not be called a system defect.
    """
    world = data["world"]
    clean = {k: v for k, v in world.items() if k != "commitments"}
    commitments = [{k: v for k, v in c.items() if k != "id"} for c in world["commitments"]]
    clean["commitments"] = sorted(commitments, key=lambda c: (c["started_minute"], canonical_sort(c)))
    ledger = [{"minute": e["minute"], "kind": e["kind"],
               "payload": {k: v for k, v in e["payload"].items() if k != "id"}}
              for e in data.get("events", [])]
    return {"state": clean, "ledger": ledger, "comparison_scope": "SAME_DETERMINISTIC_BEHAVIOR_INPUTS"}


def canonical_sort(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def compare_semantic_runs(left: dict, right: dict) -> dict:
    a, b = semantic_state_and_ledger(left), semantic_state_and_ledger(right)
    return {"equivalent": a == b, "left_hash": digest(a), "right_hash": digest(b),
            "comparison_scope": "SAME_DETERMINISTIC_BEHAVIOR_INPUTS",
            "different_policy_output_is_not_automatically_a_system_error": True}
