import pytest

from src.backend.modules.integrator import Integrator


@pytest.mark.integration
@pytest.mark.asyncio
class TestReportContract:
    async def test_report_endpoint_returns_stable_shape_on_generation_error(
        self,
        api_client,
        monkeypatch,
    ):
        async def fake_generate_final_report(self, session, max_facts=50):
            return {
                "session_id": session.session_id,
                "goal": session.global_goal,
                "error": "report generation failed",
                "partial_data": {
                    "facts_count": len(session.global_facts),
                    "nodes_count": len(session.nodes),
                    "simulations": session.total_simulations,
                },
                "generated_at": session.updated_at.isoformat(),
            }

        monkeypatch.setattr(
            Integrator,
            "generate_final_report",
            fake_generate_final_report,
        )

        start_response = await api_client.post(
            "/api/start",
            json={"goal": "测试报告契约错误归一化", "use_mock": True},
        )
        session_id = start_response.json()["session_id"]

        stop_response = await api_client.post("/api/stop")
        assert stop_response.status_code == 200

        report_response = await api_client.get(f"/api/sessions/{session_id}/report")

        assert report_response.status_code == 200
        data = report_response.json()
        assert data["session_id"] == session_id
        assert data["error_message"] == "report generation failed"
        assert "statistics" in data
        assert "llm_stats" in data
        assert isinstance(data["key_insights"], list)
        assert isinstance(data["pruned_insights"], list)
        assert isinstance(data["suggestions"], list)
        assert data["llm_stats"]["usage_by_model"] == {}
