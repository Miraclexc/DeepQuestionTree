"""
集成测试 - MCTS 流程
测试完整的 MCTS 迭代流程
"""

from types import SimpleNamespace

import pytest

from src.backend.core.mcts_engine import MCTSEngine
from src.backend.core.schema import Fact, Node, QAInteraction, SessionData
from src.backend.llm.mock_client import MockClient
from src.backend.modules.compressor import Compressor
from src.backend.modules.pruner import Pruner
from src.backend.modules.questioner import Questioner


class SequenceLLM:
    def __init__(self, responses=None):
        self.calls: list[dict] = []
        self.responses = list(responses or [])

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
            tokens=response["tokens"],
            model=response["model"],
        )

    async def get_usage_stats(self):
        return {}

    async def reset_usage_stats(self):
        return None


class SequenceChecker:
    def __init__(self, reviews=None):
        self.reviews = list(reviews or [])
        self.review_calls: list[dict] = []
        self.dedupe_calls: list[dict] = []

    async def review_question(self, **kwargs):
        self.review_calls.append(kwargs)
        payload = self.reviews.pop(0) if self.reviews else {}
        return SimpleNamespace(
            score=payload.get("score", 6.0),
            is_duplicate=payload.get("is_duplicate", False),
            is_off_topic=payload.get("is_off_topic", False),
            is_low_value=payload.get("is_low_value", False),
            should_prune=payload.get("should_prune", False),
            reason=payload.get("reason"),
            explanation=payload.get("explanation", ""),
        )

    async def dedupe_facts(self, existing_facts, new_facts):
        self.dedupe_calls.append(
            {
                "existing_facts": existing_facts,
                "new_facts": new_facts,
            }
        )
        return SimpleNamespace(replace_existing={}, discard_new=[], keep_new=[])


class StaticQuestioner:
    def __init__(self, questions=None, answer="这是回答内容。", tokens=12):
        self.questions = list(questions or [])
        self.answer = answer
        self.tokens = tokens
        self.answer_calls = 0
        self.value_calls = 0

    async def generate_candidates(
        self,
        *,
        context_facts,
        current_answer: str,
        goal: str,
        parent_question: str,
        k: int,
    ):
        del context_facts, current_answer, goal, parent_question, k
        return list(self.questions)

    async def evaluate_question_value(
        self,
        *,
        question: str,
        known_facts,
        goal: str,
        parent_question: str,
    ) -> float:
        del question, known_facts, goal, parent_question
        self.value_calls += 1
        return 8.0

    async def answer_question(
        self,
        *,
        question: str,
        context_facts,
        goal: str,
    ) -> tuple[str, int, str]:
        del question, context_facts, goal
        self.answer_calls += 1
        return self.answer, self.tokens, "answer-model"


class StaticCompressor:
    def __init__(self, extract_tokens=8):
        self.extract_tokens = extract_tokens

    async def extract_facts(
        self,
        text: str,
        source_node_id: str,
    ) -> tuple[list[Fact], int, str]:
        del text
        return (
            [
                Fact(
                    content="提取出的事实",
                    source_node_id=source_node_id,
                    confidence=0.9,
                )
            ],
            self.extract_tokens,
            "fact-model",
        )

    async def merge_facts(
        self,
        existing_facts: list[Fact],
        new_facts: list[Fact],
        similarity_threshold: float = 0.85,
    ) -> list[Fact]:
        del similarity_threshold
        return [*existing_facts, *new_facts]


class SummaryPruner:
    def __init__(self):
        self.summary_calls = 0

    async def should_prune(
        self,
        node: Node,
        session: SessionData,
        phase: str = "pre",
    ) -> tuple[bool, str | None]:
        del node, session
        if phase == "post":
            return True, "连续低价值路径"
        return False, None

    async def summarize_path(self, leaf_node: Node, session: SessionData) -> str:
        del leaf_node, session
        self.summary_calls += 1
        return "剪枝路径摘要"


