"""Read-only behavior warnings; never execute or substitute an activity."""
from __future__ import annotations

from social_sim.continuity.models import digest
from .config import WarningThresholds


def _actor(state):
    if isinstance(state, dict):
        if "actors" in state:
            return next((a for a in state["actors"] if a["actor_id"] == 1), {})
        return state.get("actor", state)
    return {}


def _state_fingerprint(state):
    actor = _actor(state)
    state = state or {}
    return digest({"actor": {k: v for k, v in actor.items() if k != "version"},
                   "links": state.get("links"),
                   "objects": [{k: o.get(k) for k in ("object_id", "stock", "available")}
                               for o in state.get("objects", [])]})


def behavior_warnings(requests, steps, config: WarningThresholds | None = None) -> list[dict]:
    """Observed signals only; synthetic thresholds are not medical standards.

    Every warning is advisory. No world reference or action executor is accepted.
    """
    config = config or WarningThresholds()
    warnings = []
    committed_steps = [s for s in steps if s.get("status", "COMMITTED") == "COMMITTED"
                       and s.get("after_state") is not None]
    by_request = {}
    for step in committed_steps:
        by_request.setdefault(step.get("commitment_id"), []).append(step)

    def actual_minutes(step):
        return max(0, step.get("actual_to_minute", step.get("to_minute", 0)) - step.get("from_minute", 0))

    def state_minute(state):
        value = state.get("minute") if isinstance(state, dict) else None
        return value if type(value) is int else None

    def execution_progress(request):
        before, after = _actor(request.get("before_state")), _actor(request.get("after_state"))
        for field in ("work_minutes", "calories_kcal"):
            a, b = before.get(field), after.get(field)
            if type(a) is int and type(b) is int and b > a:
                return True
        return any(s.get("phase") in {"WORK", "WATCH", "PLAY", "EAT"} and actual_minutes(s) > 0
                   for s in by_request.get(request.get("request_id"), []))

    def observed_work(request):
        before, after = _actor(request.get("before_state")), _actor(request.get("after_state"))
        a, b = before.get("work_minutes"), after.get("work_minutes")
        return (type(a) is int and type(b) is int and b > a) or any(
            s.get("phase") == "WORK" and actual_minutes(s) > 0
            for s in by_request.get(request.get("request_id"), []))

    def emit(code, minute, detail):
        warnings.append({"kind": "BEHAVIOR_WARNING", "code": code, "minute": minute,
                         "detail": detail, "intervention": "NONE",
                         "threshold_source": "SYNTHETIC_ENGINEERING_NOT_MEDICAL_OR_HUMAN_NORM"})

    for field, threshold, code, high in (
        ("hunger_milli", config.hunger_high, "SUSTAINED_HIGH_HUNGER", True),
        ("energy_milli", config.energy_low, "SUSTAINED_LOW_ENERGY", False),
    ):
        duration, emitted, previous_end = 0, False, None
        for step in committed_steps:
            before, after = _actor(step.get("before_state")), _actor(step.get("after_state"))
            dt = actual_minutes(step)
            if previous_end is not None and step.get("from_minute") != previous_end:
                duration, emitted = 0, False
            a, b = before.get(field), after.get(field)
            # Whole intervals are counted only when both measured endpoints meet
            # the threshold; unobserved crossing times are not fabricated.
            extreme = (a is not None and b is not None and
                       (min(a, b) >= threshold if high else max(a, b) <= threshold))
            duration = duration + dt if extreme else 0
            if duration >= config.sustained_minutes and not emitted:
                emit(code, step.get("to_minute"), {"observed_interval_minutes": duration,
                                                  "threshold_milli": threshold})
                emitted = True
            if not extreme:
                emitted = False
            previous_end = step.get("actual_to_minute", step.get("to_minute"))
    failed_key, failed_count, no_progress, unchanged, previous = None, 0, 0, 0, None
    previous_decision_minute = None
    for index, request in enumerate(requests):
        minute = request.get("minute", request.get("from_minute"))
        before, after = request.get("before_state"), request.get("after_state")
        status = request.get("status", request.get("phase"))
        key = (digest(request.get("proposal")), _state_fingerprint(before)) if before else None
        if status in {"RULE_REJECTED", "COMMITMENT_FAILED", "INVALID_MODEL_OUTPUT"} and key:
            failed_count = failed_count + 1 if key == failed_key else 1
            failed_key = key
            if failed_count == config.repeated_failure_count:
                emit("REPEATED_FAILED_PROPOSAL_UNCHANGED_STATE", minute,
                     {"decisions": failed_count, "proposal": request.get("proposal")})
        else:
            failed_key, failed_count = None, 0
        old_min, new_min = state_minute(before), state_minute(after)
        observed_minute = old_min if old_min is not None else minute
        if type(observed_minute) is int:
            # start() changes no clock. Subsequent decision observations and
            # committed execution steps establish whether life actually moved.
            own_progress = (old_min is not None and new_min is not None and new_min > old_min)
            own_progress = own_progress or any(actual_minutes(s) > 0 for s in
                                               by_request.get(request.get("request_id"), []))
            between_progress = previous_decision_minute is not None and observed_minute > previous_decision_minute
            no_progress = 0 if own_progress or between_progress else no_progress + 1
            if no_progress == config.repeated_failure_count:
                emit("CONSECUTIVE_DECISIONS_NO_SIMULATION_PROGRESS", minute,
                     {"decisions": no_progress, "source": "DECISION_OBSERVATION_CLOCK_AND_COMMITTED_STEPS"})
            previous_decision_minute = observed_minute
        else:
            no_progress, previous_decision_minute = 0, None
        if before and after:
            fingerprint = _state_fingerprint(after)
            unchanged = unchanged + 1 if fingerprint == previous else 1
            previous = fingerprint
            if unchanged == config.no_improvement_decisions:
                emit("OBSERVED_STATE_NOT_IMPROVING", minute, {"decisions": unchanged})
        window_size = max(config.no_improvement_decisions, config.frequent_travel_count)
        window = requests[max(0, index + 1 - window_size):index + 1]
        travels = sum((r.get("proposal") or {}).get("activity") == "TRAVEL" for r in window)
        progress = any(execution_progress(r) for r in window)
        if len(window) == window_size and travels >= config.frequent_travel_count and not progress:
            emit("FREQUENT_TRAVEL_WITHOUT_KNOWN_TASK_PROGRESS", minute, {"travel_decisions": travels})
        window = requests[max(0, index + 1 - config.no_improvement_decisions):index + 1]
        balances = [_actor(r.get("after_state")).get("money_cents") for r in window]
        if (len(window) == config.no_improvement_decisions and all(type(v) is int for v in balances)
                and all(b < a for a, b in zip(balances, balances[1:], strict=False))
                and balances[0] - balances[-1] >= config.money_decline_cents
                and not any(observed_work(r) for r in window)):
            emit("DECLINING_MONEY_WITHOUT_OBSERVED_WORK", minute, {"balances_cents": balances})
    return warnings
