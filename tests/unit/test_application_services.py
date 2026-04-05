from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from src.backend.core.schema import Node, QAInteraction, SessionData, SessionStatus
from src.backend.services.configuration_service import ConfigurationService
from src.backend.services.errors import NotFoundError
from src.backend.services.report_service import ReportService
from src.backend.services.session_command_service import SessionCommandService
from src.backend.services.session_query_service import SessionQueryService
from src.backend.services.session_repository import SessionSummaryRecord


@dataclass
class FakeRepository:
    sessions: dict[str, SessionData]
    reports: dict[str, dict]

    async def save_session(self, session: SessionData) -> None:
        self.sessions[session.session_id] = session

    async def get_session(self, session_id: str) -> SessionData:
        session = self.sessions.get(session_id)
        if session is None:
            raise NotFoundError(f"Session {session_id} not found")
        return session

    async def delete_session(self, session_id: str) -> None:
        if self.sessions.pop(session_id, None) is None:
            raise NotFoundError(f"Session {session_id} not found")

    def list_sessions(self) -> list[SessionSummaryRecord]:
        return [
            SessionSummaryRecord(
                session_id=session.session_id,
                global_goal=session.global_goal,
                created_at=session.created_at,
                updated_at=session.updated_at,
                status=session.status.value,
                total_simulations=session.total_simulations,
                total_nodes=session.get_total_nodes(),
                total_facts=len(session.global_facts),
                file_size=0,
            )
            for session in self.sessions.values()
        ]

    async def save_report(self, session_id: str, report: dict) -> None:
        self.reports[session_id] = report

    async def load_report(self, session_id: str) -> dict | None:
        return self.reports.get(session_id)


class FakeCoordinator:
    def __init__(
        self, active_session: SessionData | None = None, mcts_running: bool = False
    ):
        self.active_session = active_session
        self.mcts_running = mcts_running
        self.use_mock = False
        self.integrator = None
        self.stopped_with: SessionStatus | None = None
        self.cleared_active = False
        self.activated_session: SessionData | None = None
        self.reconfigured_with = None

    async def stop(self, *, status: SessionStatus, clear_active: bool) -> None:
        self.stopped_with = status
        self.mcts_running = False
        if self.active_session is not None:
            self.active_session.status = status
        if clear_active:
            self.active_session = None
            self.cleared_active = True

    async def activate_session(
        self,
        *,
        session: SessionData,
        modules,
        use_mock: bool,
    ) -> None:
        self.active_session = session
        self.activated_session = session
        self.integrator = modules.integrator
        self.use_mock = use_mock
        self.mcts_running = True

    def get_tree_statistics(self, session: SessionData) -> dict[str, int] | None:
        if self.active_session and self.active_session.session_id == session.session_id:
            return {"total_nodes": session.get_total_nodes()}
        return None

    def reconfigure(self, modules) -> None:
        self.reconfigured_with = modules
        self.integrator = modules.integrator


class FakeModuleFactory:
    def __init__(self, integrator=None):
        self.integrator = integrator or SimpleNamespace(generate_final_report=None)
        self.calls: list[bool] = []

    def build(self, *, use_mock: bool):
        self.calls.append(use_mock)
        return SimpleNamespace(
            integrator=self.integrator,
        )


class FakeIntegrator:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls = 0

    async def generate_final_report(
        self, session: SessionData, max_facts: int = 50
    ) -> dict:
        self.calls += 1
        return self.payload


class FakeExplodingIntegrator:
    def __init__(self, error: Exception):
        self.error = error
        self.calls = 0

    async def generate_final_report(
        self, session: SessionData, max_facts: int = 50
    ) -> dict:
        self.calls += 1
        raise self.error


