"""Decision-only provider settings must not borrow unverifiable assumptions."""

import pytest

from social_sim.decision.config import (
    CODING_PLAN,
    CONFIG_MISMATCH_CODING_MODEL_ON_ONLINE_ENDPOINT,
    DECISION_PROVIDER_CONFIG_MISSING,
    ONLINE_INFERENCE,
    OTHER,
    UNKNOWN,
    DecisionConfigError,
    DecisionProviderConfig,
    categorize_base_url,
    load_decision_provider_config,
)


LEGACY = {
    "AGENTSOCIETY_LLM_API_BASE": "https://legacy.example/v1",
    "AGENTSOCIETY_LLM_MODEL": "legacy-model",
    "AGENTSOCIETY_LLM_API_KEY": "legacy-secret",
}
ARK_BASE = "https://ark.cn-beijing.volces.com"


def test_dedicated_values_override_legacy_without_mutating_environment() -> None:
    environment = {
        **LEGACY,
        "DECISION_LLM_API_BASE": f"{ARK_BASE}/api/coding/v3",
        "DECISION_LLM_MODEL": "ark-code-latest",
        "DECISION_LLM_API_KEY": "decision-secret",
    }
    original = environment.copy()

    config = load_decision_provider_config(environment)

    assert environment == original
    assert config.api_base == environment["DECISION_LLM_API_BASE"]
    assert config.model == environment["DECISION_LLM_MODEL"]
    assert config.api_key == environment["DECISION_LLM_API_KEY"]
    assert config.api_base_source == "DECISION_LLM_API_BASE"
    assert config.model_source == "DECISION_LLM_MODEL"
    assert config.api_key_source == "DECISION_LLM_API_KEY"
    assert config.base_url_category == CODING_PLAN
    assert config.credential_category == UNKNOWN


def test_fallback_is_per_field_and_blank_dedicated_values_are_unset() -> None:
    config = DecisionProviderConfig.from_env(
        {
            **LEGACY,
            "DECISION_LLM_API_BASE": "   ",
            "DECISION_LLM_MODEL": "decision-model",
            "DECISION_LLM_API_KEY": "",
        }
    )

    assert config.api_base == LEGACY["AGENTSOCIETY_LLM_API_BASE"]
    assert config.model == "decision-model"
    assert config.api_key == LEGACY["AGENTSOCIETY_LLM_API_KEY"]
    assert config.api_base_source == "AGENTSOCIETY_LLM_API_BASE"
    assert config.model_source == "DECISION_LLM_MODEL"
    assert config.api_key_source == "AGENTSOCIETY_LLM_API_KEY"
    assert config.credential_category == UNKNOWN


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (f"{ARK_BASE}/api/coding/v3", CODING_PLAN),
        (f"{ARK_BASE}/api/coding/v3/", CODING_PLAN),
        (f"{ARK_BASE}/api/v3", ONLINE_INFERENCE),
        (f"{ARK_BASE}/api/v3/", ONLINE_INFERENCE),
        (f"{ARK_BASE}/v1", OTHER),
        (f"{ARK_BASE}/api/v30", OTHER),
        (f"{ARK_BASE}/API/V3", OTHER),
        (f"{ARK_BASE}/api/coding/v3/extra", OTHER),
        (f"{ARK_BASE}/proxy/api/v3", OTHER),
        (f"{ARK_BASE}/api/v3?token=secret", OTHER),
        (f"{ARK_BASE}/api/v3#fragment", OTHER),
        ("http://ark.cn-beijing.volces.com/api/v3", OTHER),
        ("https://ark.cn-beijing.volces.com:443/api/v3", OTHER),
        ("https://user@ark.cn-beijing.volces.com/api/v3", OTHER),
        ("https://ark.example/api/v3", OTHER),
        ("not-a-url/api/v3", OTHER),
        ("https://[invalid/api/v3", OTHER),
    ],
)
def test_base_url_categories(url: str, expected: str) -> None:
    assert categorize_base_url(url) == expected


def test_coding_model_on_online_endpoint_is_rejected_before_client_use() -> None:
    with pytest.raises(DecisionConfigError) as exc_info:
        DecisionProviderConfig.from_env(
            {
                "DECISION_LLM_API_BASE": f"{ARK_BASE}/api/v3",
                "DECISION_LLM_MODEL": "ark-code-latest",
                "DECISION_LLM_API_KEY": "super-secret-key",
            }
        )
    assert exc_info.value.code == CONFIG_MISMATCH_CODING_MODEL_ON_ONLINE_ENDPOINT
    assert str(exc_info.value) == CONFIG_MISMATCH_CODING_MODEL_ON_ONLINE_ENDPOINT
    assert "super-secret-key" not in repr(exc_info.value)


def test_coding_model_on_coding_endpoint_is_valid_but_key_provenance_unknown() -> None:
    config = DecisionProviderConfig.from_env(
        {
            "DECISION_LLM_API_BASE": f"{ARK_BASE}/api/coding/v3",
            "DECISION_LLM_MODEL": "ark-code-latest",
            "DECISION_LLM_API_KEY": "super-secret-key",
        }
    )
    assert config.base_url_category == CODING_PLAN
    assert config.credential_category == UNKNOWN
    assert "super-secret-key" not in repr(config)


def test_legacy_coding_model_mismatch_is_also_rejected() -> None:
    with pytest.raises(DecisionConfigError) as exc_info:
        DecisionProviderConfig.from_env(
            {
                **LEGACY,
                "AGENTSOCIETY_LLM_API_BASE": f"{ARK_BASE}/api/v3",
                "AGENTSOCIETY_LLM_MODEL": "ark-code-latest",
            }
        )
    assert exc_info.value.code == CONFIG_MISMATCH_CODING_MODEL_ON_ONLINE_ENDPOINT


def test_missing_required_settings_fail_without_leaking_values() -> None:
    with pytest.raises(DecisionConfigError) as exc_info:
        DecisionProviderConfig.from_env(
            {
                "DECISION_LLM_API_BASE": f"{ARK_BASE}/api/coding/v3",
                "DECISION_LLM_MODEL": "ark-code-latest",
            }
        )
    assert exc_info.value.code == DECISION_PROVIDER_CONFIG_MISSING
