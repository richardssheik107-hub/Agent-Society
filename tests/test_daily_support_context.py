"""Neutral-day persona, toy support interface, and bounded daily context."""

import json

import pytest

from social_sim.context import ContextCompiler
from social_sim.daily import (
    NEUTRAL_DAY_GOAL,
    TOY_UNCALIBRATED_PRIORS,
    BehaviorSupportPolicy,
    NeutralPersona,
    SupportCondition,
)
from social_sim.decision import ActionType, CompactDecisionService
from social_sim.decision.client import FakeDecisionClient
from social_sim.world.observation import LocalObservation


def _observation(
    *, hunger: float = 0.3, energy: float = 0.8,
    activity: str | None = None, end: str | None = None,
) -> LocalObservation:
    return LocalObservation(
        agent_id=1,
        time="2026-01-01T10:00:00",
        location="home",
        money=100.0,
        hunger=hunger,
        energy=energy,
        activity=activity,
        activity_end_time=end,
    )


def test_neutral_persona_has_only_short_plain_background() -> None:
    persona = NeutralPersona()
    assert (
        persona.name, persona.role, persona.occupation, persona.personality,
        persona.home, persona.workplace,
    ) == ("Alice", "adult", "office_worker", "neutral", "home", "office")
    assert persona.goal == NEUTRAL_DAY_GOAL
    assert "lunch" not in persona.goal
    assert len(persona.goal) < 80
    assert "extroversion" not in persona.profile()
    assert persona.profile() is not persona.profile()


def test_b0_is_default_and_support_is_bounded_and_toy_labelled() -> None:
    observation = _observation(hunger=0.9, energy=0.1)
    assert BehaviorSupportPolicy().condition is SupportCondition.B0_NONE
    assert BehaviorSupportPolicy().select_hints(observation, work_due=True) == ()

    tiny = BehaviorSupportPolicy(SupportCondition.B1_TINY)
    small = BehaviorSupportPolicy(SupportCondition.B3_SMALL)
    assert tiny.source_label == small.source_label == TOY_UNCALIBRATED_PRIORS
    assert len(tiny.select_hints(observation, work_due=True)) == 1
    assert 0 < len(small.select_hints(observation, work_due=True)) <= 3
    assert tiny.select_hints(observation, work_due=True) == tiny.select_hints(
        observation, work_due=True
    )
    for hint in small.select_hints(observation, work_due=True):
        assert len(hint) <= 96
        assert "09:00" not in hint and "12:00" not in hint
        assert "office" not in hint and "restaurant" not in hint


def test_daily_context_contains_only_short_local_status() -> None:
    context = ContextCompiler(max_chars=2000).compile(
        NeutralPersona().profile(),
        _observation(activity="WORK", end="2026-01-01T11:15:00"),
        available_actions=["MOVE", "BUY", "EAT", "SLEEP", "WORK", "LEISURE"],
        available_targets=["home", "office", "restaurant", "park", "meal"],
        events=[],
        daily_mode=True,
        work_window="09:00-17:00",
        behavior_hints=(),
    )
    data = json.loads(context)
    assert data["p"]["occupation"] == "office_worker"
    assert data["p"]["personality"] == "neutral"
    assert data["p"]["home"] == "home"
    assert data["p"]["workplace"] == "office"
    assert data["s"]["energy"] == 0.8
    assert data["s"]["act"] == "WORK"
    assert data["s"]["rem"] == 75
    assert data["work"] == "09:00-17:00"
    assert "h" not in data
    assert len(context) < 800
    assert "WORK must" not in context and "BUY must" not in context


def test_daily_context_idle_state_and_bounded_toy_hints() -> None:
    hints = BehaviorSupportPolicy(SupportCondition.B3_SMALL).select_hints(
        _observation(hunger=0.85, energy=0.2), work_due=True
    )
    data = json.loads(ContextCompiler().compile(
        NeutralPersona().profile(), _observation(),
        daily_mode=True, work_window="09:00-17:00", behavior_hints=hints,
    ))
    assert data["s"]["act"] is None
    assert data["s"]["rem"] == 0
    assert data["h"] == list(hints)


def test_non_daily_legacy_context_remains_byte_identical() -> None:
    observation = LocalObservation(1, "2026-01-01T10:00:00", "home", 100.0, 0.3)
    compiler = ContextCompiler()
    normal = compiler.compile(NeutralPersona().profile(), observation)
    explicit = compiler.compile(NeutralPersona().profile(), observation, daily_mode=False)
    assert normal == explicit
    assert "energy" not in normal and "occupation" not in normal and "personality" not in normal


def test_daily_input_validation_and_hard_budget() -> None:
    compiler = ContextCompiler(max_chars=2000)
    with pytest.raises(ValueError, match="daily_mode"):
        compiler.compile(NeutralPersona().profile(), _observation(), work_window="09:00-17:00")
    with pytest.raises(ValueError, match="include energy"):
        compiler.compile(
            NeutralPersona().profile(),
            LocalObservation(1, "2026-01-01T10:00:00", "home", 100.0, 0.3),
            daily_mode=True,
        )
    with pytest.raises(ValueError, match="maximum item count"):
        compiler.compile(
            NeutralPersona().profile(), _observation(), daily_mode=True,
            behavior_hints=["hint"] * 4,
        )
    with pytest.raises(ValueError, match="exceeds max_chars"):
        ContextCompiler(max_chars=30).compile(
            NeutralPersona().profile(), _observation(), daily_mode=True,
        )


@pytest.mark.asyncio
async def test_daily_service_forwards_context_and_makes_one_call() -> None:
    client = FakeDecisionClient('{"action":"MOVE","target":"office"}')
    service = CompactDecisionService(client)
    result = await service.decide(
        NeutralPersona().profile(), _observation(),
        available_actions=(ActionType.MOVE, ActionType.WORK, ActionType.SLEEP, ActionType.LEISURE),
        available_targets=("home", "office", "restaurant", "park", "meal"),
        daily_mode=True,
        work_window="09:00-17:00",
        behavior_hints=(),
    )
    assert result.proposal.action is ActionType.MOVE
    assert result.proposal.target == "office"
    assert client.call_count == service.decision_call_count == 1
    assert "SLEEP, WORK, or LEISURE" in result.user_prompt
    assert json.loads(result.context)["s"]["energy"] == 0.8