@pytest.mark.unit
@pytest.mark.asyncio
class TestSessionCommandService:
    async def test_start_session_pauses_previous_active_session(self, monkeypatch):
        previous_session = SessionData(
            global_goal="旧会话", status=SessionStatus.RUNNING
        )
        repository = FakeRepository(sessions={}, reports={})
        coordinator = FakeCoordinator(
            active_session=previous_session, mcts_running=True
        )
        module_factory = FakeModuleFactory()
        service = SessionCommandService(repository, coordinator, module_factory)

        monkeypatch.setattr(
            "src.backend.services.session_command_service.get_settings",
            lambda: SimpleNamespace(
                mcts=SimpleNamespace(model_dump=lambda: {"max_depth": 10})
            ),
        )

        response = await service.start_session(goal="新会话", use_mock=True)

        assert response.status == "running"
        assert coordinator.stopped_with == SessionStatus.PAUSED
        assert coordinator.activated_session is not None
        assert repository.sessions[response.session_id].global_goal == "新会话"

    async def test_restore_missing_session_raises_not_found(self):
        service = SessionCommandService(
            FakeRepository(sessions={}, reports={}),
            FakeCoordinator(),
            FakeModuleFactory(),
        )

        with pytest.raises(NotFoundError):
            await service.start_session(
                goal="恢复不存在会话",
                use_mock=False,
                session_id="missing-session",
            )


@pytest.mark.unit
@pytest.mark.asyncio
class TestSessionQueryService:
    async def test_get_node_detail_raises_not_found_for_unknown_node(self):
        session = SessionData(global_goal="测试节点查询")
        session.add_node(
            Node(
                id=session.root_node_id,
                depth=0,
                interaction=QAInteraction(question="root", answer="answer"),
            )
        )
        repository = FakeRepository(sessions={session.session_id: session}, reports={})
        service = SessionQueryService(
            repository, FakeCoordinator(active_session=session)
        )

        with pytest.raises(NotFoundError):
            await service.get_node_detail(session.session_id, "missing-node")


@pytest.mark.unit
@pytest.mark.asyncio
class TestReportService:
    async def test_report_service_normalizes_error_payload(self):
        session = SessionData(global_goal="测试报告归一化")
        session.add_node(
            Node(
                id=session.root_node_id,
                depth=0,
                interaction=QAInteraction(question="root", answer="answer"),
            )
        )
        repository = FakeRepository(sessions={session.session_id: session}, reports={})
        integrator = FakeIntegrator(
            {
                "session_id": session.session_id,
                "goal": session.global_goal,
                "error": "report generation failed",
                "partial_data": {
                    "facts_count": 0,
                    "nodes_count": 1,
                    "simulations": 0,
                },
                "generated_at": session.updated_at.isoformat(),
            }
        )
        service = ReportService(
            repository,
            FakeCoordinator(active_session=session),
            FakeModuleFactory(integrator=integrator),
        )

        report = await service.get_report(session.session_id)

        assert report.session_id == session.session_id
        assert report.error_message == "report generation failed"
        assert report.statistics.total_nodes == 1
        assert report.llm_stats.usage_by_model == {}
        assert report.key_insights == []
        assert (
            repository.reports[session.session_id]["error_message"]
            == "report generation failed"
        )

    async def test_report_service_returns_stable_report_when_generation_raises(self):
        session = SessionData(global_goal="测试报告异常")
        session.add_node(
            Node(
                id=session.root_node_id,
                depth=0,
                interaction=QAInteraction(question="root", answer="answer"),
            )
        )
        repository = FakeRepository(sessions={session.session_id: session}, reports={})
        integrator = FakeExplodingIntegrator(RuntimeError("llm exploded"))
        service = ReportService(
            repository,
            FakeCoordinator(active_session=session),
            FakeModuleFactory(integrator=integrator),
        )

        report = await service.get_report(session.session_id)

        assert report.session_id == session.session_id
        assert report.error_message == "llm exploded"
        assert report.statistics.total_nodes == 1
        assert report.suggestions == []
        assert repository.reports[session.session_id]["error_message"] == "llm exploded"


@pytest.mark.unit
class TestConfigurationService:
    def test_reload_configuration_rebuilds_modules(self, monkeypatch):
        coordinator = FakeCoordinator()
        module_factory = FakeModuleFactory()
        service = ConfigurationService(coordinator, module_factory)
        reloaded = {"value": False}

        def fake_reload_settings():
            reloaded["value"] = True
            return object()

        monkeypatch.setattr(
            "src.backend.services.configuration_service.reload_settings",
            fake_reload_settings,
        )
        monkeypatch.setattr(
            "src.backend.services.configuration_service.setup_logging",
            lambda: None,
        )

        message = service.reload_configuration()

        assert reloaded["value"] is True
        assert module_factory.calls == [False]
        assert coordinator.reconfigured_with is not None
        assert message.message == "配置已重新加载"
