from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.backend.llm.client_interface import StructuredOutputContractError
from src.backend.llm.llm_client import OpenAICompatibleClient
from src.backend.llm.mock_client import MockClient


def _build_chat_response(content: str, tokens: int = 32):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(total_tokens=tokens),
    )


def _build_openai_client(fake_create):
    client = object.__new__(OpenAICompatibleClient)
    client.client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=fake_create,
            )
        )
    )
    client.generation_model = "generation-model"
    client.decision_model = "decision-model"
    client.total_tokens_used = 0
    client.total_cost = 0.0
    client.request_count = 0
    return client


@pytest.mark.unit
@pytest.mark.asyncio
async def test_openai_client_uses_json_object_contract_and_parses_payload():
    calls: list[dict] = []

    async def fake_create(**kwargs):
        calls.append(kwargs)
        return _build_chat_response('{"score": 7, "reason": "ok"}')

    client = _build_openai_client(fake_create)

    response = await client.chat_completion(
        messages=[{"role": "user", "content": "请返回一个对象"}],
        temperature=0.2,
        response_contract="json_object",
        purpose="decision",
    )

    assert calls[0]["model"] == "decision-model"
    assert calls[0]["response_format"] == {"type": "json_object"}
    assert response.structured_content == {"score": 7, "reason": "ok"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_openai_client_uses_json_array_contract_without_response_format():
    calls: list[dict] = []

    async def fake_create(**kwargs):
        calls.append(kwargs)
        return _build_chat_response('["问题1", "问题2"]')

    client = _build_openai_client(fake_create)

    response = await client.chat_completion(
        messages=[{"role": "user", "content": "请返回一个数组"}],
        temperature=0.8,
        response_contract="json_array",
        purpose="generation",
    )

    assert calls[0]["model"] == "generation-model"
    assert calls[0]["response_format"] is None
    assert response.structured_content == ["问题1", "问题2"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_openai_client_raises_when_json_array_contract_returns_object():
    async def fake_create(**kwargs):
        return _build_chat_response('{"items": ["问题1"]}')

    client = _build_openai_client(fake_create)

    with pytest.raises(StructuredOutputContractError):
        await client.chat_completion(
            messages=[{"role": "user", "content": "请返回一个数组"}],
            response_contract="json_array",
            purpose="generation",
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mock_client_returns_structured_payload_for_json_array_contract():
    client = MockClient()

    response = await client.chat_completion(
        messages=[{"role": "user", "content": "请提出 3 个候选问题"}],
        response_contract="json_array",
    )

    assert isinstance(response.structured_content, list)
    assert response.structured_content


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mock_client_returns_structured_payload_for_json_object_contract():
    client = MockClient()

    response = await client.chat_completion(
        messages=[{"role": "user", "content": "请评估 score"}],
        response_contract="json_object",
    )

    assert isinstance(response.structured_content, dict)
    assert "score" in response.structured_content


@pytest.mark.unit
@pytest.mark.asyncio
async def test_openai_client_emits_trace_logs_when_debug_logging_enabled(monkeypatch):
    trace_logger = Mock()
    trace_logger.log_request.return_value = "trace-1"

    async def fake_create(**kwargs):
        return _build_chat_response("debug response", tokens=21)

    monkeypatch.setattr(
        "src.backend.llm.llm_client.get_settings",
        lambda: SimpleNamespace(
            llm=SimpleNamespace(
                api_key="debug-key",
                base_url="https://example.test/v1",
                timeout=30,
                max_retries=0,
                generation_model="generation-model",
                decision_model="decision-model",
            ),
            logging=SimpleNamespace(level="DEBUG"),
        ),
    )
    monkeypatch.setattr(
        "src.backend.llm.llm_client.openai.AsyncOpenAI",
        lambda **kwargs: SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=fake_create,
                )
            )
        ),
    )
    monkeypatch.setattr(
        "src.backend.llm.llm_client.get_llm_logger",
        lambda: trace_logger,
    )

    client = OpenAICompatibleClient()
    await client.chat_completion(
        messages=[{"role": "user", "content": "debug trace"}],
        response_contract="text",
        purpose="generation",
    )

    trace_logger.log_request.assert_called_once()
    trace_logger.log_response.assert_called_once()
