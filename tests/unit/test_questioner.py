"""
单元测试 - Questioner 模块
测试问题生成、价值评估与回答功能
"""

from types import SimpleNamespace

import pytest

from src.backend.core.schema import Fact
from src.backend.modules.questioner import Questioner


class ContractAwareQuestionerLLM:
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


class SequenceQuestionerChecker:
    def __init__(self, reviews=None):
        self.reviews = list(reviews or [])
        self.calls: list[dict] = []

    async def review_question(self, **kwargs):
        self.calls.append(kwargs)
        payload = self.reviews.pop(0) if self.reviews else {}
        return SimpleNamespace(
            score=payload.get("score", 5.0),
            is_duplicate=payload.get("is_duplicate", False),
            is_off_topic=payload.get("is_off_topic", False),
            is_low_value=payload.get("is_low_value", False),
            should_prune=payload.get("should_prune", False),
            reason=payload.get("reason"),
            explanation=payload.get("explanation", ""),
        )


@pytest.mark.unit
class TestQuestioner:
    """测试提问者模块当前活跃链路。"""

    @pytest.fixture
    def questioner(self, mock_llm_client):
        return Questioner(
            mock_llm_client,
            checker=SequenceQuestionerChecker(),
        )

    async def test_generate_candidates_basic(self, questioner):
        context_facts = [
            Fact(content="深度学习是机器学习的子领域", source_node_id="node_1"),
            Fact(content="神经网络包含多层", source_node_id="node_1"),
        ]

        questions = await questioner.generate_candidates(
            context_facts=context_facts,
            current_answer="深度学习使用多层神经网络...",
            goal="了解AI技术",
            k=3,
        )

        assert isinstance(questions, list)
        assert len(questions) > 0
        assert len(questions) <= 3
        assert all(
            isinstance(question, str) and len(question) > 5 for question in questions
        )

    async def test_generate_candidates_different_k(self, questioner):
        questions_1 = await questioner.generate_candidates(
            [], "测试回答", "测试目标", k=1
        )
        questions_5 = await questioner.generate_candidates(
            [], "测试回答", "测试目标", k=5
        )

        assert len(questions_1) <= 1
        assert len(questions_5) <= 5

    def test_questioner_exposes_only_active_api(self, questioner):
        assert hasattr(questioner, "generate_candidates")
        assert hasattr(questioner, "evaluate_question_value")
        assert hasattr(questioner, "answer_question")
        assert not hasattr(questioner, "check_duplicate")
        assert not hasattr(questioner, "_extract_questions_from_text")
        assert not hasattr(questioner, "_extract_score")

    def test_get_default_questions(self, questioner):
        questions = questioner._get_default_questions(k=3)

        assert isinstance(questions, list)
        assert len(questions) == 3
        assert all(isinstance(question, str) for question in questions)

    async def test_generate_candidates_uses_generation_purpose_and_json_array_contract(
        self,
    ):
        llm_client = ContractAwareQuestionerLLM(
            [
                {
                    "content": '["问题一是什么？", "问题二是什么？"]',
                    "structured_content": ["问题一是什么？", "问题二是什么？"],
                }
            ]
        )
        questioner = Questioner(llm_client, checker=SequenceQuestionerChecker())

        questions = await questioner.generate_candidates(
            context_facts=[],
            current_answer="当前回答",
            goal="测试目标",
            k=2,
        )

        assert llm_client.calls[0]["response_contract"] == "json_array"
        assert llm_client.calls[0]["purpose"] == "generation"
        assert questions == ["问题一是什么？", "问题二是什么？"]

    async def test_evaluate_question_value_uses_checker_score(self):
        llm_client = ContractAwareQuestionerLLM([])
        checker = SequenceQuestionerChecker(
            [
                {
                    "score": 8.0,
                    "explanation": "这个问题能带来高信息增益。",
                }
            ]
        )
        questioner = Questioner(llm_client, checker=checker)

        score = await questioner.evaluate_question_value(
            question="这个问题有多重要？",
            known_facts=[],
            goal="测试目标",
        )

        assert llm_client.calls == []
        assert checker.calls[0]["stage"] == "score"
        assert score == 8.0

    async def test_answer_question_uses_generation_purpose(self):
        llm_client = ContractAwareQuestionerLLM(
            [
                {
                    "content": "这里是回答",
                    "tokens": 42,
                    "model": "answer-model",
                }
            ]
        )
        questioner = Questioner(llm_client, checker=SequenceQuestionerChecker())

        answer, tokens, model = await questioner.answer_question(
            question="这个问题如何回答？",
            context_facts=[],
            goal="测试目标",
        )

        assert llm_client.calls[0]["response_contract"] == "text"
        assert llm_client.calls[0]["purpose"] == "generation"
        assert answer == "这里是回答"
        assert tokens == 42
        assert model == "answer-model"


@pytest.mark.unit
class TestQuestionerEdgeCases:
    @pytest.fixture
    def questioner(self, mock_llm_client):
        return Questioner(
            mock_llm_client,
            checker=SequenceQuestionerChecker(),
        )

    async def test_generate_candidates_empty_context(self, questioner):
        questions = await questioner.generate_candidates(
            context_facts=[],
            current_answer="",
            goal="测试",
            k=3,
        )

        assert isinstance(questions, list)

    async def test_evaluate_question_empty_facts(self, questioner):
        score = await questioner.evaluate_question_value(
            question="测试问题",
            known_facts=[],
            goal="测试目标",
        )

        assert 0.0 <= score <= 10.0
