"""One neutral 18-hour day using the existing single-call closed-loop path."""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from social_sim.closed_loop import ClosedLoopStep
from social_sim.decision import ActionType, CompactDecisionService, DecisionClientError, DecisionParseError, ProviderContractError
from social_sim.decision.client import DecisionModelClient
from social_sim.events import DomainEvent, EventLog, EventType
from social_sim.evaluation.models import (
    StepTrajectory, TerminationReason, effects_snapshots, event_snapshot,
    intent_snapshot, observation_snapshot, proposal_snapshot, world_snapshot,
)
from social_sim.evaluation.recorder import TrajectoryRecorder
from social_sim.world import ObservationBuilder, OfferState, PersonWorldState, WorldState

from .idle import IdleDetector, IdleTick
from .models import DayOutcome, DailyEpisodeResult, DailyTerminationReason, DailyTickRecord
from .persona import NeutralPersona
from .support import BehaviorSupportPolicy, SupportCondition
from .time import DAY_END, DAY_START, TICK_MINUTES, WORK_END, WORK_START, advance_daily_tick
from .trigger import DecisionTrigger
from .trigger_audit import DecisionTriggerAudit
from .validation import validate_daily_trajectory


DAILY_ACTIONS = (
    ActionType.MOVE, ActionType.BUY, ActionType.EAT,
    ActionType.SLEEP, ActionType.WORK, ActionType.LEISURE,
)
DAILY_TARGETS = ("home", "office", "restaurant", "park", "meal")
MAX_DECISIONS_PER_DAY = 30
MAX_IDENTICAL_REJECTIONS = 5
_SAFE_CONTRACT_CATEGORIES = frozenset({
    "PROVIDER_SCHEMA_MISMATCH", "NO_CHOICES", "OUTPUT_BUDGET_EXHAUSTED",
    "PROVIDER_REFUSAL", "TOOL_CALL_INSTEAD_OF_TEXT",
    "EMPTY_FINAL_CONTENT_WITH_REASONING", "EMPTY_FINAL_CONTENT",
})
_SAFE_PROVIDER_MODEL = re.compile(r"[A-Za-z0-9_.:/-]{1,128}\Z")


def _safe_provider_model(value: object, client: DecisionModelClient) -> str | None:
    if not isinstance(value, str) or not _SAFE_PROVIDER_MODEL.fullmatch(value):
        return None
    if "://" in value or re.fullmatch(r"(?:ark|sk)-[A-Za-z0-9-]{12,}", value):
        return None
    secret = getattr(client, "_redaction_secret", None)
    if isinstance(secret, str) and secret and secret in value:
        return None
    return value


def neutral_day_initial_world() -> WorldState:
    """A fresh, identical world for every simulated day."""
    return WorldState(
        time=datetime(2026, 1, 1, 6, 0, tzinfo=timezone.utc),
        people={1: PersonWorldState(1, "home", 100.0, 0.3, energy=0.8)},
        locations=("home", "office", "restaurant", "park"),
        venues={"restaurant": {"meal": OfferState("meal", 20.0, 10)}},
    )


def _core(world: WorldState, *, coarse_needs: bool = False) -> tuple[object, ...]:
    """Exclude clock drift; coarse needs distinguish meaningful from tiny drift."""
    person = world.get_person(1)
    hunger = round(person.hunger, 1) if coarse_needs else person.hunger
    energy = round(person.energy, 1) if coarse_needs and person.energy is not None else person.energy
    return (
        person.location, person.activity, person.money,
        tuple(sorted(person.inventory.items())), hunger, energy,
    )


