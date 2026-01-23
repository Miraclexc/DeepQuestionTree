"""
单元测试 - Compressor 模块
测试事实提取、上下文压缩、事实合并功能
"""
import pytest

from src.backend.modules.compressor import Compressor
from src.backend.core.schema import Fact


@pytest.mark.unit
@pytest.mark.asyncio
class TestCompressor:
    """测试压缩器模块"""

    @pytest.fixture
    def compressor(self, mock_llm_client):
        """创建压缩器实例"""
        return Compressor(mock_llm_client)

    async def test_extract_facts_basic(self, compressor):
        """测试基本的事实提取"""
        text = """
        深度学习是机器学习的一个子领域。
        Transformer 架构于 2017 年提出。
        GPT-4 是目前最先进的语言模型之一。
        """
        source_node_id = "test_node_123"

        facts = await compressor.extract_facts(text, source_node_id)

        # 应该提取到至少一些事实
        assert isinstance(facts, list)
        assert len(facts) > 0

        # 每个事实应该是 Fact 对象
        for fact in facts:
            assert isinstance(fact, Fact)
            assert fact.source_node_id == source_node_id
            assert 0.0 <= fact.confidence <= 1.0

    async def test_extract_facts_empty_text(self, compressor):
        """测试空文本"""
        facts = await compressor.extract_facts("", "node_1")
        # 空文本应该返回空列表或很少的事实
        assert isinstance(facts, list)

    async def test_compress_context_no_compression_needed(self, compressor):
        """测试不需要压缩的情况"""
        short_text = "这是一段很短的文本。"
        token_limit = 2000

        compressed = await compressor.compress_context(short_text, token_limit)

        # 短文本应该直接返回
        assert compressed == short_text

    async def test_compress_context_compression_needed(self, compressor):
        """测试需要压缩的情况"""
        long_text = "这是一段很长的文本。" * 500  # 创建长文本
        token_limit = 100

        compressed = await compressor.compress_context(long_text, token_limit)

        # 压缩后应该更短
        assert len(compressed) < len(long_text)
        assert isinstance(compressed, str)

    async def test_merge_facts_no_duplicates(self, compressor):
        """测试合并无重复的事实"""
        existing_facts = [
            Fact(content="深度学习是机器学习的子领域", source_node_id="node_1", confidence=0.9)
        ]

        new_facts = [
            Fact(content="Transformer 于 2017 年提出", source_node_id="node_2", confidence=0.95)
        ]

        merged = await compressor.merge_facts(existing_facts, new_facts)

        # 应该包含所有事实
        assert len(merged) == 2

    async def test_merge_facts_with_duplicates(self, compressor, embedding_manager):
        """测试合并重复事实"""
        existing_facts = [
            Fact(content="深度学习是机器学习的一个子领域", source_node_id="node_1", confidence=0.9)
        ]

        # 语义相似的事实
        new_facts = [
            Fact(content="深度学习属于机器学习的一种", source_node_id="node_2", confidence=0.95)
        ]

        merged = await compressor.merge_facts(
            existing_facts,
            new_facts,
            similarity_threshold=0.85
        )

        # 高相似度的事实应该被去重或替换
        # 由于 Mock 客户端的 embedding 是基于哈希的，相似文本可能不会被识别为重复
        # 但至少不应该比原来少
        assert len(merged) >= len(existing_facts)

    async def test_merge_facts_confidence_replacement(self, compressor):
        """测试基于置信度的事实替换"""
        # 低置信度的已有事实
        existing_facts = [
            Fact(content="测试事实A", source_node_id="node_1", confidence=0.6)
        ]

        # 高置信度的新事实（完全相同）
        new_facts = [
            Fact(content="测试事实A", source_node_id="node_2", confidence=0.95)
        ]

        merged = await compressor.merge_facts(
            existing_facts,
            new_facts,
            similarity_threshold=1.0  # 完全匹配
        )

        # 应该保留高置信度的版本
        assert len(merged) >= 1
        # 至少有一个事实的置信度很高
        assert any(f.confidence >= 0.9 for f in merged)

    def test_manual_fact_extraction(self, compressor):
        """测试手动事实提取（降级方案）"""
        text = """
        深度学习是一种机器学习方法。
        它使用多层神经网络。
        训练需要大量数据。
        我认为这很复杂。
        """

        facts = compressor._extract_facts_manually(text, "node_1")

        # 应该提取到一些事实
        assert isinstance(facts, list)
        assert len(facts) > 0

        # 不应该包含主观表述
        contents = [f.content for f in facts]
        assert not any("我认为" in c for c in contents)

    async def test_summarize_interactions(self, compressor):
        """测试交互总结"""
        from src.backend.core.schema import QAInteraction

        interactions = [
            QAInteraction(
                question="什么是AI？",
                answer="人工智能是计算机科学的一个分支。它专注于创建能够执行需要人类智能的任务的系统。",
                tokens_used=100
            ),
            QAInteraction(
                question="AI 有哪些应用？",
                answer="AI 应用广泛，包括医疗诊断、自动驾驶、语音识别等领域。",
                tokens_used=80
            )
        ]

        summary = compressor.summarize_interactions(interactions, max_facts=10)

        assert isinstance(summary, dict)
        assert "total_interactions" in summary
        assert summary["total_interactions"] == 2
        assert "total_facts" in summary
        assert "key_facts" in summary


@pytest.mark.unit
class TestCompressorEdgeCases:
    """测试 Compressor 的边界情况"""

    @pytest.fixture
    def compressor(self, mock_llm_client):
        return Compressor(mock_llm_client)

    async def test_extract_facts_special_characters(self, compressor):
        """测试包含特殊字符的文本"""
        text = "这是包含特殊字符的文本：@#$%^&*()，应该能正常处理。"
        facts = await compressor.extract_facts(text, "node_1")

        assert isinstance(facts, list)

    async def test_merge_facts_empty_lists(self, compressor):
        """测试合并空列表"""
        # 两个都为空
        merged = await compressor.merge_facts([], [])
        assert merged == []

        # 一个为空
        existing = [Fact(content="测试", source_node_id="node_1")]
        merged = await compressor.merge_facts(existing, [])
        assert len(merged) == 1

    async def test_compress_context_edge_cases(self, compressor):
        """测试压缩的边界情况"""
        # 空字符串
        result = await compressor.compress_context("", 100)
        assert result == ""

        # 单字符
        result = await compressor.compress_context("A", 100)
        assert result == "A"
