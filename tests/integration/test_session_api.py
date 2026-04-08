import pytest

import src.backend.main as main_module
from src.backend.core.schema import Node, QAInteraction, SessionData, SessionStatus


@pytest.mark.integration
@pytest.mark.asyncio
class TestSessionScopedAPI:
    async def test_status_reports_single_session_runtime(self, api_client):
        response = await api_client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        assert data["single_session_mode"] is True
        assert "active_session_id" in data

    async def test_session_scoped_tree_endpoint(self, api_client):
        start_response = await api_client.post(
            "/api/start",
            json={"goal": "测试会话级树接口", "use_mock": True},
        )
        session_id = start_response.json()["session_id"]

        response = await api_client.get(f"/api/sessions/{session_id}/tree")

        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        assert "statistics" in data
        assert len(data["nodes"]) >= 1

    async def test_tree_endpoint_exposes_session_revision(self, api_client):
        session = SessionData(global_goal="树版本号")
        root_node = Node(
            id=session.root_node_id,
            depth=0,
            interaction=QAInteraction(question="树版本号", answer="探索起点"),
        )
        session.add_node(root_node)
        session.session_revision = 7

        repository = main_module.app.state.runtime.repository
        await repository.save_session(session)

        response = await api_client.get(f"/api/sessions/{session.session_id}/tree")

        assert response.status_code == 200
        assert response.json()["session_revision"] == 7

    async def test_status_exposes_active_session_revision_and_error_message(
        self,
        api_client,
    ):
        session = SessionData(
            global_goal="错误状态",
            status=SessionStatus.ERROR,
            error_message="fatal runtime failure",
        )
        session.add_node(
            Node(
                id=session.root_node_id,
                depth=0,
                interaction=QAInteraction(question="错误状态", answer="探索起点"),
            )
        )
        session.session_revision = 11

        runtime = main_module.app.state.runtime
        runtime.coordinator._active_session = session
        runtime.coordinator._mcts_running = False

        response = await api_client.get("/api/status")

        assert response.status_code == 200
        data = response.json()
        assert data["session_revision"] == 11
        assert data["session_error_message"] == "fatal runtime failure"

    async def test_starting_new_session_pauses_previous_session(
        self, api_client, monkeypatch
    ):
        async def never_prune(*args, **kwargs):
            return False, ""

        monkeypatch.setattr(
            "src.backend.modules.pruner.Pruner.should_prune",
            never_prune,
        )

        first = await api_client.post(
            "/api/start",
            json={"goal": "第一个会话", "use_mock": True},
        )
        first_id = first.json()["session_id"]

        second = await api_client.post(
            "/api/start",
            json={"goal": "第二个会话", "use_mock": True},
        )
        second_id = second.json()["session_id"]

        assert first_id != second_id

        response = await api_client.get(f"/api/sessions/{first_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "paused"

    async def test_node_details_are_read_models_and_do_not_mutate_domain_data(
        self, api_client
    ):
        session = SessionData(global_goal="测试节点详情")
        raw_answer = '[{"content":"结构化回答"}]'
        root_node = Node(
            id=session.root_node_id,
            depth=0,
            interaction=QAInteraction(
                question="测试节点详情",
                answer=raw_answer,
                summary="摘要",
            ),
        )
        session.add_node(root_node)
        session.bump_session_version()

        repository = main_module.app.state.runtime.repository
        await repository.save_session(session)

        response = await api_client.get(
            f"/api/sessions/{session.session_id}/nodes/{root_node.id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["interaction"]["answer"] == "结构化回答"

        reloaded = await repository.get_session(session.session_id)
        assert reloaded.nodes[root_node.id].interaction.answer == raw_answer
