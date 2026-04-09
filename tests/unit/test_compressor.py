"""
单元测试 - Compressor 模块
测试事实提取、事实合并与摘要功能
"""

from types import SimpleNamespace

import pytest

from src.backend.core.schema import Fact
from src.backend.modules.compressor import Compressor


class ContractAwareCompressorLLM:
    def __init__(self, responses):
        self.responses = list(responses)
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
        response = self.responses.pop(0)
        return SimpleNamespace(
            content=response["content"],
            structured_content=response.get("structured_content"),
            tokens=response.get("tokens", 0),
            model=response.get("model", "contract-aware"),
        )

    async def get_usage_stats(self):
        return {}

    async def reset_usage_stats(self):
        return None


class ScriptedCompressorChecker:
    def __init__(self, *, plan=None, error: Exception | None = None):
        self.plan = plan or SimpleNamespace(
            replace_existing={},
            discard_new=[],
            keep_new=[],
        )
        self.error = error
        self.calls: list[dict] = []

    async def dedupe_facts(self, existing_facts, new_facts):
        self.calls.append(
            {
                "existing_facts": existing_facts,
                "new_facts": new_facts,
            }
        )
        if self.error is not None:
            raise self.error
        return self.plan


@pytest.mark.unit
class TestCompressor:
    @pytest.fixture
    def compressor(self, mock_llm_client):
        return Compressor(
            mock_llm_client,
            checker=ScriptedCompressorChecker(),
        )

    async def test_extract_facts_basic(self, compressor):
        text = """
        深度学习是机器学习的一个子领域。
        Transformer 架构于 2017 年提出。
        GPT-4 是目前最先进的语言模型之一。
        """

        facts, tokens, model = await compressor.extract_facts(text, "test_node_123")

        assert isinstance(facts, list)
        assert len(facts) > 0
        assert isinstance(tokens, int)
        assert isinstance(model, str)
        assert all(isinstance(fact, Fact) for fact in facts)

    async def test_extract_facts_empty_text(self, compressor):
        facts, _, _ = await compressor.extract_facts("", "node_1")

        assert isinstance(facts, list)

    def test_compressor_exposes_only_active_api(self, compressor):
        assert hasattr(compressor, "extract_facts")
        assert hasattr(compressor, "merge_facts")
        assert hasattr(compressor, "summarize_interactions")
        assert not hasattr(compressor, "compress_context")

    async def test_merge_facts_with_literal_duplicates_prefers_higher_confidence(self):
        checker = ScriptedCompressorChecker()
        compressor = Compressor(
            ContractAwareCompressorLLM([]),
            checker=checker,
        )
        existing_facts = [
            Fact(
                content="深度学习是机器学习的一个子领域。",
                source_node_id="node_1",
                confidence=0.9,
            )
        ]
        new_facts = [
            Fact(
                content=" 深度学习是机器学习的一个子领域 ",
                source_node_id="node_2",
                confidence=0.95,
            )
        ]

        merged = await compressor.merge_facts(existing_facts, new_facts)

        assert len(merged) == 1
        assert merged[0].source_node_id == "node_2"
        assert checker.calls == []

    async def test_merge_facts_applies_checker_replace_and_discard(self):
        existing_fact = Fact(
            id="existing-1",
            content="旧事实",
            source_node_id="node_1",
            confidence=0.6,
        )
        replacing_fact = Fact(
            id="new-1",
            content="更新后的事实",
            source_node_id="node_2",
            confidence=0.95,
        )
        discarded_fact = Fact(
            id="new-2",
            content="重复事实",
            source_node_id="node_2",
            confidence=0.7,
        )
        kept_fact = Fact(
            id="new-3",
            content="新增事实",
            source_node_id="node_2",
            confidence=0.9,
        )
        checker = ScriptedCompressorChecker(
            plan=SimpleNamespace(
                replace_existing={"new-1": "existing-1"},
                discard_new=["new-2"],
                keep_new=["new-3"],
            )
        )
        compressor = Compressor(
            ContractAwareCompressorLLM([]),
            checker=checker,
        )

        merged = await compressor.merge_facts(
            [existing_fact],
            [replacing_fact, discarded_fact, kept_fact],
        )

        assert {fact.id for fact in merged} == {"new-1", "new-3"}
        assert checker.calls

    async def test_merge_facts_fail_open_keeps_non_literal_new_facts(self):
        checker = ScriptedCompressorChecker(error=RuntimeError("checker unavailable"))
        compressor = Compressor(
            ContractAwareCompressorLLM([]),
            checker=checker,
        )
        existing_facts = [
            Fact(content="测试事实A", source_node_id="node_1", confidence=0.6)
        ]
        new_facts = [
            Fact(content="测试事实B", source_node_id="node_2", confidence=0.95),
            Fact(content="测试事实C", source_node_id="node_2", confidence=0.8),
        ]

        merged = await compressor.merge_facts(existing_facts, new_facts)

        assert {fact.content for fact in merged} == {
            "测试事实A",
            "测试事实B",
            "测试事实C",
        }

    def test_manual_fact_extraction(self, compressor):
        text = """
        深度学习是一种机器学习方法。
        它使用多层神经网络。
        训练需要大量数据。
        我认为这很复杂。
        """

        facts = compressor._extract_facts_manually(text, "node_1")

        assert isinstance(facts, list)
        assert len(facts) > 0
        assert not any("我认为" in fact.content for fact in facts)

    async def test_summarize_interactions(self, compressor):
        from src.backend.core.schema import QAInteraction

        interactions = [
            QAInteraction(
                question="什么是AI？",
                answer="人工智能是计算机科学的一个分支。它专注于创建能够执行需要人类智能的任务的系统。",
                tokens_used=100,
            ),
            QAInteraction(
                question="AI 有哪些应用？",
                answer="AI 应用广泛，包括医疗诊断、自动驾驶、语音识别等领域。",
                tokens_used=80,
            ),
        ]

        summary = compressor.summarize_interactions(interactions, max_facts=10)

        assert isinstance(summary, dict)
        assert summary["total_interactions"] == 2
        assert "total_facts" in summary
        assert "key_facts" in summary

    async def test_extract_facts_uses_generation_purpose_and_json_array_contract(self):
        llm_client = ContractAwareCompressorLLM(
            [
                {
                    "content": '[{"content": "事实1", "confidence": 0.9}]',
                    "structured_content": [{"content": "事实1", "confidence": 0.9}],
                    "tokens": 12,
                    "model": "structured-model",
                }
            ]
        )
        compressor = Compressor(llm_client, checker=ScriptedCompressorChecker())

        facts, tokens, model = await compressor.extract_facts("测试文本", "node_1")

        assert llm_client.calls[0]["response_contract"] == "json_array"
        assert llm_client.calls[0]["purpose"] == "generation"
        assert [fact.content for fact in facts] == ["事实1"]
        assert tokens == 12
        assert model == "structured-model"


@pytest.mark.unit
class TestCompressorEdgeCases:
    @pytest.fixture
    def compressor(self, mock_llm_client):
        return Compressor(
            mock_llm_client,
            checker=ScriptedCompressorChecker(),
        )

    async def test_extract_facts_special_characters(self, compressor):
        facts, _, _ = await compressor.extract_facts(
            "这是包含特殊字符的文本：@#$%^&*()，应该能正常处理。",
            "node_1",
        )

        assert isinstance(facts, list)

    async def test_merge_facts_empty_lists(self, compressor):
        assert await compressor.merge_facts([], []) == []

        existing = [Fact(content="测试", source_node_id="node_1")]
        merged = await compressor.merge_facts(existing, [])
        assert len(merged) == 1
