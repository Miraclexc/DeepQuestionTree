"""
集成测试 - FastAPI API 契约
"""

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
class TestAPIEndpoints:
    async def test_start_session(self, api_client):
        response = await api_client.post(
            "/api/start",
            json={
                "goal": "测试人工智能技术",
                "use_mock": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert data["status"] == "running"

    async def test_get_status(self, api_client):
        response = await api_client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        assert data["single_session_mode"] is True
        assert "has_active_session" in data
        assert "environment" in data

    async def test_list_sessions(self, api_client):
        await api_client.post(
            "/api/start",
            json={"goal": "测试列出会话", "use_mock": True},
        )

        response = await api_client.get("/api/sessions")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert "global_goal" in data[0]

    async def test_get_session_details(self, api_client):
        start_response = await api_client.post(
            "/api/start",
            json={"goal": "测试会话详情", "use_mock": True},
        )
        session_id = start_response.json()["session_id"]

        response = await api_client.get(f"/api/sessions/{session_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert data["global_goal"] == "测试会话详情"

    async def test_get_report_for_session(self, api_client):
        start_response = await api_client.post(
            "/api/start",
            json={"goal": "测试报告接口", "use_mock": True},
        )
        session_id = start_response.json()["session_id"]

        stop_response = await api_client.post("/api/stop")
        assert stop_response.status_code == 200

        report_response = await api_client.get(f"/api/sessions/{session_id}/report")

        assert report_response.status_code == 200
        report = report_response.json()
        assert "full_report" in report
        assert "statistics" in report

    async def test_delete_session(self, api_client):
        start_response = await api_client.post(
            "/api/start",
            json={"goal": "测试删除会话", "use_mock": True},
        )
        session_id = start_response.json()["session_id"]

        delete_response = await api_client.delete(f"/api/sessions/{session_id}")
        assert delete_response.status_code == 204

        get_response = await api_client.get(f"/api/sessions/{session_id}")
        assert get_response.status_code == 404

    async def test_reload_config(self, api_client):
        response = await api_client.post("/api/config/reload")
        assert response.status_code == 200
        assert response.json()["message"] == "配置已重新加载"


@pytest.mark.integration
@pytest.mark.asyncio
class TestAPICORS:
    async def test_cors_headers(self, api_client):
        response = await api_client.get(
            "/api/status",
            headers={"Origin": "http://localhost:3000"},
        )

        assert response.status_code == 200
        assert (
            response.headers.get("access-control-allow-origin")
            == "http://localhost:3000"
        )
