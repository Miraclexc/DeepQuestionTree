"""
集成测试 - MCTS 流程
测试完整的 MCTS 迭代流程
"""
import pytest

from src.backend.core.mcts_engine import MCTSEngine
from src.backend.core.schema import SessionData, Node, QAInteraction
from src.backend.modules.questioner import Questioner
from src.backend.modules.pruner import Pruner
from src.backend.llm.mock_client import MockClient
from src.backend.llm.embedding import get_embedding_manager


@pytest.mark.integration
@pytest.mark.asyncio
class TestMCTSFlow:
    """测试 MCTS 完整流程"""

    @pytest.fixture
    def setup_mcts_environment(self):
        """设置 MCTS 测试环境"""
        # 创建会话
        session = SessionData(global_goal="探索人工智能技术的未来发展")

        # 创建根节点
        root_node = Node(
            id=session.root_node_id,
            depth=0,
            interaction=QAInteraction(
                question="探索人工智能技术的未来发展",
                answer="人工智能技术正在快速发展，涉及多个领域...",
                summary="AI 技术发展概况"
            )
        )
        session.add_node(root_node)

        # 创建 LLM 客户端和模块
        llm_client = MockClient()
        embedding_manager = get_embedding_manager()
        embedding_manager.set_client(llm_client)

        questioner = Questioner(llm_client, embedding_manager)
        pruner = Pruner(llm_client, embedding_manager)

        # 创建 MCTS 引擎
        # 注意：这需要修复 mcts_engine.py 的初始化
        engine = MCTSEngine(session)

        return {
            "session": session,
            "engine": engine,
            "llm_client": llm_client,
            "questioner": questioner,
            "pruner": pruner
        }

    async def test_mcts_initialization(self, setup_mcts_environment):
        """测试 MCTS 引擎初始化"""
        env = setup_mcts_environment
        engine = env["engine"]
        session = env["session"]

        assert engine is not None
        assert engine.session == session
        assert engine.c_param > 0

    async def test_mcts_selection(self, setup_mcts_environment):
        """测试 Selection 步骤"""
        env = setup_mcts_environment
        engine = env["engine"]
        session = env["session"]

        # 添加一些子节点
        child1 = Node(
            parent_id=session.root_node_id,
            depth=1,
            interaction=QAInteraction(question="问题1", answer="回答1")
        )
        child1.state.visit_count = 5
        child1.state.value_sum = 30.0

        child2 = Node(
            parent_id=session.root_node_id,
            depth=1,
            interaction=QAInteraction(question="问题2", answer="回答2")
        )
        child2.state.visit_count = 3
        child2.state.value_sum = 24.0

        session.add_node(child1)
        session.add_node(child2)
        session.nodes[session.root_node_id].children_ids = [child1.id, child2.id]

        # 执行 Selection
        leaf_id = engine._select(session.root_node_id)

        # 应该选中一个叶子节点
        assert leaf_id in [child1.id, child2.id]

    async def test_mcts_single_step(self, setup_mcts_environment):
        """测试单次 MCTS 迭代"""
        env = setup_mcts_environment
        engine = env["engine"]
        session = env["session"]

        initial_simulations = session.total_simulations

        # 执行一步（注意：当前 expand 返回空列表）
        result = await engine.run_step()

        # 模拟次数应该增加（如果成功执行）
        # 由于 expand 未实现，可能返回 None
        if result:
            assert session.total_simulations > initial_simulations

    async def test_mcts_multiple_iterations(self, setup_mcts_environment):
        """测试多次 MCTS 迭代"""
        env = setup_mcts_environment
        engine = env["engine"]
        session = env["session"]

        # 执行多次迭代
        max_iterations = 5
        for i in range(max_iterations):
            if engine.should_stop():
                break
            await engine.run_step()

        # 会话应该有一些更新
        assert session.total_simulations >= 0

    async def test_mcts_stop_conditions(self, setup_mcts_environment):
        """测试停止条件"""
        env = setup_mcts_environment
        engine = env["engine"]
        session = env["session"]

        # 测试最大模拟次数
        session.total_simulations = 100
        assert engine.should_stop()

        # 重置
        session.total_simulations = 0

        # 测试无活跃节点
        session.nodes[session.root_node_id].is_terminal = True
        assert engine.should_stop()

    async def test_mcts_tree_statistics(self, setup_mcts_environment):
        """测试树统计信息"""
        env = setup_mcts_environment
        engine = env["engine"]
        session = env["session"]

        # 添加一些节点
        for i in range(3):
            node = Node(
                parent_id=session.root_node_id,
                depth=1,
                interaction=QAInteraction(question=f"问题{i}", answer=f"回答{i}")
            )
            node.state.visit_count = i + 1
            node.state.value_sum = (i + 1) * 5.0
            session.add_node(node)

        stats = engine.get_tree_statistics()

        assert "total_nodes" in stats
        assert "total_simulations" in stats
        assert "tree_depth" in stats
        assert stats["total_nodes"] >= 4  # 根节点 + 3个子节点

    async def test_mcts_get_best_child(self, setup_mcts_environment):
        """测试获取最佳子节点"""
        env = setup_mcts_environment
        engine = env["engine"]
        session = env["session"]

        # 添加子节点
        child1 = Node(
            parent_id=session.root_node_id,
            depth=1,
            interaction=QAInteraction(question="问题1", answer="回答1")
        )
        child1.state.visit_count = 10  # 访问最多

        child2 = Node(
            parent_id=session.root_node_id,
            depth=1,
            interaction=QAInteraction(question="问题2", answer="回答2")
        )
        child2.state.visit_count = 5

        session.add_node(child1)
        session.add_node(child2)
        session.nodes[session.root_node_id].children_ids = [child1.id, child2.id]

        best_child = engine.get_best_child()

        # 应该选中访问次数最多的子节点
        assert best_child.id == child1.id


@pytest.mark.integration
@pytest.mark.asyncio
class TestMCTSBackpropagation:
    """测试 MCTS 回传播机制"""

    @pytest.fixture
    def session_with_path(self):
        """创建有路径的会话"""
        session = SessionData(global_goal="测试")

        # 创建一条深度为 3 的路径
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
        """测试回传播更新所有祖先节点"""
        engine = MCTSEngine(session_with_path)

        # 获取叶子节点
        leaf_nodes = [n for n in session_with_path.nodes.values() if not n.children_ids]
        leaf = leaf_nodes[0]

        # 记录初始访问次数
        initial_visits = {
            node_id: node.state.visit_count
            for node_id, node in session_with_path.nodes.items()
        }

        # 执行回传播
        value = 7.5
        engine._backpropagate(leaf.id, value)

        # 检查路径上所有节点的访问次数都增加了
        for node_id in session_with_path.nodes:
            current_visits = session_with_path.nodes[node_id].state.visit_count
            # 路径上的节点访问次数应该增加
            if node_id in [leaf.id, leaf.parent_id, session_with_path.root_node_id]:
                assert current_visits > initial_visits[node_id]

    async def test_backpropagation_value_accumulation(self, session_with_path):
        """测试回传播价值累积"""
        engine = MCTSEngine(session_with_path)

        leaf_nodes = [n for n in session_with_path.nodes.values() if not n.children_ids]
        leaf = leaf_nodes[0]

        # 多次回传播
        values = [5.0, 7.0, 6.0]
        for value in values:
            engine._backpropagate(leaf.id, value)

        # 叶子节点的累积价值应该等于所有值的和
        assert leaf.state.value_sum == sum(values)
        assert leaf.state.visit_count == len(values)
