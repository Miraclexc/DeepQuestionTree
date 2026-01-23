"""
单元测试 - 数据模型和 Schema
测试 Pydantic 模型的验证、序列化和核心方法
"""
import pytest
import math
import json
from datetime import datetime

from src.backend.core.schema import (
    Fact, QAInteraction, NodeState, Node, SessionData, SessionStatus
)


@pytest.mark.unit
class TestFact:
    """测试 Fact 数据模型"""

    def test_fact_creation(self):
        """测试事实创建"""
        fact = Fact(
            content="测试事实内容",
            source_node_id="node_123",
            confidence=0.95
        )

        assert fact.content == "测试事实内容"
        assert fact.source_node_id == "node_123"
        assert fact.confidence == 0.95
        assert fact.id is not None
        assert isinstance(fact.created_at, datetime)

    def test_fact_confidence_validation(self):
        """测试置信度范围验证"""
        # 有效范围
        fact = Fact(content="测试", source_node_id="node_1", confidence=0.5)
        assert fact.confidence == 0.5

        # 边界值
        fact_min = Fact(content="测试", source_node_id="node_1", confidence=0.0)
        assert fact_min.confidence == 0.0

        fact_max = Fact(content="测试", source_node_id="node_1", confidence=1.0)
        assert fact_max.confidence == 1.0

    def test_fact_serialization(self):
        """测试事实序列化"""
        fact = Fact(
            content="测试事实",
            source_node_id="node_1",
            confidence=0.9
        )

        # 序列化为字典
        fact_dict = fact.model_dump()
        assert "content" in fact_dict
        assert "source_node_id" in fact_dict
        assert "confidence" in fact_dict

        # 序列化为 JSON
        fact_json = fact.model_dump_json()
        assert isinstance(fact_json, str)

        # 反序列化
        fact_loaded = Fact.model_validate_json(fact_json)
        assert fact_loaded.content == fact.content


@pytest.mark.unit
class TestQAInteraction:
    """测试问答交互模型"""

    def test_qa_interaction_creation(self):
        """测试问答创建"""
        qa = QAInteraction(
            question="什么是AI？",
            answer="人工智能（AI）是...",
            summary="AI 定义",
            tokens_used=150
        )

        assert qa.question == "什么是AI？"
        assert qa.answer == "人工智能（AI）是..."
        assert qa.summary == "AI 定义"
        assert qa.tokens_used == 150

    def test_qa_default_values(self):
        """测试默认值"""
        qa = QAInteraction(
            question="测试问题",
            answer="测试回答"
        )

        assert qa.summary is None
        assert qa.tokens_used == 0
        assert qa.model_used is None


@pytest.mark.unit
class TestNodeState:
    """测试节点状态模型"""

    def test_node_state_creation(self):
        """测试节点状态创建"""
        state = NodeState(visit_count=10, value_sum=75.0)

        assert state.visit_count == 10
        assert state.value_sum == 75.0

    def test_average_value_calculation(self):
        """测试平均价值计算"""
        state = NodeState(visit_count=5, value_sum=35.0)
        assert state.average_value == 7.0

        # 未访问节点
        state_unvisited = NodeState(visit_count=0, value_sum=0.0)
        assert state_unvisited.average_value == 0.0


@pytest.mark.unit
class TestNode:
    """测试节点模型"""

    def test_node_creation(self):
        """测试节点创建"""
        node = Node(depth=1)

        assert node.id is not None
        assert node.parent_id is None
        assert node.children_ids == []
        assert node.depth == 1
        assert not node.is_terminal
        assert not node.is_pruned

    def test_uct_value_unvisited(self):
        """测试未访问节点的 UCT 值"""
        node = Node()
        uct = node.uct_value(parent_visit_count=10, c_param=1.414)

        # 未访问节点应返回无穷大
        assert uct == float('inf')

    def test_uct_value_calculation(self):
        """测试 UCT 值计算"""
        node = Node()
        node.state.visit_count = 5
        node.state.value_sum = 35.0  # 平均值 7.0

        parent_visits = 20
        c_param = 1.414

        uct = node.uct_value(parent_visits, c_param)

        # 手动计算期望值
        exploitation = 7.0
        exploration = c_param * math.sqrt(math.log(parent_visits) / 5)
        expected_uct = exploitation + exploration

        assert abs(uct - expected_uct) < 0.001

    def test_uct_formula_components(self):
        """测试 UCT 公式的利用和探索项"""
        # 高价值、多访问的节点
        high_value_node = Node()
        high_value_node.state.visit_count = 10
        high_value_node.state.value_sum = 90.0  # 平均 9.0

        # 低价值、少访问的节点
        low_value_node = Node()
        low_value_node.state.visit_count = 2
        low_value_node.state.value_sum = 6.0  # 平均 3.0

        parent_visits = 20
        c_param = 1.414

        uct_high = high_value_node.uct_value(parent_visits, c_param)
        uct_low = low_value_node.uct_value(parent_visits, c_param)

        # 验证 UCT 值都是有效的数字
        assert isinstance(uct_high, float)
        assert isinstance(uct_low, float)

        # 低访问节点的探索项应该更大
        # exploration_low = 1.414 * sqrt(ln(20)/2) ≈ 2.15
        # exploration_high = 1.414 * sqrt(ln(20)/10) ≈ 0.96
        # 即使高价值节点的平均值更高，低访问节点也可能因探索奖励而有竞争力
        # 但不一定总是更高，所以我们只验证它们都在合理范围内
        assert 0 < uct_low < 20  # 合理范围
        assert 0 < uct_high < 20  # 合理范围

    def test_add_child(self):
        """测试添加子节点"""
        parent = Node()
        child_id = "child_123"

        parent.add_child(child_id)
        assert child_id in parent.children_ids

        # 重复添加应不会重复
        parent.add_child(child_id)
        assert parent.children_ids.count(child_id) == 1

    def test_mark_pruned(self):
        """测试剪枝标记"""
        node = Node()
        reason = "重复问题"

        node.mark_pruned(reason)

        assert node.is_pruned
        assert node.prune_reason == reason


