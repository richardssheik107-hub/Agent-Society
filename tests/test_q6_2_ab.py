"""Q6.2 A/B protocol: no real provider; fake-client and dry-run contracts only."""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from social_sim.continuity.action_projection import (
    FEASIBLE,
    RAW,
    candidate_fingerprint,
    project_actions,
    proposal_in_feasible_set,
    projected_prompt,
)
from social_sim.continuity.benchmark import seed_demo
from social_sim.continuity.context import decision_prompt
from social_sim.continuity.engine import ContinuityWorld
from social_sim.continuity.models import digest
from social_sim.continuity.q6_2_ab import prepare_dry_run, run_ab_session


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_candidate_digest_is_stable_sorted_and_changes_with_ownership():
    with ContinuityWorld(":memory:") as world:
        seed_demo(world)
        one = project_actions(world)
        two = project_actions(world)
        assert one["candidate_count"] == len(one["executable_options"])
        assert one["candidate_digest"] == two["candidate_digest"]
        assert one["candidate_digest"] == candidate_fingerprint(list(reversed(one["executable_options"])))
        assert one["executable_options"] == sorted(
            one["executable_options"], key=lambda p: (p["activity"], p["target"] or ""))
        play = {"activity": "PLAY", "target": "game_a"}
        assert not proposal_in_feasible_set(play, one)
        assert world.act("buy", 1, "BUY", "game_a")["accepted"]
        owned = project_actions(world)
        assert proposal_in_feasible_set(play, owned)
        assert owned["candidate_digest"] != one["candidate_digest"]
        world.set_available("off", "game_a", False)
        assert not proposal_in_feasible_set(play, project_actions(world))


def test_raw_prompt_still_exact_and_b_adds_only_projection():
    with ContinuityWorld(":memory:") as world:
        seed_demo(world)
        assert projected_prompt(world, mode=RAW) == decision_prompt(world, 1)
        raw_sys, raw_user = projected_prompt(world, mode=RAW)
        feasible_sys, feasible_user = projected_prompt(world, mode=FEASIBLE)
        body = json.loads(feasible_user)
        assert body.pop("executable_options") == project_actions(world)["executable_options"]
        assert body == json.loads(raw_user)
        assert feasible_sys.startswith(raw_sys)


def test_dry_run_has_isolated_equal_worlds_and_no_provider_or_secret(tmp_path):
    output = tmp_path / "ab-one"
    comparison = prepare_dry_run(output, session_id="ab-one", schedule="BA")
    assert comparison["provider_requests"] == 0
    assert not comparison["real_ab_executed"]
    assert _json(output / "config.json")["schedule"] == "BA"
    a = _json(output / "arm_a/final_state.json")
    b = _json(output / "arm_b/final_state.json")
    assert digest(a) == digest(b)
    assert (output / "arm_a/world.sqlite3").resolve() != (output / "arm_b/world.sqlite3").resolve()
    for arm in ("arm_a", "arm_b"):
        summary = _json(output / arm / "summary.json")
        assert summary["status"] == "NOT_RUN" and summary["provider_requests"] == 0
        assert (output / arm / "decisions.jsonl").read_text() == ""
    for path in output.rglob("*"):
        if path.is_file() and path.suffix in {".json", ".jsonl", ".md"}:
            data = path.read_text(encoding="utf-8")
            assert "Authorization" not in data
            assert "api_key" not in data.lower()
            assert "raw_text" not in data
            assert "reasoning_content" not in data
    with pytest.raises(FileExistsError):
        prepare_dry_run(output, session_id="ab-one")


def test_worlds_are_independent_after_dry_run(tmp_path):
    output = tmp_path / "separate"
    prepare_dry_run(output, session_id="separate")
    with ContinuityWorld(output / "arm_a/world.sqlite3") as a:
        assert a.act("change-a", 1, "MOVE", "restaurant")["accepted"]
    with ContinuityWorld(output / "arm_b/world.sqlite3") as b:
        assert b.store.actor(1)["location"] == "home"
        assert b.minute == 0