def _remaining_minutes(world: WorldState) -> int:
    person = world.get_person(1)
    if person.activity_end_time is None:
        return 0
    remaining = datetime.fromisoformat(person.activity_end_time) - world.time
    return max(0, int(remaining.total_seconds() // 60))


def _taxonomy(
    *, idle: dict[str, object], valid_activity_count: int,
    activity_metrics: dict[str, object], unique_activity_types: int,
    termination: DailyTerminationReason, simulated_minutes: int,
) -> tuple[str, ...]:
    flags: list[str] = []
    # Partial infrastructure windows are not a behavioral sample. In
    # particular, a timeout before the first completed tick is never idle.
    if termination in (DailyTerminationReason.PROVIDER_ERROR, DailyTerminationReason.TIMEOUT):
        return ("PROVIDER_FAILURE",)
    if termination is DailyTerminationReason.INVALID_MODEL_OUTPUT:
        return ("MODEL_OUTPUT_FAILURE",)
    if termination is DailyTerminationReason.ARCHITECTURE_ERROR:
        return ("ARCHITECTURE_FAILURE",)
    if simulated_minutes and (valid_activity_count == 0 or idle["idle_ratio"] >= 0.5):
        flags.append("NO_ACTION")
    if idle["behavior_loop_count"]:
        flags.append("REPETITION")
    if idle["repeated_invalid_count"]:
        flags.append("INVALID_LOOP")
    if idle["unresolved_need_minutes"]:
        flags.append("NEED_NEGLECT")
    if termination is DailyTerminationReason.DAY_END and activity_metrics["work_minutes"] == 0:
        flags.append("OBLIGATION_NEGLECT")
    if simulated_minutes == 18 * 60 and unique_activity_types < 3:
        flags.append("LOW_ACTIVITY_DIVERSITY")
    return tuple(flags)


def _day_outcome(termination: DailyTerminationReason) -> DayOutcome:
    if termination is DailyTerminationReason.DAY_END:
        return DayOutcome.DAY_COMPLETED
    if termination in (DailyTerminationReason.TIMEOUT, DailyTerminationReason.PROVIDER_ERROR):
        return DayOutcome.DAY_TRUNCATED_PROVIDER
    if termination is DailyTerminationReason.INVALID_MODEL_OUTPUT:
        return DayOutcome.DAY_TRUNCATED_MODEL_OUTPUT
    if termination is DailyTerminationReason.ARCHITECTURE_ERROR:
        return DayOutcome.DAY_TRUNCATED_ARCHITECTURE
    return DayOutcome.DAY_TRUNCATED_BEHAVIOR


def _safe_failure(
    error: Exception, client: DecisionModelClient, *,
    simulation_time: datetime, trigger_reason: str, decision_index: int,
    elapsed_seconds: float, metadata_before: object,
) -> dict[str, object]:
    """Capture diagnostic facts only; never stringify the provider exception."""
    current_metadata = getattr(client, "last_metadata", None)
    metadata = getattr(error, "metadata", None) or (
        current_metadata if current_metadata is not metadata_before else None
    )
    http_status = getattr(metadata, "http_status", None)
    if http_status is None and isinstance(error, httpx.HTTPStatusError):
        http_status = error.response.status_code
    if isinstance(error, (httpx.TimeoutException, asyncio.TimeoutError)):
        failure_type = "TIMEOUT"
    elif isinstance(error, ProviderContractError):
        failure_type = (
            "EMPTY_CONTENT" if error.category.startswith("EMPTY_")
            else "INVALID_PROVIDER_ENVELOPE"
        )
    elif isinstance(error, DecisionParseError):
        failure_type = "INVALID_MODEL_OUTPUT"
    elif isinstance(error, httpx.HTTPStatusError) or http_status is not None:
        failure_type = "HTTP_ERROR"
    elif isinstance(error, httpx.HTTPError):
        failure_type = "NETWORK_ERROR"
    else:
        failure_type = "PROVIDER_ERROR"
    return {
        "decision_index": decision_index,
        "simulation_time": simulation_time.isoformat(),
        "trigger_reason": trigger_reason,
        "failure_type": failure_type,
        "provider_contract_category": (
            error.category if isinstance(error, ProviderContractError)
            and error.category in _SAFE_CONTRACT_CATEGORIES else None
        ),
        "http_status": http_status,
        # The elapsed failed attempt is known even when the provider supplies
        # neither a response envelope nor token usage (notably on timeout).
        "latency_seconds": float(elapsed_seconds),
        "provider_model": _safe_provider_model(getattr(metadata, "provider_model", None), client),
        "input_tokens": getattr(metadata, "input_tokens", None),
        "output_tokens": getattr(metadata, "output_tokens", None),
        "reasoning_tokens": getattr(metadata, "reasoning_tokens", None),
    }


class DailyEpisodeRunner:
    """Run one fresh day with <=1 provider request per decision-triggered tick."""

    def __init__(
        self,
        client: DecisionModelClient,
        *,
        output_dir: Path | str = Path("run/evaluation/neutral_day"),
        persona: NeutralPersona | None = None,
        support_policy: BehaviorSupportPolicy | None = None,
        max_decisions_per_day: int = MAX_DECISIONS_PER_DAY,
        model_name: str | None = None,
        write_artifacts: bool = True,
    ) -> None:
        if isinstance(max_decisions_per_day, bool) or not 1 <= max_decisions_per_day <= MAX_DECISIONS_PER_DAY:
            raise ValueError("max_decisions_per_day must be in [1,30]")
        self.client = client
        self.output_dir = Path(output_dir)
        self.persona = persona or NeutralPersona()
        self.support_policy = support_policy or BehaviorSupportPolicy(SupportCondition.B0_NONE)
        self.max_decisions_per_day = max_decisions_per_day
        self.model_name = model_name
        self.write_artifacts = write_artifacts

    async def run_episode(self, number: int) -> DailyEpisodeResult:
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            raise ValueError("episode number must be positive")
        start_episode = getattr(self.client, "start_episode", None)
        if callable(start_episode):
            start_episode()
        episode_id = f"neutral-day-{number:06d}"
        world = neutral_day_initial_world()
        day_end = world.time + timedelta(hours=18)
        event_log = EventLog()
        recorder = TrajectoryRecorder(episode_id, output_dir=self.output_dir, record_prompt=False)
        service = CompactDecisionService(self.client)
        stepper = ClosedLoopStep(service, event_log)
        trigger = DecisionTrigger()
        trigger_audit = DecisionTriggerAudit()
        idle_detector = IdleDetector()
        ticks: list[DailyTickRecord] = []
        activity_counts: Counter[str] = Counter({action.value: 0 for action in DAILY_ACTIONS})
        durations = {"SLEEP": 0, "WORK": 0, "LEISURE": 0}
        meal_count = move_count = location_transitions = active_minutes = state_transitions = 0
        provider_start = getattr(self.client, "provider_request_count", None)
        termination = DailyTerminationReason.DAY_END
        provider_failures: list[dict[str, object]] = []
        last_rejected = False
        last_completed = False

        while world.time < day_end:
            before = world
            before_person = before.get_person(1)
            before_snapshot = world_snapshot(before)
            after_decision = before
            decision_step_index = None
            attempted_action = attempted_target = rejection_reason = None
            action_accepted = None
            activity_started = False
            food_progress = False
            obligation_boundary = before.time.strftime("%H:%M") in (WORK_START, WORK_END)
            reason = trigger.reason(
                before.time, before_person.activity, before_person.activity_end_time,
                rejected=last_rejected,
                activity_completed=last_completed,
                obligation_boundary=obligation_boundary,
                critical_need=before_person.hunger >= 0.8,
            )
            trigger_reason = reason.value if reason is not None else None
            if reason is not None:
                if service.decision_call_count >= self.max_decisions_per_day:
                    termination = DailyTerminationReason.MAX_DECISIONS
                    break
                observation = ObservationBuilder(before).build(1)
                work_due = WORK_START <= before.time.strftime("%H:%M") < WORK_END
                hints = self.support_policy.select_hints(observation, work_due=work_due)
                trigger_audit.record_decision(before.time, before, trigger_reason)
                started = time.perf_counter()
                metadata_before = getattr(self.client, "last_metadata", None)
                try:
                    completed = await stepper.run(
                        before, 1, self.persona.profile(),
                        available_actions=DAILY_ACTIONS,
                        available_targets=DAILY_TARGETS,
                        daily_mode=True,
                        work_window=f"{WORK_START}-{WORK_END}",
                        behavior_hints=hints,
                    )
                except DecisionParseError:
                    termination = DailyTerminationReason.INVALID_MODEL_OUTPUT
                    break
                except ProviderContractError as exc:
                    provider_failures.append(_safe_failure(
                        exc, self.client, simulation_time=before.time,
                        trigger_reason=trigger_reason,
                        decision_index=service.decision_call_count,
                        elapsed_seconds=time.perf_counter() - started,
                        metadata_before=metadata_before,
                    ))
                    termination = DailyTerminationReason.PROVIDER_ERROR
                    break
                except (httpx.TimeoutException, asyncio.TimeoutError) as exc:
                    provider_failures.append(_safe_failure(
                        exc, self.client, simulation_time=before.time,
                        trigger_reason=trigger_reason,
                        decision_index=service.decision_call_count,
                        elapsed_seconds=time.perf_counter() - started,
                        metadata_before=metadata_before,
                    ))
                    termination = DailyTerminationReason.TIMEOUT
                    break
                except (DecisionClientError, httpx.HTTPError) as exc:
                    provider_failures.append(_safe_failure(
                        exc, self.client, simulation_time=before.time,
                        trigger_reason=trigger_reason,
                        decision_index=service.decision_call_count,
                        elapsed_seconds=time.perf_counter() - started,
                        metadata_before=metadata_before,
                    ))
                    termination = DailyTerminationReason.PROVIDER_ERROR
                    break
                except Exception:
                    # A deterministic invariant failed. Keep the partial day
                    # auditable; orchestration must not run another day after it.
                    termination = DailyTerminationReason.ARCHITECTURE_ERROR
                    break
                if completed.context_chars >= 2000 or completed.prompt_chars >= 3000:
                    termination = DailyTerminationReason.ARCHITECTURE_ERROR
                    break
                if len(completed.outcome.events) != 1:
                    termination = DailyTerminationReason.ARCHITECTURE_ERROR
                    break
                after_decision = completed.world_after
                outcome = completed.outcome
                action = completed.proposal.action
                attempted_action = action.value
                attempted_target = completed.proposal.target
                action_accepted = outcome.allowed
                rejection_reason = None if outcome.allowed else outcome.reason_code
                activity_started = outcome.allowed
                food_progress = outcome.allowed and (
                    action in (ActionType.BUY, ActionType.EAT)
                    or (action is ActionType.MOVE and attempted_target == "restaurant")
                )
                decision_step_index = len(recorder.steps) + 1
                recorder.append_step(StepTrajectory(
                    episode_id=episode_id,
                    step_index=decision_step_index,
                    state_before=before_snapshot,
                    observation=observation_snapshot(completed.observation_before),
                    context=completed.context,
                    proposal=proposal_snapshot(completed.proposal),
                    intent=intent_snapshot(completed.intent),
                    rule_allowed=outcome.allowed,
                    rule_reason_code=outcome.reason_code,
                    effects=effects_snapshots(outcome.effects),
                    event=event_snapshot(outcome.events[0]),
                    state_after=world_snapshot(after_decision),
                    decision_call_count=1,
                    provider_request_count=completed.provider_request_count,
                    context_chars=completed.context_chars,
                    prompt_chars=completed.prompt_chars,
                    decision_latency_seconds=completed.decision_latency_seconds,
                    input_tokens=completed.input_tokens,
                    output_tokens=completed.output_tokens,
                    reasoning_tokens=completed.reasoning_tokens,
                    visible_content_chars=completed.raw_output_chars,
                    provider_model=completed.provider_model,
                    simulation_time=before.time.isoformat(),
                    active_activity=before_person.activity,
                    activity_remaining_minutes=_remaining_minutes(before),
                    hunger=before_person.hunger,
                    energy=before_person.energy,
                    trigger_reason=trigger_reason,
                ))
                if outcome.allowed:
                    activity_counts[action.value] += 1
                    if action is ActionType.EAT:
                        meal_count += 1
                    if action is ActionType.MOVE:
                        move_count += 1
                        location_transitions += (
                            before_person.location != after_decision.get_person(1).location
                        )
                    if _core(before) != _core(after_decision):
                        state_transitions += 1

            during_activity = after_decision.get_person(1).activity
            if during_activity in durations:
                durations[during_activity] += TICK_MINUTES
            if during_activity is not None or activity_started:
                active_minutes += TICK_MINUTES
            world, completions = advance_daily_tick(after_decision, TICK_MINUTES)
            completion_events = []
            for actor_id, action in completions:
                completion_event = DomainEvent(
                    event_id=event_log.next_event_id(), actor_id=actor_id,
                    event_type=EventType(f"{action.value}_COMPLETED"),
                    action=action, target=None, success=True, reason_code="ACCEPTED",
                )
                event_log.append(completion_event)
                completion_events.append(event_snapshot(completion_event))
                state_transitions += 1
            tick = DailyTickRecord(
                tick_index=len(ticks) + 1,
                simulation_time=before.time.isoformat(),
                end_time=world.time.isoformat(),
                world_before=before_snapshot,
                world_after_decision=world_snapshot(after_decision),
                world_after=world_snapshot(world),
                decision_step_index=decision_step_index,
                attempted_action=attempted_action,
                attempted_target=attempted_target,
                action_accepted=action_accepted,
                rejection_reason=rejection_reason,
                active_activity=during_activity,
                completed_activities=tuple(action.value for _, action in completions),
                completion_events=tuple(completion_events),
                trigger_reason=trigger_reason,
            )
            ticks.append(tick)
            last_rejected = action_accepted is False
            last_completed = bool(completions)
            person_after = world.get_person(1)
            idle_status = idle_detector.record_tick(IdleTick(
                time_minute=before.time.hour * 60 + before.time.minute,
                activity=during_activity,
                valid_activity_started=activity_started,
                state_before=_core(before, coarse_needs=True),
                state_after=_core(world, coarse_needs=True),
                hunger=person_after.hunger,
                food_progress=food_progress,
                action=attempted_action,
                target=attempted_target,
                rejection_reason=rejection_reason,
                action_accepted=action_accepted,
                goal_progress=food_progress,
                action_state_unchanged=(
                    _core(before) == _core(after_decision)
                    if attempted_action is not None else None
                ),
            ))
            if idle_status.current_repeated_invalid_streak >= MAX_IDENTICAL_REJECTIONS:
                termination = DailyTerminationReason.BEHAVIOR_LOOP
                break

        provider_end = getattr(self.client, "provider_request_count", None)
        provider_requests = (
            provider_end - provider_start
            if isinstance(provider_start, int) and isinstance(provider_end, int)
            else sum(step.provider_request_count for step in recorder.steps)
        )
        phase7_reason = {
            DailyTerminationReason.DAY_END: TerminationReason.DAY_END,
            DailyTerminationReason.PROVIDER_ERROR: TerminationReason.PROVIDER_ERROR,
            DailyTerminationReason.TIMEOUT: TerminationReason.TIMEOUT,
            DailyTerminationReason.INVALID_MODEL_OUTPUT: TerminationReason.INVALID_MODEL_OUTPUT,
            DailyTerminationReason.MAX_DECISIONS: TerminationReason.MAX_DECISIONS,
            DailyTerminationReason.BEHAVIOR_LOOP: TerminationReason.BEHAVIOR_LOOP,
            DailyTerminationReason.ARCHITECTURE_ERROR: TerminationReason.ARCHITECTURE_ERROR,
        }[termination]
        trajectory = recorder.finish_episode(
            success=termination is DailyTerminationReason.DAY_END,
            termination_reason=phase7_reason,
            final_state=world_snapshot(world),
            decision_count=service.decision_call_count,
            invalid_outputs=int(termination is DailyTerminationReason.INVALID_MODEL_OUTPUT),
            provider_errors=int(termination in (DailyTerminationReason.PROVIDER_ERROR, DailyTerminationReason.TIMEOUT)),
            total_provider_requests=provider_requests,
            scenario_name="neutral_day",
            context_policy_name="C3_recent3",
            decision_policy_name=self.support_policy.condition.value,
            model_name=self.model_name,
        )
        idle = idle_detector.summary().to_dict()
        activity_metrics = {
            "sleep_minutes": durations["SLEEP"],
            "work_minutes": durations["WORK"],
            "meal_count": meal_count,
            "leisure_minutes": durations["LEISURE"],
            "move_count": move_count,
            "location_transition_count": location_transitions,
            "active_minutes": active_minutes,
            "state_transition_count": state_transitions,
            "decisions_per_simulated_hour": (
                service.decision_call_count / (15 * len(ticks) / 60) if ticks else 0.0
            ),
            "provider_requests_per_day": provider_requests,
        }
        activity_metrics.update(trigger_audit.summary(
            observed_ticks=len(ticks), active_minutes=active_minutes,
        ))
        unique = sum(count > 0 for count in activity_counts.values())
        observed_minutes = TICK_MINUTES * len(ticks)
        day_completed = termination is DailyTerminationReason.DAY_END and world.time == day_end
        outcome = _day_outcome(termination)
        full_day_behavior_metrics = (
            {
                "idle_ratio": idle["idle_ratio"],
                "idle_minutes": idle["idle_minutes"],
                "max_idle_streak_minutes": idle["max_idle_streak_minutes"],
                "unique_activity_types": unique,
                "repeated_invalid_count": idle["repeated_invalid_count"],
                "unresolved_need_minutes": idle["unresolved_need_minutes"],
                "sleep_minutes": durations["SLEEP"],
                "work_minutes": durations["WORK"],
                "leisure_minutes": durations["LEISURE"],
                "meal_count": meal_count,
                "activity_counts": dict(activity_counts),
            }
            if day_completed else None
        )
        partial_window_metrics = (
            None if day_completed else {
                "observed_minutes": observed_minutes,
                "observed_ticks": len(ticks),
                "partial_idle_minutes": idle["idle_minutes"],
                "partial_idle_ratio": idle["idle_ratio"] if ticks else None,
                "partial_activity_counts": dict(activity_counts),
                "partial_decisions": service.decision_call_count,
            }
        )
        result = DailyEpisodeResult(
            episode_id=episode_id,
            termination_reason=termination,
            trajectory=trajectory,
            ticks=tuple(ticks),
            idle_metrics=idle,
            activity_metrics=activity_metrics,
            failure_taxonomy=_taxonomy(
                idle=idle, valid_activity_count=sum(activity_counts.values()),
                activity_metrics=activity_metrics, unique_activity_types=unique,
                termination=termination, simulated_minutes=observed_minutes,
            ),
            decision_count=service.decision_call_count,
            provider_request_count=provider_requests,
            valid_activity_count=sum(activity_counts.values()),
            unique_activity_types=unique,
            activity_counts=dict(activity_counts),
            simulated_minutes=observed_minutes,
            day_outcome=outcome,
            day_completed=day_completed,
            observed_minutes=observed_minutes,
            observed_ticks=len(ticks),
            truncation_reason=None if day_completed else outcome.value,
            provider_failures=tuple(provider_failures),
            behavior_metrics_valid=day_completed,
            full_day_behavior_metrics=full_day_behavior_metrics,
            partial_window_metrics=partial_window_metrics,
        )
        validate_daily_trajectory(result)
        if self.write_artifacts:
            recorder.write_episode(trajectory)
            daily_dir = self.output_dir / "daily_episodes"
            daily_dir.mkdir(parents=True, exist_ok=True)
            with (daily_dir / f"episode_{number:06d}.json").open("x", encoding="utf-8") as target:
                json.dump(result.to_dict(), target, ensure_ascii=False, indent=2, allow_nan=False)
                target.write("\n")
        return result
