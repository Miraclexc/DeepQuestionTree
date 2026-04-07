from __future__ import annotations

import pytest


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_real_provider_smoke_flow(e2e_server):
    async with e2e_server.create_client() as client:
        status_response = await client.get("/api/status")
        assert status_response.status_code == 200

        start_response = await client.post(
            "/api/start",
            json={
                "goal": "评估多服务商 E2E 测试重构是否工作正常",
                "use_mock": False,
            },
        )
        assert start_response.status_code == 200

        session_id = start_response.json()["session_id"]
        await e2e_server.wait_for_session_completion(session_id)

        session_response = await client.get(f"/api/sessions/{session_id}")
        tree_response = await client.get(f"/api/sessions/{session_id}/tree")
        report_response = await client.get(f"/api/sessions/{session_id}/report")

        assert session_response.status_code == 200
        assert tree_response.status_code == 200
        assert report_response.status_code == 200

        session_payload = session_response.json()
        tree_payload = tree_response.json()
        report_payload = report_response.json()

        assert session_payload["session_id"] == session_id
        assert session_payload["status"] in {"completed", "paused"}
        assert tree_payload["session_id"] == session_id
        assert len(tree_payload["nodes"]) >= 1
        assert report_payload["session_id"] == session_id
        assert "statistics" in report_payload

        assert e2e_server.session_db_path.exists()
        assert e2e_server.has_session_row(session_id) is True
