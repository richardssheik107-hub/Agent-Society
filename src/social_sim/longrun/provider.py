"""M5 single-request provider adapter and credential-before-authorization gates.

Importing this module neither reads provider configuration nor constructs a client.
Only parsed proposal JSON and allowlisted envelope facts cross into the runtime.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING

from social_sim.provider_runtime.safety import atom, counter, exception_type

if TYPE_CHECKING:
    from social_sim.decision.client import DecisionReply


class AuthorizationError(ValueError):
    """An enum-only refusal; never contains file contents or credential values."""


def _require(condition: bool, category: str) -> None:
    if not condition:
        raise AuthorizationError(category)


def validate_real_authorization(
    *, root: Path, registry: Path, config, session_id: str,
    allow_provider: bool, execution_commit: str | None, protocol_hash: str | None,
    frozen_protocol_hash: str, authorization_path: Path | None, resume: bool = False,
    previous_authorized_budget: int | None = None,
) -> dict:
    """Reject all unapproved requests before any environment or key is loaded.

    A future positive budget requires a separately supplied JSON authorization
    binding this new session, accepted execution commit, and frozen protocol.
    Product decisions D-02/D-09 alone are never a paid-execution authorization.
    The session's own exclusive lock must subsequently be held before key loading.
    """
    _require(config.mode == "real", "REAL_MODE_REQUIRED")
    _require(allow_provider is True, "REAL_PROVIDER_NOT_AUTHORIZED")
    _require(config.max_provider_requests > 0, "ZERO_PROVIDER_BUDGET_NOT_AUTHORIZED")
    _require(bool(re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", session_id)),
             "INVALID_SESSION_ID")
    if resume:
        _require((registry / session_id / "world.sqlite3").is_file(), "RESUME_SESSION_MISSING")
    else:
        _require(not (registry / session_id).exists(), "SESSION_ALREADY_EXISTS")
    _require(bool(execution_commit and re.fullmatch(r"[0-9a-f]{40}", execution_commit)),
             "EXECUTION_COMMIT_REQUIRED")
    _require(protocol_hash == frozen_protocol_hash, "FROZEN_PROTOCOL_HASH_MISMATCH")
    _require(authorization_path is not None, "EXECUTION_AUTHORIZATION_REQUIRED")
    path = Path(authorization_path)
    _require(path.suffix == ".json" and path.resolve().suffix == ".json"
             and path.is_file() and path.stat().st_size <= 65536,
             "EXECUTION_AUTHORIZATION_FILE_INVALID")
    try:
        def unique(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError("DUPLICATE_AUTHORIZATION_KEY")
                result[key] = value
            return result
        authorization = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)
    except (OSError, ValueError, UnicodeError) as error:
        raise AuthorizationError("EXECUTION_AUTHORIZATION_FILE_INVALID") from error
    _require(isinstance(authorization, dict), "EXECUTION_AUTHORIZATION_FILE_INVALID")
    expected = {
        "authorization_type": "EXPLICIT_USER_SESSION_AUTHORIZATION", "approved": True,
        "session_id": session_id, "execution_commit": execution_commit,
        "protocol_hash": frozen_protocol_hash, "resume": resume,
    }
    _require(all(authorization.get(key) == value for key, value in expected.items()),
             "EXECUTION_AUTHORIZATION_MISMATCH")
    _require(authorization.get("approved") is True and authorization.get("resume") is resume,
             "EXECUTION_AUTHORIZATION_MISMATCH")
    # Bool must not be mistaken for an integer budget.
    budget = counter(authorization.get("max_provider_requests"))
    _require(budget is not None and budget > 0 and config.max_provider_requests <= budget,
             "EXECUTION_AUTHORIZATION_BUDGET_MISMATCH")
    if resume:
        _require(previous_authorized_budget is not None and budget == previous_authorized_budget,
                 "RESUME_BUDGET_EXPANSION_FORBIDDEN")
    acceptance = authorization.get("acceptance")
    _require(isinstance(acceptance, dict)
             and acceptance.get("execution_commit") == execution_commit
             and acceptance.get("result") == "PASS", "EXECUTION_COMMIT_NOT_ACCEPTED")
    policy = authorization.get("request_policy")
    _require(isinstance(policy, dict) and policy.get("retry") is False
             and policy.get("fallback") is False, "UNAPPROVED_REQUEST_POLICY")
    from social_sim.provider_runtime.environment import inspect_runtime, repository_info
    repository = repository_info(root)
    _require(repository.get("git_commit") == execution_commit
             and all(repository.get(key) is True for key in
                     ("parent_repository", "worktree_clean", "upstream_matches")),
             "REAL_REPOSITORY_GATE_FAILED")
    _require(inspect_runtime().get("result") == "PASS", "REAL_RUNTIME_GATE_FAILED")
    # Reconstruct, rather than persist arbitrary authorization-file fields.
    return {**expected, "max_provider_requests": budget,
            "acceptance": {"execution_commit": execution_commit, "result": "PASS"},
            "request_policy": {"retry": False, "fallback": False}}


def load_provider_environment(env_file: Path | None = None) -> dict:
    """Use the existing protected configuration loader only after the CLI gates."""
    from social_sim.provider_runtime.environment import load_provider_config
    return load_provider_config(env_file)


class M5ProviderClient:
    """Wrap the existing POST client without retries, repairs, or model fallback.

    Raw final text lives only within this call while the M2 parser runs. The
    returned DecisionReply contains canonical proposal JSON, and hidden reasoning
    or provider error prose never enters safe_evidence or last_metadata.
    """

    mode = "real"

    def __init__(self, provider_config: dict, config, *, transport=None) -> None:
        from social_sim.decision.client import OpenAICompatibleDecisionClient
        self._client = OpenAICompatibleDecisionClient(
            **provider_config, timeout_seconds=config.request_timeout_seconds,
            minimal_request=config.provider_minimal_request,
            max_tokens=config.provider_max_tokens, temperature=config.provider_temperature,
            thinking_disabled=config.provider_thinking_disabled, transport=transport,
        )
        self._secret = provider_config["api_key"]
        self._requested_model = atom(provider_config["model"], self._secret)
        self._timeout = config.request_timeout_seconds
        self.call_count = 0
        self._safe_evidence: dict = {}
        self.last_metadata = None

    @property
    def provider_request_count(self) -> int:
        return self._client.provider_request_count

    @property
    def safe_evidence(self) -> dict:
        return dict(self._safe_evidence)

    def _envelope(self) -> None:
        from social_sim.decision.client import DecisionResponseMetadata
        source = self._client.last_metadata
        status = getattr(source, "http_status", None)
        status = (status if isinstance(status, int) and not isinstance(status, bool)
                  and 100 <= status <= 599 else None)
        values = {name: counter(getattr(source, name, None)) for name in
                  ("input_tokens", "output_tokens", "reasoning_tokens")}
        values.update(http_status=status,
                      provider_model=atom(getattr(source, "provider_model", None), self._secret),
                      finish_reason=atom(getattr(source, "finish_reason", None), self._secret))
        self.last_metadata = DecisionResponseMetadata(**values)
        self._safe_evidence.update(values, http_observable=status is not None,
                                   response_backend=values["provider_model"],
                                   provider_request_count=self.provider_request_count)

    async def complete(self, system_prompt: str, user_prompt: str) -> DecisionReply:
        from social_sim.continuity.m2_acquire import parse_m2_proposal
        from social_sim.decision.client import DecisionReply, ProviderContractError
        self.call_count += 1
        self.last_metadata = None
        self._safe_evidence = {
            "request_alias": self._requested_model, "valid_proposal": None,
            "failure_category": None, "exception_type": None,
            "input_tokens": None, "output_tokens": None, "reasoning_tokens": None,
            "unknown_field_count": None,
        }
        started = time.monotonic()
        try:
            reply = await asyncio.wait_for(
                self._client.complete(system_prompt, user_prompt), timeout=self._timeout)
            self._envelope()
            # The existing envelope permits final text with tool/refusal fields.
            # A decision request must not accept either such alternative channel.
            envelope = self._client.last_metadata
            if (getattr(envelope, "tool_calls_count", 0)
                    or getattr(envelope, "refusal_chars", 0)):
                raise ProviderContractError("NON_DECISION_ENVELOPE", self.last_metadata)
            try:
                proposal = parse_m2_proposal(reply.raw_text)
            except (TypeError, ValueError) as error:
                try:
                    parsed = json.loads(reply.raw_text)
                    if isinstance(parsed, dict):
                        self._safe_evidence["unknown_field_count"] = len(
                            set(parsed).difference({"activity", "target"}))
                except (TypeError, ValueError):
                    pass
                raise ValueError("INVALID_MODEL_OUTPUT") from error
            target = proposal["target"]
            if isinstance(target, str) and self._secret in target:
                raise ValueError("INVALID_MODEL_OUTPUT")
            # Only short catalog-like atoms are retained as proposal evidence.
            # Runtime rule validation separately decides whether the target exists.
            if target is None or atom(target, self._secret) is not None:
                self._safe_evidence["valid_proposal"] = dict(proposal)
            return DecisionReply(
                json.dumps(proposal, ensure_ascii=False, sort_keys=True),
                self.last_metadata.input_tokens, self.last_metadata.output_tokens,
                self.last_metadata.reasoning_tokens, self.last_metadata.provider_model, 1,
            )
        except BaseException as error:
            self._envelope()
            category = getattr(error, "category", None)
            if isinstance(category, str) and re.fullmatch(r"[A-Z0-9_]{1,64}", category):
                self._safe_evidence["failure_category"] = category
            elif isinstance(error, (TypeError, ValueError)):
                self._safe_evidence["failure_category"] = "INVALID_MODEL_OUTPUT"
            elif exception_type(error) in {
                "TimeoutError", "ConnectTimeout", "ReadTimeout", "WriteTimeout", "PoolTimeout",
            }:
                self._safe_evidence["failure_category"] = "PROVIDER_TIMEOUT"
            else:
                self._safe_evidence["failure_category"] = "PROVIDER_ERROR"
            self._safe_evidence["exception_type"] = exception_type(error)
            raise
        finally:
            self._safe_evidence["latency_seconds"] = round(time.monotonic() - started, 6)
            self._client.last_raw_text = None

    async def aclose(self) -> None:
        try:
            await self._client.aclose()
        finally:
            self._client.last_raw_text = None
