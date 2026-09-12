from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from framework.contracts import read_json
from project.dqt.llm.client_interface import CompletionResponse
from project.worker import BudgetReached, ProviderFailed, RecordedClient


async def test_budget_records_last_response_and_never_calls_again(tmp_path):
    provider = SimpleNamespace(
        chat_completion=AsyncMock(
            return_value=CompletionResponse(content="answer", model="mock", tokens=20)
        )
    )
    client = RecordedClient(provider, {"tokens": 10}, tmp_path)
    with pytest.raises(BudgetReached, match="token_limit"):
        await client.chat_completion(messages=[])
    assert len(read_json(tmp_path / "trace.json")) == 1
    with pytest.raises(BudgetReached):
        await client.chat_completion(messages=[])
    assert provider.chat_completion.await_count == 1


async def test_provider_failure_bypasses_legacy_fallback_and_preserves_trace(tmp_path):
    provider = SimpleNamespace(
        chat_completion=AsyncMock(side_effect=RuntimeError("provider broke"))
    )
    client = RecordedClient(provider, {}, tmp_path)
    with pytest.raises(ProviderFailed):
        await client.chat_completion(messages=[])
    assert provider.chat_completion.await_count == 1
    assert read_json(tmp_path / "trace.json")[0]["type"] == "provider_error"


async def test_unknown_usage_cannot_satisfy_token_budget(tmp_path):
    provider = SimpleNamespace(
        chat_completion=AsyncMock(
            return_value=CompletionResponse(content="answer", model="mock", tokens=0)
        )
    )
    with pytest.raises(ProviderFailed, match="reported provider usage"):
        await RecordedClient(provider, {"tokens": 10}, tmp_path).chat_completion(
            messages=[]
        )
