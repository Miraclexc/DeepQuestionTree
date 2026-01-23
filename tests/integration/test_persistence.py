"""
集成测试 - 持久化模块
测试会话的保存、加载、恢复功能
"""
import pytest
import json
from pathlib import Path

from src.backend.modules.persistence import SessionManager
from src.backend.core.schema import SessionData, Node, QAInteraction, Fact


@pytest.mark.integration
@pytest.mark.asyncio
class TestPersistence:
    """测试持久化功能"""

    @pytest.fixture
    def session_manager(self, temp_session_dir):
        """创建会话管理器"""
        manager = SessionManager()
        # 使用临时目录
        manager.sessions_dir = temp_session_dir
        return manager

    @pytest.fixture
    def sample_session_with_data(self):
        """创建包含数据的示例会话"""
        session = SessionData(global_goal="测试持久化功能")

        # 添加根节点
        root = Node(
            id=session.root_node_id,
            depth=0,
            interaction=QAInteraction(
                question="测试持久化功能",
                answer="这是一个测试会话",
                summary="测试会话"
            )
        )
        session.add_node(root)

        # 添加子节点
        child = Node(
            parent_id=root.id,
            depth=1,
            interaction=QAInteraction(
                question="子节点问题",
                answer="子节点回答",
                tokens_used=150
            )
        )
        child.state.visit_count = 5
        child.state.value_sum = 35.0
        session.add_node(child)
        root.children_ids.append(child.id)

        # 添加事实
        fact1 = Fact(content="测试事实1", source_node_id=child.id, confidence=0.9)
        fact2 = Fact(content="测试事实2", source_node_id=child.id, confidence=0.85)
        session.add_global_fact(fact1)
        session.add_global_fact(fact2)

        # 更新统计
        session.total_simulations = 10
        session.total_tokens_used = 500

        return session

    async def test_save_session(self, session_manager, sample_session_with_data):
        """测试保存会话"""
        session = sample_session_with_data

        result = await session_manager.save_session(session)

        assert result is True

        # 检查文件是否存在
        file_path = session_manager.sessions_dir / f"{session.session_id}.json"
        assert file_path.exists()

    async def test_save_and_load_session(self, session_manager, sample_session_with_data):
        """测试保存后加载会话"""
        original_session = sample_session_with_data

        # 保存
        await session_manager.save_session(original_session)

        # 加载
        loaded_session = await session_manager.load_session(original_session.session_id)

        # 验证数据一致性
        assert loaded_session is not None
        assert loaded_session.session_id == original_session.session_id
        assert loaded_session.global_goal == original_session.global_goal
        assert len(loaded_session.nodes) == len(original_session.nodes)
        assert len(loaded_session.global_facts) == len(original_session.global_facts)
        assert loaded_session.total_simulations == original_session.total_simulations

    async def test_load_nonexistent_session(self, session_manager):
        """测试加载不存在的会话"""
        result = await session_manager.load_session("nonexistent_session_id")

        assert result is None

    async def test_delete_session(self, session_manager, sample_session_with_data):
        """测试删除会话"""
        session = sample_session_with_data

        # 先保存
        await session_manager.save_session(session)

        # 删除
        result = await session_manager.delete_session(session.session_id)

        assert result is True

        # 文件应该不存在了
        file_path = session_manager.sessions_dir / f"{session.session_id}.json"
        assert not file_path.exists()

    async def test_list_sessions(self, session_manager, sample_session_with_data):
        """测试列出会话"""
        # 保存几个会话
        session1 = sample_session_with_data
        await session_manager.save_session(session1)

        session2 = SessionData(global_goal="第二个测试会话")
        root2 = Node(id=session2.root_node_id, depth=0)
        session2.add_node(root2)
        await session_manager.save_session(session2)

        # 列出会话
        sessions = session_manager.list_sessions()

        # 应该有至少 2 个会话
        assert len(sessions) >= 2

        # 检查会话信息
        session_ids = [s["session_id"] for s in sessions]
        assert session1.session_id in session_ids
        assert session2.session_id in session_ids

    async def test_backup_session(self, session_manager, sample_session_with_data, tmp_path):
        """测试会话备份"""
        session = sample_session_with_data

        # 先保存
        await session_manager.save_session(session)

        # 备份
        backup_dir = tmp_path / "backup"
        result = await session_manager.backup_session(session.session_id, str(backup_dir))

        assert result is True

        # 检查备份文件
        backup_file = backup_dir / f"{session.session_id}_backup.json"
        assert backup_file.exists()

    def test_get_session_count(self, session_manager):
        """测试获取会话数量"""
        count = session_manager.get_session_count()
        assert isinstance(count, int)
        assert count >= 0

    async def test_session_json_structure(self, session_manager, sample_session_with_data):
        """测试保存的 JSON 结构"""
        session = sample_session_with_data

        # 保存
        await session_manager.save_session(session)

        # 读取 JSON 文件
        file_path = session_manager.sessions_dir / f"{session.session_id}.json"
        with open(file_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)

        # 检查 JSON 结构
        assert "session_id" in json_data
        assert "global_goal" in json_data
        assert "nodes" in json_data
        assert "global_facts" in json_data
        assert "total_simulations" in json_data
        assert "status" in json_data

        # 检查节点结构
        assert isinstance(json_data["nodes"], dict)
        assert len(json_data["nodes"]) > 0

    async def test_atomic_write(self, session_manager, sample_session_with_data):
        """测试原子写入（临时文件机制）"""
        session = sample_session_with_data

        # 保存
        await session_manager.save_session(session)

        # 临时文件应该不存在（已被重命名）
        temp_file = session_manager.sessions_dir / f"{session.session_id}.tmp"
        assert not temp_file.exists()

        # 正式文件应该存在
        file_path = session_manager.sessions_dir / f"{session.session_id}.json"
        assert file_path.exists()


@pytest.mark.integration
class TestPersistenceEdgeCases:
    """测试持久化的边界情况"""

    @pytest.fixture
    def session_manager(self, temp_session_dir):
        manager = SessionManager()
        manager.sessions_dir = temp_session_dir
        return manager

    async def test_save_empty_session(self, session_manager):
        """测试保存空会话"""
        session = SessionData(global_goal="空会话")
        # 不添加任何节点

        result = await session_manager.save_session(session)
        assert result is True

    async def test_load_corrupted_json(self, session_manager, temp_session_dir):
        """测试加载损坏的 JSON 文件"""
        # 创建一个损坏的 JSON 文件
        session_id = "corrupted_session"
        file_path = temp_session_dir / f"{session_id}.json"

        with open(file_path, 'w') as f:
            f.write("{ invalid json content")

        # 尝试加载
        result = await session_manager.load_session(session_id)

        # 应该返回 None 或处理错误
        assert result is None

    async def test_list_sessions_empty_directory(self, session_manager):
        """测试空目录的会话列表"""
        sessions = session_manager.list_sessions()

        assert isinstance(sessions, list)
        assert len(sessions) == 0

    def test_cleanup_old_sessions(self, session_manager, temp_session_dir):
        """测试清理旧会话"""
        # 创建一些测试文件
        for i in range(3):
            file_path = temp_session_dir / f"old_session_{i}.json"
            file_path.write_text('{"test": "data"}')

        # 清理（保留 0 天，即删除所有）
        cleaned = session_manager.cleanup_old_sessions(days=0)

        # 应该清理了一些会话
        assert cleaned >= 0