def test_default_cli_needs_no_credentials_and_cannot_rerun_session(tmp_path):
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts/run_q6_2_real_ab.py"
    output = tmp_path / "cli"
    env = {k: v for k, v in os.environ.items() if not k.startswith("CONTINUITY_")}
    args = [sys.executable, str(script), "--session-id", "cli", "--output", str(output)]
    first = subprocess.run(args, env=env, capture_output=True, text=True, timeout=20)
    assert first.returncode == 0, first.stderr
    assert "Q6_2_REAL_AB_EXECUTED=NO" in first.stdout
    assert "PROVIDER_REQUESTS=0" in first.stdout
    second = subprocess.run(args, env=env, capture_output=True, text=True, timeout=20)
    assert second.returncode != 0
    assert "SESSION_ALREADY_EXISTS" in second.stderr


class _IllegalProposalClient:
    def __init__(self):
        self.call_count = 0

    async def complete(self, _system: str, _user: str):
        self.call_count += 1
        return SimpleNamespace(raw_text='{"activity":"PLAY","target":"game_a"}')


def test_rule_rejection_stops_each_arm_without_repair_and_preserves_membership(tmp_path):
    client = _IllegalProposalClient()
    output = tmp_path / "fake"
    comparison = asyncio.run(run_ab_session(output, session_id="fake", client=client))
    assert client.call_count == 2
    assert comparison["provider_requests"] == 2
    assert comparison["both_arms_ran"]
    assert not comparison["real_ab_executed"]
    for arm in ("arm_a", "arm_b"):
        summary = _json(output / arm / "summary.json")
        assert summary["termination_reason"] == "RULE_REJECTED"
        assert summary["metrics"]["rule_rejection_rate"] == 1
        row = json.loads((output / arm / "decisions.jsonl").read_text())
        assert row["proposal_activity"] == "PLAY" and row["proposal_target"] == "game_a"
        assert row["PROPOSAL_IN_FEASIBLE_SET"] is False
        assert row["rule_reason"] == "ITEM_NOT_OWNED"


class _FailingProvider:
    def __init__(self):
        self.call_count = 0

    async def complete(self, _system: str, _user: str):
        self.call_count += 1
        raise RuntimeError("synthetic failure")


def test_provider_failure_stops_whole_session_before_other_arm(tmp_path):
    client = _FailingProvider()
    output = tmp_path / "failure"
    comparison = asyncio.run(run_ab_session(output, session_id="failure", client=client))
    assert client.call_count == 1 and comparison["provider_requests"] == 1
    assert _json(output / "arm_a/summary.json")["termination_reason"] == "PROVIDER_ERROR"
    assert _json(output / "arm_b/summary.json")["status"] == "NOT_RUN"
    assert not comparison["both_arms_ran"]


class _ValidProposalClient:
    def __init__(self):
        self.call_count = 0
        self.modes = []

    async def complete(self, _system: str, user: str):
        self.call_count += 1
        self.modes.append(FEASIBLE if "executable_options" in json.loads(user) else RAW)
        return SimpleNamespace(raw_text='{"activity":"WATCH","target":"series_a"}')


def test_ba_schedule_never_exceeds_eight_calls_and_shares_no_world(tmp_path):
    client = _ValidProposalClient()
    output = tmp_path / "ba"
    comparison = asyncio.run(run_ab_session(output, session_id="ba", client=client, schedule="BA"))
    assert client.call_count == 8
    assert comparison["provider_requests"] == 8
    assert not comparison["real_ab_executed"]
    assert client.modes == [FEASIBLE] * 4 + [RAW] * 4
    for arm in ("arm_a", "arm_b"):
        summary = _json(output / arm / "summary.json")
        assert summary["completed_decisions"] == 4
        assert summary["metrics"]["proposal_in_feasible_set_rate"] == 1
    assert digest(_json(output / "arm_a/final_state.json")) == digest(
        _json(output / "arm_b/final_state.json"))


def test_invalid_session_id_rejected_before_files_created(tmp_path):
    with pytest.raises(ValueError, match="INVALID_SESSION_ID"):
        prepare_dry_run(tmp_path / "bad", session_id="../bad")
    assert not (tmp_path / "bad").exists()
