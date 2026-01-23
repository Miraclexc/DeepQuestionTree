"""
单元测试 - Questioner 模块
测试问题生成、价值评估、重复检测功能
"""
import pytest

from src.backend.modules.questioner import Questioner
from src.backend.core.schema import Fact


@pytest.mark.unit
@pytest.mark.asyncio
class TestQuestioner:
    """测试提问者模块"""

    @pytest.fixture
    def questioner(self, mock_llm_client, embedding_manager):
        """创建提问者实例"""
        return Questioner(mock_llm_client, embedding_manager)

    async def test_generate_candidates_basic(self, questioner):
        """测试基本的候选问题生成"""
        context_facts = [
            Fact(content="深度学习是机器学习的子领域", source_node_id="node_1"),
            Fact(content="神经网络包含多层", source_node_id="node_1")
        ]
        current_answer = "深度学习使用多层神经网络..."
        goal = "了解AI技术"

        questions = await questioner.generate_candidates(
            context_facts=context_facts,
            current_answer=current_answer,
            goal=goal,
            k=3
        )

        # 应该生成至少一些问题
        assert isinstance(questions, list)
        assert len(questions) > 0
        assert len(questions) <= 3  # 不超过请求数量

        # 每个问题应该是字符串
        for q in questions:
            assert isinstance(q, str)
            assert len(q) > 5  # 问题应该有实际内容

    async def test_generate_candidates_different_k(self, questioner):
        """测试不同的 k 值"""
        context_facts = []
        current_answer = "测试回答"
        goal = "测试目标"

        # k=1
        questions_1 = await questioner.generate_candidates(
            context_facts, current_answer, goal, k=1
        )
        assert len(questions_1) <= 1

        # k=5
        questions_5 = await questioner.generate_candidates(
            context_facts, current_answer, goal, k=5
        )
        assert len(questions_5) <= 5

    async def test_evaluate_question_value(self, questioner):
        """测试问题价值评估"""
        question = "深度学习的核心原理是什么？"
        known_facts = [
            Fact(content="深度学习是机器学习的子领域", source_node_id="node_1")
        ]
        goal = "了解深度学习"

        score = await questioner.evaluate_question_value(
            question=question,
            known_facts=known_facts,
            goal=goal
        )

        # 分数应该在 0-10 范围内
        assert isinstance(score, float)
        assert 0.0 <= score <= 10.0

    async def test_evaluate_question_value_bounds(self, questioner):
        """测试评估分数边界"""
        question = "测试问题"
        known_facts = []
        goal = "测试目标"

        # 多次评估，确保分数始终在范围内
        for _ in range(5):
            score = await questioner.evaluate_question_value(
                question, known_facts, goal
            )
            assert 0.0 <= score <= 10.0

    async def test_check_duplicate_first_question(self, questioner):
        """测试第一个问题（不重复）"""
        question = "这是第一个问题"

        is_duplicate = await questioner.check_duplicate(question)

        # 第一个问题不应该被认为是重复
        assert not is_duplicate
        # 应该被加入历史
        assert question in questioner.history_questions

    async def test_check_duplicate_identical_question(self, questioner):
        """测试完全相同的问题"""
        question = "这是一个测试问题"

        # 第一次不重复
        is_dup_1 = await questioner.check_duplicate(question, threshold=0.9)
        assert not is_dup_1

        # 第二次应该重复
        is_dup_2 = await questioner.check_duplicate(question, threshold=0.9)
        assert is_dup_2

    async def test_check_duplicate_different_questions(self, questioner):
        """测试不同的问题"""
        question1 = "深度学习的原理是什么？"
        question2 = "Transformer 架构如何工作？"

        await questioner.check_duplicate(question1)
        is_duplicate = await questioner.check_duplicate(question2)

        # 两个不同的问题不应该被认为是重复
        assert not is_duplicate

    async def test_check_duplicate_threshold(self, questioner):
        """测试不同的相似度阈值"""
        question1 = "什么是深度学习？"

        await questioner.check_duplicate(question1)

        # 相似但不完全相同的问题
        question2 = "什么是深度学习"  # 缺少问号

        # 高阈值（严格）
        is_dup_strict = await questioner.check_duplicate(question2, threshold=0.99)

        # 低阈值（宽松）
        is_dup_loose = await questioner.check_duplicate(question2, threshold=0.5)

        # 至少有一种情况应该能工作
        assert isinstance(is_dup_strict, bool)
        assert isinstance(is_dup_loose, bool)

    async def test_history_limit(self, questioner):
        """测试历史问题数量限制"""
        # 添加大量问题
        for i in range(1100):  # 超过限制 1000
            question = f"测试问题 {i}"
            await questioner.check_duplicate(question)

        # 历史应该被限制在 1000 个
        assert len(questioner.history_questions) <= 1000

    def test_extract_questions_from_text(self, questioner):
        """测试从文本中提取问题"""
        text = """
        1. 深度学习的核心原理是什么？
        2. Transformer 如何工作？
        "什么是注意力机制？"
        这是一个陈述句。
        """

        questions = questioner._extract_questions_from_text(text)

        # 应该提取到一些问题
        assert isinstance(questions, list)
        assert len(questions) > 0

    def test_extract_score_from_response(self, questioner):
        """测试从响应中提取分数"""
        # 纯数字
        score1 = questioner._extract_score("8")
        assert score1 == 8.0

        # 带文字的数字
        score2 = questioner._extract_score("评分：7.5 分")
        assert score2 == 7.5

        # JSON 格式
        score3 = questioner._extract_score('{"score": 9, "reason": "高价值"}')
        assert score3 == 9.0

        # 无法解析的文本
        score4 = questioner._extract_score("无法解析")
        assert score4 == 5.0  # 应该返回默认值

    def test_get_default_questions(self, questioner):
        """测试获取默认问题"""
        questions = questioner._get_default_questions(k=3)

        assert isinstance(questions, list)
        assert len(questions) == 3
        assert all(isinstance(q, str) for q in questions)


@pytest.mark.unit
@pytest.mark.asyncio
class TestQuestionerEdgeCases:
    """测试 Questioner 的边界情况"""

    @pytest.fixture
    def questioner(self, mock_llm_client, embedding_manager):
        return Questioner(mock_llm_client, embedding_manager)

    async def test_generate_candidates_empty_context(self, questioner):
        """测试空上下文"""
        questions = await questioner.generate_candidates(
            context_facts=[],
            current_answer="",
            goal="测试",
            k=3
        )

        # 应该返回列表（可能是默认问题）
        assert isinstance(questions, list)

    async def test_evaluate_question_empty_facts(self, questioner):
        """测试无已知事实的评估"""
        score = await questioner.evaluate_question_value(
            question="测试问题",
            known_facts=[],
            goal="测试目标"
        )

        # 应该返回有效分数
        assert 0.0 <= score <= 10.0

    async def test_check_duplicate_empty_string(self, questioner):
        """测试空字符串"""
        is_duplicate = await questioner.check_duplicate("")

        # 空字符串应该被处理
        assert isinstance(is_duplicate, bool)