@pytest.mark.integration
@pytest.mark.asyncio
class TestMCTSFlow:
    @pytest.fixture
    def setup_mcts_environment(self):
        session = SessionData(global_goal="探索人工智能技术的未来发展")
        root_node = Node(
            id=session.root_node_id,
            depth=0,
            interaction=QAInteraction(
                question="探索人工智能技术的未来发展",
                answer="人工智能技术正在快速发展，涉及多个领域...",
                summary="AI 技术发展概况",
            ),
        )
        session.add_node(root_node)

        llm_client = MockClient()
        checker = SequenceChecker()
        engine = MCTSEngine(
            session,
            questioner=Questioner(llm_client, checker=checker),
            pruner=Pruner(llm_client, checker=checker),
            compressor=Compressor(llm_client, checker=checker),
        )

        return {
            "session": session,
            "engine": engine,
        }

    async def test_mcts_initialization(self, setup_mcts_environment):
        engine = setup_mcts_environment["engine"]
        session = setup_mcts_environment["session"]

        assert engine is not None
        assert engine.session == session
        assert engine.c_param > 0

    async def test_mcts_selection(self, setup_mcts_environment):
        engine = setup_mcts_environment["engine"]
        session = setup_mcts_environment["session"]

        child1 = Node(
            parent_id=session.root_node_id,
            depth=1,
            interaction=QAInteraction(question="问题1", answer="回答1"),
        )
        child1.state.visit_count = 5
        child1.state.value_sum = 30.0

        child2 = Node(
            parent_id=session.root_node_id,
            depth=1,
            interaction=QAInteraction(question="问题2", answer="回答2"),
        )
        child2.state.visit_count = 3
        child2.state.value_sum = 24.0

        session.add_node(child1)
        session.add_node(child2)
        session.nodes[session.root_node_id].children_ids = [child1.id, child2.id]

        leaf_id = engine._select(session.root_node_id)

        assert leaf_id in [child1.id, child2.id]

    async def test_mcts_single_step(self, setup_mcts_environment):
        engine = setup_mcts_environment["engine"]
        session = setup_mcts_environment["session"]
        initial_simulations = session.total_simulations

        await engine.run_step()

        assert session.total_simulations >= initial_simulations

    async def test_mcts_multiple_iterations(self, setup_mcts_environment):
        engine = setup_mcts_environment["engine"]
        session = setup_mcts_environment["session"]

        for _ in range(5):
            if engine.should_stop():
                break
            await engine.run_step()

        assert session.total_simulations >= 0

    async def test_mcts_stop_conditions(self, setup_mcts_environment):
        engine = setup_mcts_environment["engine"]
        session = setup_mcts_environment["session"]

        session.total_simulations = 100
        assert engine.should_stop()

        session.total_simulations = 0
        session.nodes[session.root_node_id].is_terminal = True
        assert engine.should_stop()

    async def test_mcts_tree_statistics(self, setup_mcts_environment):
        engine = setup_mcts_environment["engine"]
        session = setup_mcts_environment["session"]

        for i in range(3):
            node = Node(
                parent_id=session.root_node_id,
                depth=1,
                interaction=QAInteraction(question=f"问题{i}", answer=f"回答{i}"),
            )
            node.state.visit_count = i + 1
            node.state.value_sum = (i + 1) * 5.0
            session.add_node(node)

        stats = engine.get_tree_statistics()

        assert "total_nodes" in stats
        assert "total_simulations" in stats
        assert "tree_depth" in stats
        assert stats["total_nodes"] >= 4

    async def test_mcts_get_best_child(self, setup_mcts_environment):
        engine = setup_mcts_environment["engine"]
        session = setup_mcts_environment["session"]

        child1 = Node(
            parent_id=session.root_node_id,
            depth=1,
            interaction=QAInteraction(question="问题1", answer="回答1"),
        )
        child1.state.visit_count = 10

        child2 = Node(
            parent_id=session.root_node_id,
            depth=1,
            interaction=QAInteraction(question="问题2", answer="回答2"),
        )
        child2.state.visit_count = 5

        session.add_node(child1)
        session.add_node(child2)
        session.nodes[session.root_node_id].children_ids = [child1.id, child2.id]

        best_child = engine.get_best_child()

        assert best_child.id == child1.id

    async def test_mcts_pre_review_prunes_duplicate_before_answer(self):
        session = SessionData(global_goal="测试预检查剪枝")
        root_node = Node(
            id=session.root_node_id,
            depth=0,
            interaction=QAInteraction(question="测试预检查剪枝", answer="探索起点"),
        )
        duplicate_leaf = Node(
            parent_id=root_node.id,
            depth=1,
            interaction=QAInteraction(question="重复问题", answer=""),
        )
        session.add_node(root_node)
        session.add_node(duplicate_leaf)
        root_node.children_ids = [duplicate_leaf.id]

        llm_client = SequenceLLM([])
        checker = SequenceChecker(
            reviews=[
                {
                    "is_duplicate": True,
                    "should_prune": True,
                    "reason": "问题重复",
                }
            ]
        )
        engine = MCTSEngine(
            session,
            questioner=Questioner(llm_client, checker=checker),
            compressor=Compressor(llm_client, checker=checker),
            pruner=Pruner(llm_client, checker=checker),
        )

        result = await engine.run_step()

        assert result is None
        assert duplicate_leaf.is_pruned is True
        assert duplicate_leaf.prune_reason == "问题重复"
        assert llm_client.calls == []

    async def test_mcts_post_review_prunes_low_value_after_processing(self):
        session = SessionData(global_goal="测试后检查剪枝")
        root_node = Node(
            id=session.root_node_id,
            depth=0,
            interaction=QAInteraction(question="测试后检查剪枝", answer="探索起点"),
        )
        leaf = Node(
            parent_id=root_node.id,
            depth=1,
            interaction=QAInteraction(question="这个方向是否值得继续？", answer=""),
        )
        session.add_node(root_node)
        session.add_node(leaf)
        root_node.children_ids = [leaf.id]

        llm_client = SequenceLLM(
            responses=[
                {
                    "content": "这是回答内容。",
                    "structured_content": None,
                    "tokens": 12,
                    "model": "answer-model",
                },
                {
                    "content": '[{"content": "提取出的事实", "confidence": 0.9}]',
                    "structured_content": [
                        {"content": "提取出的事实", "confidence": 0.9}
                    ],
                    "tokens": 8,
                    "model": "fact-model",
                },
            ]
        )
        checker = SequenceChecker(
            reviews=[
                {"score": 6.0},
                {
                    "is_low_value": True,
                    "should_prune": True,
                    "reason": "连续低价值路径",
                },
            ]
        )
        engine = MCTSEngine(
            session,
            questioner=Questioner(llm_client, checker=checker),
            compressor=Compressor(llm_client, checker=checker),
            pruner=Pruner(llm_client, checker=checker),
        )

        result = await engine.run_step()

        assert result is None
        assert leaf.is_pruned is True
        assert leaf.prune_reason == "连续低价值路径"
        assert leaf.interaction.answer == "这是回答内容。"
        assert llm_client.calls[0]["purpose"] == "generation"
        assert llm_client.calls[0]["response_contract"] == "text"
        assert llm_client.calls[1]["purpose"] == "generation"
        assert llm_client.calls[1]["response_contract"] == "json_array"

    async def test_mcts_normal_chain_uses_generation_contracts(self):
        session = SessionData(global_goal="测试正常执行链路")
        root_node = Node(
            id=session.root_node_id,
            depth=0,
            interaction=QAInteraction(question="测试正常执行链路", answer="探索起点"),
        )
        leaf = Node(
            parent_id=root_node.id,
            depth=1,
            interaction=QAInteraction(question="下一步该关注什么？", answer=""),
        )
        session.add_node(root_node)
        session.add_node(leaf)
        root_node.children_ids = [leaf.id]

        llm_client = SequenceLLM(
            responses=[
                {
                    "content": "这是一个正常回答。",
                    "structured_content": None,
                    "tokens": 12,
                    "model": "answer-model",
                },
                {
                    "content": '[{"content": "结构化事实", "confidence": 0.92}]',
                    "structured_content": [
                        {"content": "结构化事实", "confidence": 0.92}
                    ],
                    "tokens": 9,
                    "model": "fact-model",
                },
                {
                    "content": '["后续问题是什么？"]',
                    "structured_content": ["后续问题是什么？"],
                    "tokens": 11,
                    "model": "question-model",
                },
            ]
        )
        checker = SequenceChecker(
            reviews=[{"score": 6.0}, {"score": 6.0}, {"score": 7.5}]
        )
        engine = MCTSEngine(
            session,
            questioner=Questioner(llm_client, checker=checker),
            compressor=Compressor(llm_client, checker=checker),
            pruner=Pruner(llm_client, checker=checker),
        )

        result = await engine.run_step()

        assert result is not None
        assert llm_client.calls[0]["purpose"] == "generation"
        assert llm_client.calls[0]["response_contract"] == "text"
        assert llm_client.calls[1]["purpose"] == "generation"
        assert llm_client.calls[1]["response_contract"] == "json_array"
        assert llm_client.calls[2]["purpose"] == "generation"
        assert llm_client.calls[2]["response_contract"] == "json_array"
        assert session.global_facts
        assert any(
            session.nodes[node_id].interaction.question == "后续问题是什么？"
            for node_id in leaf.children_ids
        )

    async def test_expand_filters_candidates_before_creating_nodes(self):
        session = SessionData(global_goal="测试候选准入过滤")
        root_node = Node(
            id=session.root_node_id,
            depth=0,
            interaction=QAInteraction(
                question="测试候选准入过滤",
                answer="这里是根节点回答",
            ),
        )
        session.add_node(root_node)

        checker = SequenceChecker(
            reviews=[
                {"score": 7.0},
                {
                    "is_off_topic": True,
                    "should_prune": True,
                    "reason": "偏离主题",
                },
            ]
        )
        questioner = StaticQuestioner(
            questions=[
                "这个方向可行吗？",
                " 这个方向可行吗？ ",
                "今天午饭吃什么？",
            ]
        )
        engine = MCTSEngine(
            session,
            questioner=questioner,
            pruner=Pruner(SequenceLLM([]), checker=checker),
            compressor=StaticCompressor(),
        )

        new_node_ids = await engine._expand(session, root_node)

        assert len(new_node_ids) == 1
        assert len(root_node.children_ids) == 1
        assert session.nodes[root_node.children_ids[0]].interaction.question == (
            "这个方向可行吗？"
        )
        assert len(checker.review_calls) == 2
        assert all(call["stage"] == "pre" for call in checker.review_calls)

    async def test_post_prune_persists_generated_path_summary(self):
        session = SessionData(global_goal="测试剪枝摘要")
        root_node = Node(
            id=session.root_node_id,
            depth=0,
            interaction=QAInteraction(question="测试剪枝摘要", answer="探索起点"),
        )
        leaf = Node(
            parent_id=root_node.id,
            depth=1,
            interaction=QAInteraction(question="这个方向是否值得继续？", answer=""),
        )
        session.add_node(root_node)
        session.add_node(leaf)
        root_node.children_ids = [leaf.id]

        pruner = SummaryPruner()
        engine = MCTSEngine(
            session,
            questioner=StaticQuestioner(questions=[]),
            compressor=StaticCompressor(),
            pruner=pruner,
        )

        result = await engine.run_step()

        assert result is None
        assert leaf.is_pruned is True
        assert leaf.prune_reason == "连续低价值路径"
        assert leaf.interaction.summary == "剪枝路径摘要"
        assert pruner.summary_calls == 1


