from pathlib import Path

import pytest

from tests.e2e.support import (
    E2EConfigError,
    build_backend_environment,
    resolve_provider_profile,
)


@pytest.mark.unit
def test_resolve_openai_compatible_provider_from_environment():
    profile = resolve_provider_profile(
        environ={
            "E2E_PROVIDER": "openai-compatible",
            "E2E_API_TOKEN": "token-123",
            "E2E_TIMEOUT_SECONDS": "75",
            "E2E_MAX_SIMULATIONS": "4",
            "E2E_OPENAI_COMPATIBLE_API_KEY": "sk-openai-compatible",
            "E2E_OPENAI_COMPATIBLE_BASE_URL": "https://example.com/v1",
            "E2E_OPENAI_COMPATIBLE_GENERATION_MODEL": "provider-gen",
            "E2E_OPENAI_COMPATIBLE_DECISION_MODEL": "provider-decide",
        }
    )

    assert profile.provider == "openai-compatible"
    assert profile.api_token == "token-123"
    assert profile.timeout_seconds == 75
    assert profile.max_simulations == 4
    assert profile.api_key == "sk-openai-compatible"
    assert profile.base_url == "https://example.com/v1"
    assert profile.generation_model == "provider-gen"
    assert profile.decision_model == "provider-decide"


@pytest.mark.unit
def test_deepseek_profile_uses_default_values():
    profile = resolve_provider_profile(
        provider="deepseek",
        environ={
            "E2E_DEEPSEEK_API_KEY": "sk-deepseek",
        },
    )

    assert profile.provider == "deepseek"
    assert profile.api_key == "sk-deepseek"
    assert profile.base_url == "https://api.deepseek.com/v1"
    assert profile.generation_model == "deepseek-chat"
    assert profile.decision_model == "deepseek-chat"
    assert profile.api_token == "test-token"
    assert profile.timeout_seconds == 180
    assert profile.max_simulations == 2


@pytest.mark.unit
def test_invalid_provider_is_rejected():
    with pytest.raises(E2EConfigError, match="Unsupported E2E provider"):
        resolve_provider_profile(
            provider="anthropic",
            environ={},
        )


@pytest.mark.unit
def test_missing_required_api_key_raises_clear_error():
    with pytest.raises(E2EConfigError, match="E2E_DEEPSEEK_API_KEY"):
        resolve_provider_profile(
            provider="deepseek",
            environ={},
        )


@pytest.mark.unit
def test_build_backend_environment_does_not_inject_embedding_overrides():
    profile = resolve_provider_profile(
        provider="deepseek",
        environ={
            "E2E_DEEPSEEK_API_KEY": "sk-deepseek",
        },
    )

    env = build_backend_environment(
        profile=profile,
        port=8123,
        data_dir=Path("D:/tmp/dqt-e2e"),
    )

    assert "EMBEDDING__USE_LOCAL" not in env
    assert "EMBEDDING__LOCAL_FILES_ONLY" not in env
    assert "EMBEDDING__FALLBACK_MODE" not in env
