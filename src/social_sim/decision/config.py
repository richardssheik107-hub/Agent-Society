"""Decision provider configuration independent of AgentSociety's LLM settings.

Each ``DECISION_LLM_*`` value takes precedence over its corresponding
``AGENTSOCIETY_LLM_*`` value. Reading this module never changes the environment
or AgentSociety's configuration. Credential provenance cannot be established
from an environment variable name or from the shape of a secret, so it remains
UNKNOWN even when a dedicated decision key is supplied.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit


CODING_PLAN = "CODING_PLAN"
ONLINE_INFERENCE = "ONLINE_INFERENCE"
OTHER = "OTHER"
UNKNOWN = "UNKNOWN"
CONFIG_MISMATCH_CODING_MODEL_ON_ONLINE_ENDPOINT = (
    "CONFIG_MISMATCH_CODING_MODEL_ON_ONLINE_ENDPOINT"
)
DECISION_PROVIDER_CONFIG_MISSING = "DECISION_PROVIDER_CONFIG_MISSING"


class DecisionConfigError(ValueError):
    """Safe configuration failure identified by a stable, secret-free code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def categorize_base_url(api_base: str) -> str:
    """Classify the endpoint path, without making claims about credentials.

    Only the official Ark HTTPS host and exact API base paths (allowing a
    trailing slash) are classified. Other hosts or URL components are not
    sufficient evidence of an Ark endpoint category.
    """
    try:
        parsed = urlsplit(api_base)
    except ValueError:
        return OTHER
    if (
        parsed.scheme != "https"
        or parsed.netloc.casefold() != "ark.cn-beijing.volces.com"
        or parsed.query
        or parsed.fragment
    ):
        return OTHER
    path = parsed.path.rstrip("/")
    if path == "/api/coding/v3":
        return CODING_PLAN
    if path == "/api/v3":
        return ONLINE_INFERENCE
    return OTHER


def _selected(
    environment: Mapping[str, str], dedicated_name: str, legacy_name: str
) -> tuple[str, str | None]:
    for name in (dedicated_name, legacy_name):
        value = environment.get(name)
        if value is not None and value.strip():
            return value.strip(), name
    return "", None


@dataclass(frozen=True)
class DecisionProviderConfig:
    """Resolved endpoint inputs for ``OpenAICompatibleDecisionClient``.

    ``api_key`` and ``api_base`` are excluded from repr to prevent accidental
    secret or URL-token exposure. The source fields contain variable names,
    never values. Do not serialize this object for diagnostics.
    """

    api_base: str = field(repr=False)
    model: str
    api_key: str = field(repr=False)
    api_base_source: str | None = None
    model_source: str | None = None
    api_key_source: str | None = None
    base_url_category: str = field(init=False)
    credential_category: str = field(init=False, default=UNKNOWN)

    def __post_init__(self) -> None:
        if not self.api_base or not self.model or not self.api_key:
            raise DecisionConfigError(DECISION_PROVIDER_CONFIG_MISSING)

        category = categorize_base_url(self.api_base)
        object.__setattr__(self, "base_url_category", category)
        # No locally available, trustworthy attestation of key provenance.
        object.__setattr__(self, "credential_category", UNKNOWN)
        model_name = self.model.rsplit("/", 1)[-1].casefold()
        if model_name == "ark-code-latest" and category == ONLINE_INFERENCE:
            raise DecisionConfigError(CONFIG_MISMATCH_CODING_MODEL_ON_ONLINE_ENDPOINT)

    @classmethod
    def from_env(
        cls, environment: Mapping[str, str] | None = None
    ) -> DecisionProviderConfig:
        """Resolve dedicated values first, falling back field-by-field.

        Passing a mapping makes configuration deterministic in tests. Omitted
        ``environment`` reads ``os.environ`` without modifying it.
        """
        source = os.environ if environment is None else environment
        api_base, api_base_source = _selected(
            source, "DECISION_LLM_API_BASE", "AGENTSOCIETY_LLM_API_BASE"
        )
        model, model_source = _selected(
            source, "DECISION_LLM_MODEL", "AGENTSOCIETY_LLM_MODEL"
        )
        api_key, api_key_source = _selected(
            source, "DECISION_LLM_API_KEY", "AGENTSOCIETY_LLM_API_KEY"
        )
        return cls(
            api_base=api_base,
            model=model,
            api_key=api_key,
            api_base_source=api_base_source,
            model_source=model_source,
            api_key_source=api_key_source,
        )


def load_decision_provider_config(
    environment: Mapping[str, str] | None = None
) -> DecisionProviderConfig:
    """Convenience entry point for resolving a decision-only provider."""
    return DecisionProviderConfig.from_env(environment)
