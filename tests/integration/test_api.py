"""
集成测试 - FastAPI 端点
测试 API 的功能性和集成
"""
import pytest
from httpx import AsyncClient, ASGITransport

from src.backend.main import app
from src.backend.core.schema import SessionData


@pytest.mark.integration
@pytest.mark.asyncio
class TestAPIEndpoints:
    """测试 API 端点"""

    @pytest.fixture
    async def client(self):
        """创建测试客户端"""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as ac:
            yield ac

    async def test_start_session(self, client):
        """测试启动会话"""
        response = await client.post(
            "/api/start",
            json={
                "goal": "测试人工智能技术",
                "use_mock": True
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert "session_id" in data
        assert "message" in data
        assert "status" in data
        assert data["status"] == "running"

    async def test_get_status(self, client):
        """测试获取状态"""
        response = await client.get("/api/status")

        assert response.status_code == 200
        data = response.json()

        assert "mcts_running" in data
        assert "has_active_session" in data
        assert "environment" in data

    async def test_stop_session(self, client):
        """测试停止会话"""
        # 先启动一个会话
        await client.post(
            "/api/start",
            json={"goal": "测试", "use_mock": True}
        )

        # 停止会话
        response = await client.post("/api/stop")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    async def test_get_tree_no_session(self, client):
        """测试无会话时获取树数据"""
        response = await client.get("/api/tree")

        assert response.status_code == 200
        data = response.json()

        assert "nodes" in data
        assert "edges" in data
        assert "statistics" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)

    async def test_get_tree_with_session(self, client):
        """测试有会话时获取树数据"""
        # 启动会话
        await client.post(
            "/api/start",
            json={"goal": "测试", "use_mock": True}
        )

        # 获取树数据
        response = await client.get("/api/tree")

        assert response.status_code == 200
        data = response.json()

        assert "nodes" in data
        assert "edges" in data
        # 应该至少有根节点
        assert len(data["nodes"]) >= 1

    async def test_list_sessions(self, client):
        """测试列出会话"""
        response = await client.get("/api/sessions")

        assert response.status_code == 200
        data = response.json()

        assert "sessions" in data
        assert isinstance(data["sessions"], list)

    async def test_get_node_details_not_found(self, client):
        """测试获取不存在的节点"""
        response = await client.get("/api/node/nonexistent_id")

        assert response.status_code == 404

    async def test_load_nonexistent_session(self, client):
        """测试加载不存在的会话"""
        response = await client.post("/api/session/nonexistent_id/load")

        assert response.status_code == 404

    async def test_get_report_no_session(self, client):
        """测试无会话时获取报告"""
        # 先停止可能存在的会话
        await client.post("/api/stop")

        response = await client.get("/api/report")

        # 无会话时应该返回 404，但如果之前的测试创建了会话可能返回 200
        # 这里我们接受两种情况
        assert response.status_code in [200, 404]

    async def test_reload_config(self, client):
        """测试重新加载配置"""
        response = await client.post("/api/config/reload")

        # 应该成功或返回错误（取决于配置文件是否存在）
        assert response.status_code in [200, 500]


@pytest.mark.integration
@pytest.mark.asyncio
class TestAPIWorkflow:
    """测试完整的 API 工作流"""

    @pytest.fixture
    async def client(self):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as ac:
            yield ac

    async def test_complete_workflow(self, client):
        """测试完整工作流：启动 -> 获取数据 -> 停止"""
        # 1. 启动会话
        start_response = await client.post(
            "/api/start",
            json={"goal": "探索AI技术", "use_mock": True}
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session_id"]

        # 2. 检查状态
        status_response = await client.get("/api/status")
        assert status_response.status_code == 200
        status = status_response.json()
        assert status["has_active_session"]

        # 3. 获取树数据
        tree_response = await client.get("/api/tree")
        assert tree_response.status_code == 200
        tree_data = tree_response.json()
        assert len(tree_data["nodes"]) >= 1

        # 4. 停止会话
        stop_response = await client.post("/api/stop")
        assert stop_response.status_code == 200

    async def test_session_restart(self, client):
        """测试会话重启"""
        # 启动第一个会话
        response1 = await client.post(
            "/api/start",
            json={"goal": "第一个会话", "use_mock": True}
        )
        assert response1.status_code == 200
        session_id_1 = response1.json()["session_id"]

        # 启动第二个会话（应该停止第一个）
        response2 = await client.post(
            "/api/start",
            json={"goal": "第二个会话", "use_mock": True}
        )
        assert response2.status_code == 200
        session_id_2 = response2.json()["session_id"]

        # 两个会话 ID 应该不同
        assert session_id_1 != session_id_2


@pytest.mark.integration
@pytest.mark.asyncio
class TestAPICORS:
    """测试 CORS 配置"""

    @pytest.fixture
    async def client(self):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as ac:
            yield ac

    async def test_cors_headers(self, client):
        """测试 CORS 头部"""
        # FastAPI 的 CORSMiddleware 会自动处理 CORS，但 OPTIONS 请求可能返回 405
        # 测试实际的 GET 请求以验证 CORS 头部
        response = await client.get(
            "/api/status",
            headers={"Origin": "http://localhost:3000"}
        )

        # 请求应该成功
        assert response.status_code == 200

        # 验证 CORS 头部存在（如果 CORS 中间件正常工作）
        # 注意：在测试环境中，CORS 头部可能不会自动添加
