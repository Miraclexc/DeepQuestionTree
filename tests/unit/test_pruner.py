"""
单元测试 - Pruner 模块
测试剪枝判断、路径摘要、子树剪枝功能
"""

from types import SimpleNamespace

import pytest

from src.backend.core.schema import Fact, Node, QAInteraction, SessionData
from src.backend.modules.pruner import Pruner


class SequencePrunerChecker:
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
class TestPruner:
    @pytest.fixture
    def pruner(self, mock_llm_client):
        return Pruner(
            mock_llm_client,
            checker=SequencePrunerChecker(),
        )

    @pytest.fixture
    def test_session(self):
        session = SessionData(global_goal="测试AI技术")
        root = Node(
            id=session.root_node_id,
            depth=0,
            interaction=QAInteraction(question="测试AI技术", answer="AI是..."),
        )
        session.add_node(root)
        return session

    async def test_should_prune_max_depth(self, pruner, test_session):
        deep_node = Node(
            depth=10,
            interaction=QAInteraction(question="深层问题", answer="深层回答"),
        )
        test_session.add_node(deep_node)

        should_prune, reason = await pruner.should_prune(
            deep_node,
            test_session,
            phase="pre",
        )

        assert should_prune is True
        assert "深度" in reason or "depth" in reason.lower()

    async def test_should_prune_duplicate_question(self, mock_llm_client, test_session):
        pruner = Pruner(
            mock_llm_client,
            checker=SequencePrunerChecker(
                [
                    {
                        "is_duplicate": True,
                        "should_prune": True,
                        "reason": "问题重复",
                    }
                ]
            ),
        )
        node1 = Node(
            depth=1,
            interaction=QAInteraction(
                question="什么是深度学习？", answer="深度学习是..."
            ),
        )
        node2 = Node(
            depth=1,
            interaction=QAInteraction(question="什么是深度学习？", answer=""),
        )
        test_session.add_node(node1)
        test_session.add_node(node2)

        should_prune, reason = await pruner.should_prune(
            node2,
            test_session,
            phase="pre",
        )

        assert should_prune is True
        assert reason == "问题重复"

    async def test_should_prune_off_topic_question(self, mock_llm_client, test_session):
        pruner = Pruner(
            mock_llm_client,
            checker=SequencePrunerChecker(
                [
                    {
                        "is_off_topic": True,
                        "should_prune": True,
                        "reason": "偏离主题",
                    }
                ]
            ),
        )
        node = Node(
            depth=1,
            interaction=QAInteraction(question="今天中午吃什么？", answer=""),
        )
        test_session.add_node(node)

        should_prune, reason = await pruner.should_prune(
            node,
            test_session,
            phase="pre",
        )

        assert should_prune is True
        assert reason == "偏离主题"

    async def test_should_prune_low_value_path(self, mock_llm_client, test_session):
        pruner = Pruner(
            mock_llm_client,
            checker=SequencePrunerChecker(
                [
                    {
                        "is_low_value": True,
                        "should_prune": True,
                        "reason": "连续低价值路径",
                    }
                ]
            ),
        )
        nodes = []
        parent_id = test_session.root_node_id

        for i in range(4):
            node = Node(
                parent_id=parent_id,
                depth=i + 1,
                interaction=QAInteraction(question=f"问题{i}", answer=f"回答{i}"),
            )
            node.state.visit_count = 3
            node.state.value_sum = 3.0
            test_session.add_node(node)
            nodes.append(node)
            parent_id = node.id

        should_prune, reason = await pruner.should_prune(
            nodes[-1],
            test_session,
            phase="post",
        )

        assert should_prune is True
        assert reason == "连续低价值路径"

    async def test_should_prune_sufficient_facts(self, pruner, test_session):
        for i in range(60):
            test_session.add_global_fact(
                Fact(content=f"事实 {i}", source_node_id="node_1")
            )

        node = Node(
            depth=1, interaction=QAInteraction(question="测试问题ABC", answer="测试")
        )
        test_session.add_node(node)

        should_prune, reason = await pruner.should_prune(
            node,
            test_session,
            phase="pre",
        )

        assert should_prune is True
        assert reason is not None

    async def test_should_not_prune_normal_node(self, pruner, test_session):
        node = Node(
            depth=2,
            interaction=QAInteraction(
                question="一个非常独特的新问题XYZ123",
                answer="一个新回答",
            ),
        )
        node.state.visit_count = 5
        node.state.value_sum = 35.0
        test_session.add_node(node)

        should_prune, reason = await pruner.should_prune(
            node,
            test_session,
            phase="pre",
        )

        assert should_prune is False
        assert reason is None

    async def test_summarize_path(self, pruner, sample_nodes):
        leaf_nodes = [
            node for node in sample_nodes.nodes.values() if not node.children_ids
        ]
        summary = await pruner.summarize_path(leaf_nodes[0], sample_nodes)

        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_get_path_to_root(self, pruner, sample_nodes):
        deepest_node = max(sample_nodes.nodes.values(), key=lambda node: node.depth)
        path = pruner._get_path_to_root(deepest_node, sample_nodes)

        assert path[0].id == sample_nodes.root_node_id
        assert path[-1].id == deepest_node.id
        for index in range(1, len(path)):
            assert path[index].parent_id == path[index - 1].id

    def test_prune_subtree(self, pruner, sample_nodes):
        parent_node = next(
            node for node in sample_nodes.nodes.values() if node.children_ids
        )
        pruned_count = pruner.prune_subtree(parent_node.id, "测试剪枝", sample_nodes)

        assert pruned_count >= 1
        assert sample_nodes.nodes[parent_node.id].is_pruned is True
        assert sample_nodes.nodes[parent_node.id].prune_reason == "测试剪枝"

    def test_get_pruning_statistics(self, pruner, sample_nodes):
        nodes_list = list(sample_nodes.nodes.values())
        nodes_list[1].mark_pruned("测试原因1")
        nodes_list[2].mark_pruned("测试原因2")

        stats = pruner.get_pruning_statistics(sample_nodes)

        assert stats["total_nodes"] > 0
        assert stats["pruned_nodes"] >= 0
        assert 0 <= stats["pruned_percentage"] <= 100
        assert "prune_reasons" in stats

    def test_get_history_questions(self, pruner, sample_nodes):
        questions = pruner._get_history_questions(
            sample_nodes, sample_nodes.root_node_id
        )

        assert isinstance(questions, list)
        excluded_node = sample_nodes.nodes[sample_nodes.root_node_id]
        if excluded_node.interaction:
            assert excluded_node.interaction.question not in questions


@pytest.mark.unit
class TestPrunerEdgeCases:
    @pytest.fixture
    def pruner(self, mock_llm_client):
        return Pruner(
            mock_llm_client,
            checker=SequencePrunerChecker(),
        )

    async def test_should_prune_node_without_interaction(self, pruner):
        session = SessionData(global_goal="测试")
        node = Node(depth=1)
        session.add_node(node)

        should_prune, reason = await pruner.should_prune(node, session, phase="pre")

        assert isinstance(should_prune, bool)
        assert reason in (None, "已有足够信息")

    async def test_summarize_path_empty_path(self, pruner):
        session = SessionData(global_goal="测试")
        root = Node(id=session.root_node_id, depth=0)
        session.add_node(root)

        summary = await pruner.summarize_path(root, session)

        assert isinstance(summary, str)

    def test_prune_subtree_nonexistent_node(self, pruner, sample_session):
        assert pruner.prune_subtree("nonexistent_id", "测试", sample_session) == 0

    def test_get_pruning_statistics_empty_session(self, pruner):
        stats = pruner.get_pruning_statistics(SessionData(global_goal="测试"))

        assert stats["total_nodes"] == 0
        assert stats["pruned_nodes"] == 0
        assert stats["active_nodes"] == 0