@pytest.mark.integration
@pytest.mark.asyncio
class TestMCTSBackpropagation:
    @pytest.fixture
    def session_with_path(self):
        session = SessionData(global_goal="测试")
        root = Node(id=session.root_node_id, depth=0)
        session.add_node(root)

        child = Node(parent_id=root.id, depth=1)
        session.add_node(child)
        root.children_ids.append(child.id)

        grandchild = Node(parent_id=child.id, depth=2)
        session.add_node(grandchild)
        child.children_ids.append(grandchild.id)

        return session

    async def test_backpropagation_updates_all_ancestors(self, session_with_path):
        engine = MCTSEngine(session_with_path)
        leaf = [
            node for node in session_with_path.nodes.values() if not node.children_ids
        ][0]
        initial_visits = {
            node_id: node.state.visit_count
            for node_id, node in session_with_path.nodes.items()
        }

        engine._backpropagate(leaf.id, 7.5)

        for node_id in session_with_path.nodes:
            current_visits = session_with_path.nodes[node_id].state.visit_count
            if node_id in [leaf.id, leaf.parent_id, session_with_path.root_node_id]:
                assert current_visits > initial_visits[node_id]

    async def test_backpropagation_value_accumulation(self, session_with_path):
        engine = MCTSEngine(session_with_path)
        leaf = [
            node for node in session_with_path.nodes.values() if not node.children_ids
        ][0]

        for value in [5.0, 7.0, 6.0]:
            engine._backpropagate(leaf.id, value)

        assert leaf.state.value_sum == 18.0
        assert leaf.state.visit_count == 3
