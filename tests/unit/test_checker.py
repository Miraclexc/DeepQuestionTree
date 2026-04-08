from types import SimpleNamespace

import pytest

from src.backend.core.schema import Fact
from src.backend.modules.checker import Checker


class RecordingCheckerLLM:
    def __init__(self, responses=None, error: Exception | None = None):
        self.responses = list(responses or [])
        self.error = error
        self.calls: list[dict] = []

    async def chat_completion(
        self,
        messages,
        temperature=0.7,
        max_tokens=None,
        response_contract="text",
        purpose="generation",
    ):
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "response_contract": response_contract,
                "purpose": purpose,
            }
        )
        if self.error is not None:
            raise self.error

        response = self.responses.pop(0)
        return SimpleNamespace(
            content=response.get("content", ""),
            structured_content=response.get("structured_content"),
            tokens=response.get("tokens", 0),
            model=response.get("model", "checker-model"),
        )

    async def get_usage_stats(self):
        return {}

    async def reset_usage_stats(self):
        return None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_review_question_short_circuits_literal_duplicate():
    llm_client = RecordingCheckerLLM()
    checker = Checker(llm_client)

    review = await checker.review_question(
        question="什么是深度学习？",
        goal="理解深度学习",
        history_questions=["什么是深度学习"],
    )

    assert review.is_duplicate is True
    assert review.should_prune is True
    assert review.reason == "问题重复"
    assert llm_client.calls == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_review_question_uses_decision_purpose_and_json_object_contract():
    llm_client = RecordingCheckerLLM(
        responses=[
            {
                "content": '{"score": 8.5, "is_duplicate": false, "is_off_topic": false, "is_low_value": false, "should_prune": false, "reason": null, "explanation": "问题和主题高度相关"}',
                "structured_content": {
                    "score": 8.5,
                    "is_duplicate": False,
                    "is_off_topic": False,
                    "is_low_value": False,
                    "should_prune": False,
                    "reason": None,
                    "explanation": "问题和主题高度相关",
                },
            }
        ]
    )
    checker = Checker(llm_client)

    review = await checker.review_question(
        question="Transformer 的注意力机制如何影响长上下文能力？",
        goal="理解大模型的长上下文能力",
        parent_question="大模型有哪些核心机制？",
        history_questions=["长上下文有哪些限制？"],
        known_facts=[
            Fact(content="Transformer 使用自注意力机制。", source_node_id="node-1")
        ],
        stage="pre",
    )

    assert llm_client.calls[0]["purpose"] == "decision"
    assert llm_client.calls[0]["response_contract"] == "json_object"
    assert review.score == 8.5
    assert review.should_prune is False
    assert review.explanation == "问题和主题高度相关"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_dedupe_facts_uses_decision_purpose_and_returns_plan():
    llm_client = RecordingCheckerLLM(
        responses=[
            {
                "content": '{"replace_existing": {"new-1": "existing-1"}, "discard_new": ["new-2"], "keep_new": ["new-3"]}',
                "structured_content": {
                    "replace_existing": {"new-1": "existing-1"},
                    "discard_new": ["new-2"],
                    "keep_new": ["new-3"],
                },
            }
        ]
    )
    checker = Checker(llm_client)
    existing_facts = [
        Fact(
            id="existing-1",
            content="模型蒸馏可以降低部署成本。",
            source_node_id="node-1",
            confidence=0.6,
        )
    ]
    new_facts = [
        Fact(
            id="new-1",
            content="模型蒸馏通常能显著降低推理成本。",
            source_node_id="node-2",
            confidence=0.9,
        ),
        Fact(
            id="new-2",
            content="推理成本和部署成本相关。",
            source_node_id="node-2",
            confidence=0.7,
        ),
        Fact(
            id="new-3",
            content="蒸馏后的学生模型可能更适合端侧部署。",
            source_node_id="node-2",
            confidence=0.9,
        ),
    ]

    plan = await checker.dedupe_facts(existing_facts, new_facts)

    assert llm_client.calls[0]["purpose"] == "decision"
    assert llm_client.calls[0]["response_contract"] == "json_object"
    assert plan.replace_existing == {"new-1": "existing-1"}
    assert plan.discard_new == ["new-2"]
    assert plan.keep_new == ["new-3"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_dedupe_facts_fail_open_keeps_all_unresolved_facts():
    checker = Checker(RecordingCheckerLLM(error=RuntimeError("checker unavailable")))
    new_facts = [
        Fact(id="new-1", content="事实一", source_node_id="node-1", confidence=0.8),
        Fact(id="new-2", content="事实二", source_node_id="node-1", confidence=0.9),
    ]

    plan = await checker.dedupe_facts([], new_facts)

    assert plan.replace_existing == {}
    assert plan.discard_new == []
    assert sorted(plan.keep_new) == ["new-1", "new-2"]
