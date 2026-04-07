"""
集成测试 - FastAPI API 契约
"""

import asyncio
from datetime import UTC, datetime

import pytest

from src.backend.modules.integrator import Integrator


async def _wait_for_total_simulations(
    api_client,
    session_id: str,
    minimum: int,
    *,
    timeout_seconds: float = 10.0,
) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    last_payload: dict | None = None
    while asyncio.get_running_loop().time() < deadline:
        response = await api_client.get(f"/api/sessions/{session_id}")
        assert response.status_code == 200
        payload = response.json()
        last_payload = payload
        if int(payload["total_simulations"]) >= minimum:
            return payload
        await asyncio.sleep(0.1)

    raise AssertionError(
        f"session {session_id} did not reach simulations>={minimum}, last={last_payload}"
    )


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

    async def test_report_regenerates_after_running_session_advances(
        self,
        api_client,
        monkeypatch,
    ):
        async def never_prune(*args, **kwargs):
            return False, ""

        async def fake_generate_final_report(self, session, max_facts=50):
            return {
                "session_id": session.session_id,
                "goal": session.global_goal,
                "executive_summary": f"simulations={session.total_simulations}",
                "statistics": {
                    "total_nodes": session.get_total_nodes(),
                    "total_simulations": session.total_simulations,
                    "tree_depth": session.get_tree_depth(),
                    "total_facts": len(session.global_facts),
                    "active_nodes": len(session.get_active_nodes()),
                    "pruned_nodes": sum(
                        1 for node in session.nodes.values() if node.is_pruned
                    ),
                },
                "generated_at": datetime.now(UTC).isoformat(),
            }

        monkeypatch.setattr(
            Integrator,
            "generate_final_report",
            fake_generate_final_report,
        )
        monkeypatch.setattr(
            "src.backend.modules.pruner.Pruner.should_prune",
            never_prune,
        )

        start_response = await api_client.post(
            "/api/start",
            json={"goal": "运行中重新生成报告", "use_mock": True},
        )
        session_id = start_response.json()["session_id"]

        first_session = await _wait_for_total_simulations(api_client, session_id, 1)
        first_report_response = await api_client.get(
            f"/api/sessions/{session_id}/report"
        )
        assert first_report_response.status_code == 200
        first_report = first_report_response.json()

        await _wait_for_total_simulations(
            api_client,
            session_id,
            int(first_report["statistics"]["total_simulations"]) + 1,
        )
        second_report_response = await api_client.get(
            f"/api/sessions/{session_id}/report"
        )
        assert second_report_response.status_code == 200
        second_report = second_report_response.json()

        assert (
            second_report["statistics"]["total_simulations"]
            > first_report["statistics"]["total_simulations"]
        )
        assert second_report["generated_at"] != first_report["generated_at"]

    async def test_report_cache_is_invalidated_after_restoring_session(
        self,
        api_client,
        monkeypatch,
    ):
        async def never_prune(*args, **kwargs):
            return False, ""

        async def fake_generate_final_report(self, session, max_facts=50):
            return {
                "session_id": session.session_id,
                "goal": session.global_goal,
                "executive_summary": (
                    f"version={session.session_version};"
                    f"simulations={session.total_simulations}"
                ),
                "statistics": {
                    "total_nodes": session.get_total_nodes(),
                    "total_simulations": session.total_simulations,
                    "tree_depth": session.get_tree_depth(),
                    "total_facts": len(session.global_facts),
                    "active_nodes": len(session.get_active_nodes()),
                    "pruned_nodes": sum(
                        1 for node in session.nodes.values() if node.is_pruned
                    ),
                },
                "generated_at": datetime.now(UTC).isoformat(),
            }

        monkeypatch.setattr(
            Integrator,
            "generate_final_report",
            fake_generate_final_report,
        )
        monkeypatch.setattr(
            "src.backend.modules.pruner.Pruner.should_prune",
            never_prune,
        )

        start_response = await api_client.post(
            "/api/start",
            json={"goal": "恢复后报告失效", "use_mock": True},
        )
        session_id = start_response.json()["session_id"]
        await _wait_for_total_simulations(api_client, session_id, 1)

        stop_response = await api_client.post("/api/stop")
        assert stop_response.status_code == 200

        first_report_response = await api_client.get(
            f"/api/sessions/{session_id}/report"
        )
        assert first_report_response.status_code == 200
        first_report = first_report_response.json()

        resume_response = await api_client.post(
            "/api/start",
            json={
                "goal": "恢复后报告失效",
                "session_id": session_id,
                "use_mock": True,
            },
        )
        assert resume_response.status_code == 200

        resumed_session_response = await api_client.get(f"/api/sessions/{session_id}")
        assert resumed_session_response.status_code == 200
        resumed_session = resumed_session_response.json()
        assert resumed_session["report_available"] is False

        stop_again_response = await api_client.post("/api/stop")
        assert stop_again_response.status_code == 200

        second_report_response = await api_client.get(
            f"/api/sessions/{session_id}/report"
        )
        assert second_report_response.status_code == 200
        second_report = second_report_response.json()

        assert second_report["executive_summary"] != first_report["executive_summary"]
        assert second_report["generated_at"] != first_report["generated_at"]

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
