"""Parsing is strict and local: invalid model output gets no repair call."""

import socket

import pytest

from social_sim.decision.models import ActionType, DecisionProposal
from social_sim.decision.parser import DecisionParseError, DecisionParser


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('{"action":"WAIT","target":null}', DecisionProposal(ActionType.WAIT)),
        ('{"action":"REST"}', DecisionProposal(ActionType.REST)),
        (
            '{"action":"MOVE","target":"park"}',
            DecisionProposal(ActionType.MOVE, "park"),
        ),
        ('{"action":"BUY","target":"meal"}', DecisionProposal(ActionType.BUY, "meal")),
        ('{"action":"EAT","target":"meal"}', DecisionProposal(ActionType.EAT, "meal")),
    ],
)
def test_valid_compact_json(raw: str, expected: DecisionProposal) -> None:
    assert DecisionParser().parse(raw) == expected


def test_surrounding_whitespace_is_allowed() -> None:
    assert DecisionParser().parse(' \n {"action":"WAIT"} \t') == DecisionProposal(
        ActionType.WAIT
    )


@pytest.mark.parametrize(
    "raw",
    [
        '```json\n{"action":"REST"}\n```',
        '```\n{"action":"REST"}\n```',
    ],
)
def test_simple_full_code_fence_is_allowed(raw: str) -> None:
    assert DecisionParser().parse(raw) == DecisionProposal(ActionType.REST)


@pytest.mark.parametrize(
    "raw",
    [
        "{not json}",
        '{"action":"WAIT",}',
        'I choose REST: {"action":"REST"}',
        'Here is my decision:\n```json\n{"action":"REST"}\n```',
        '{"action":"REST"} more prose',
        "",
    ],
)
def test_invalid_json_or_long_prose_rejected(raw: str) -> None:
    with pytest.raises(DecisionParseError):
        DecisionParser().parse(raw)


def test_invalid_action_rejected() -> None:
    with pytest.raises(DecisionParseError, match="Unknown action"):
        DecisionParser().parse('{"action":"FLY"}')


def test_move_target_missing_rejected() -> None:
    with pytest.raises(DecisionParseError, match="MOVE requires"):
        DecisionParser().parse('{"action":"MOVE"}')


def test_non_move_target_rejected() -> None:
    with pytest.raises(DecisionParseError, match="target=None"):
        DecisionParser().parse('{"action":"WAIT","target":"park"}')


@pytest.mark.parametrize(
    "raw",
    [
        '{"action":"WAIT","money":999}',
        '{"action":"WAIT","action":"REST"}',
        "[]",
        '{"target":null}',
    ],
)
def test_extra_duplicate_or_missing_fields_rejected(raw: str) -> None:
    with pytest.raises(DecisionParseError):
        DecisionParser().parse(raw)


def test_parser_never_opens_network_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> None:
        raise AssertionError("parser attempted a network call")

    with monkeypatch.context() as patch:
        patch.setattr(socket, "socket", fail_socket)
        assert DecisionParser().parse('{"action":"WAIT"}') == DecisionProposal(
            ActionType.WAIT
        )