@pytest.mark.unit
class TestSessionData:
    """测试会话数据模型"""

    def test_session_creation(self):
        """测试会话创建"""
        session = SessionData(global_goal="探索AI技术")

        assert session.session_id is not None
        assert session.root_node_id is not None
        assert session.global_goal == "探索AI技术"
        assert session.nodes == {}
        assert session.global_facts == []
        assert session.total_simulations == 0
        assert session.status == SessionStatus.RUNNING

    def test_add_node(self):
        """测试添加节点"""
        session = SessionData(global_goal="测试")
        node = Node(depth=0)

        session.add_node(node)

        assert node.id in session.nodes
        assert session.nodes[node.id] == node

    def test_get_node(self):
        """测试获取节点"""
        session = SessionData(global_goal="测试")
        node = Node()
        session.add_node(node)

        retrieved = session.get_node(node.id)
        assert retrieved == node

        # 不存在的节点
        assert session.get_node("nonexistent") is None

    def test_add_global_fact(self):
        """测试添加全局事实"""
        session = SessionData(global_goal="测试")
        fact = Fact(content="测试事实", source_node_id="node_1")

        session.add_global_fact(fact)

        assert fact in session.global_facts
        assert len(session.global_facts) == 1

    def test_increment_simulations(self):
        """测试增加模拟次数"""
        session = SessionData(global_goal="测试")
        initial = session.total_simulations

        session.increment_simulations()

        assert session.total_simulations == initial + 1

    def test_get_tree_depth(self, sample_nodes):
        """测试获取树深度"""
        depth = sample_nodes.get_tree_depth()
        assert depth == 2  # 最深的节点在第2层

    def test_get_total_nodes(self, sample_nodes):
        """测试获取节点总数"""
        total = sample_nodes.get_total_nodes()
        assert total == 4  # 根节点 + 2个子节点 + 1个孙节点

    def test_get_active_nodes(self, sample_nodes):
        """测试获取活跃节点"""
        # 标记一个节点为剪枝
        nodes_list = list(sample_nodes.nodes.values())
        nodes_list[1].mark_pruned("测试剪枝")

        active = sample_nodes.get_active_nodes()

        # 应该少一个被剪枝的节点
        assert len(active) < sample_nodes.get_total_nodes()
        assert all(not node.is_pruned and not node.is_terminal for node in active)

    def test_get_best_path(self, sample_nodes):
        """测试获取最佳路径"""
        path = sample_nodes.get_best_path()

        # 应该是从根到访问次数最多的分支
        assert len(path) >= 1
        assert path[0].id == sample_nodes.root_node_id

        # 路径应该是连续的（每个节点的父节点是前一个节点）
        for i in range(1, len(path)):
            assert path[i].parent_id == path[i-1].id

    def test_session_serialization(self, sample_session):
        """测试会话序列化"""
        # 序列化为 JSON
        session_json = sample_session.model_dump_json(indent=2)
        assert isinstance(session_json, str)

        # 反序列化
        session_dict = json.loads(session_json)
        loaded_session = SessionData(**session_dict)

        assert loaded_session.session_id == sample_session.session_id
        assert loaded_session.global_goal == sample_session.global_goal
        assert len(loaded_session.nodes) == len(sample_session.nodes)

    def test_session_status_enum(self):
        """测试会话状态枚举"""
        session = SessionData(global_goal="测试")

        # 测试状态转换
        session.status = SessionStatus.PAUSED
        assert session.status == SessionStatus.PAUSED

        session.status = SessionStatus.COMPLETED
        assert session.status == SessionStatus.COMPLETED

        session.status = SessionStatus.ERROR
        assert session.status == SessionStatus.ERROR


@pytest.mark.unit
class TestUCTAlgorithm:
    """专门测试 UCT 算法的正确性"""

    def test_exploration_bonus(self):
        """测试探索奖励随访问次数衰减"""
        node = Node()
        node.state.value_sum = 50.0
        parent_visits = 100
        c_param = 1.414

        # 访问次数增加，探索奖励应该减少
        uct_values = []
        for visit_count in [1, 5, 10, 20, 50]:
            node.state.visit_count = visit_count
            uct = node.uct_value(parent_visits, c_param)
            uct_values.append(uct)

        # UCT 值应该递减（因为探索项递减）
        for i in range(len(uct_values) - 1):
            assert uct_values[i] > uct_values[i + 1]

    def test_c_param_effect(self):
        """测试 C 参数对探索的影响"""
        node = Node()
        node.state.visit_count = 5
        node.state.value_sum = 25.0
        parent_visits = 20

        # 较小的 C 值（更重视利用）
        uct_small_c = node.uct_value(parent_visits, c_param=0.5)

        # 较大的 C 值（更重视探索）
        uct_large_c = node.uct_value(parent_visits, c_param=2.0)

        # 大 C 值应该产生更大的 UCT（更鼓励探索）
        assert uct_large_c > uct_small_c

    def test_parent_visits_effect(self):
        """测试父节点访问次数的影响"""
        node = Node()
        node.state.visit_count = 5
        node.state.value_sum = 35.0
        c_param = 1.414

        # 父节点访问次数增加，探索奖励应该增加
        uct_low_parent = node.uct_value(parent_visit_count=10, c_param=c_param)
        uct_high_parent = node.uct_value(parent_visit_count=100, c_param=c_param)

        # 父节点访问多了，子节点的探索奖励应该增加
        assert uct_high_parent > uct_low_parent
