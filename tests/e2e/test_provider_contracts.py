from __future__ import annotations

import pytest

from src.backend.config_loader import reload_settings
from src.backend.llm.llm_client import OpenAICompatibleClient


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_real_provider_structured_contracts(e2e_provider_profile, monkeypatch):
    monkeypatch.setenv("LLM__API_KEY", e2e_provider_profile.api_key)
    monkeypatch.setenv("LLM__BASE_URL", e2e_provider_profile.base_url)
    monkeypatch.setenv(
        "LLM__GENERATION_MODEL",
        e2e_provider_profile.generation_model,
    )
    monkeypatch.setenv(
        "LLM__DECISION_MODEL",
        e2e_provider_profile.decision_model,
    )
    reload_settings()

    try:
        client = OpenAICompatibleClient()

        object_response = await client.chat_completion(
            messages=[
                {
                    "role": "user",
                    "content": "请严格返回一个 JSON 对象，包含 status 和 provider 两个键。",
                }
            ],
            temperature=0.0,
            response_contract="json_object",
        )
        assert isinstance(object_response.structured_content, dict)
        assert object_response.structured_content

        array_response = await client.chat_completion(
            messages=[
                {
                    "role": "user",
                    "content": "请严格返回一个 JSON 字符串数组，包含两个简短的中文短语，不要附加解释。",
                }
            ],
            temperature=0.0,
            response_contract="json_array",
        )
        assert isinstance(array_response.structured_content, list)
        assert array_response.structured_content
    finally:
        reload_settings()
