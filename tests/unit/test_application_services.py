from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from src.backend.core.schema import Node, QAInteraction, SessionData, SessionStatus
from src.backend.llm.usage_tracking import record_usage_for_current_request
from src.backend.services.configuration_service import ConfigurationService
from src.backend.services.coordinator import RuntimeCoordinator
from src.backend.services.errors import NotFoundError, RuntimeConflictError
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
        self.reports.pop(session_id, None)

    def list_sessions(self) -> list[SessionSummaryRecord]:
        return [
            SessionSummaryRecord(
                session_id=session.session_id,
                global_goal=session.global_goal,
                created_at=session.created_at,
                updated_at=session.updated_at,
                status=session.status.value,
                is_legacy_token_accounting=session.is_legacy_token_accounting,
                total_simulations=session.total_simulations,
                total_nodes=session.get_total_nodes(),
                total_facts=len(session.global_facts),
                file_size=0,
            )
            for session in self.sessions.values()
        ]

    async def save_report(
        self, session_id: str, source_session_version: int, report: dict
    ) -> None:
        self.reports[session_id] = {
            "source_session_version": source_session_version,
            "report": report,
        }

    async def load_report(self, session_id: str) -> dict | None:
        record = self.reports.get(session_id)
        if record is None:
            return None
        return SimpleNamespace(**record)

    async def has_fresh_report(self, session_id: str, session_version: int) -> bool:
        record = self.reports.get(session_id)
        if record is None:
            return False
        return record["source_session_version"] == session_version


class FakeCoordinator:
    def __init__(
        self,
        active_session: SessionData | None = None,
        mcts_running: bool = False,
        *,
        single_session_mode: bool = True,
    ):
        self.active_session = active_session
        self.mcts_running = mcts_running
        self.single_session_mode = single_session_mode
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

    async def merge_report_usage(self, *, session_id: str, usage_delta) -> SessionData | None:
        if self.active_session is None or self.active_session.session_id != session_id:
            return None
        self.active_session.merge_llm_usage(usage_delta)
        return self.active_session.model_copy(deep=True)


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
        if callable(self.payload):
            return self.payload(session, self.calls)
        return self.payload


class RecordingUsageIntegrator:
    def __init__(self, tokens_by_model: list[tuple[str, int]]):
        self.tokens_by_model = tokens_by_model
        self.calls = 0

    async def generate_final_report(
        self, session: SessionData, max_facts: int = 50
    ) -> dict:
        del max_facts
        self.calls += 1
        for model, tokens in self.tokens_by_model:
            record_usage_for_current_request(model, tokens)
        return {
            "session_id": session.session_id,
            "goal": session.global_goal,
            "executive_summary": "usage aware report",
            "generated_at": session.updated_at.isoformat(),
        }


class FakeExplodingIntegrator:
    def __init__(self, error: Exception):
        self.error = error
        self.calls = 0

    async def generate_final_report(
        self, session: SessionData, max_facts: int = 50
    ) -> dict:
        self.calls += 1
        raise self.error


class RecordingRepository:
    def __init__(self) -> None:
        self.saved_sessions: list[SessionData] = []

    async def save_session(self, session: SessionData) -> None:
        self.saved_sessions.append(session.model_copy(deep=True))


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
        assert repository.sessions[response.session_id].session_version == 1

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

    async def test_restore_session_bumps_session_version(self):
        session = SessionData(global_goal="旧会话", status=SessionStatus.PAUSED)
        session.add_node(
            Node(
                id=session.root_node_id,
                depth=0,
                interaction=QAInteraction(question="旧会话", answer="探索起点"),
            )
        )
        session.session_version = 2
        repository = FakeRepository(
            sessions={session.session_id: session},
            reports={},
        )
        service = SessionCommandService(
            repository,
            FakeCoordinator(),
            FakeModuleFactory(),
        )

        response = await service.start_session(
            goal="恢复旧会话",
            use_mock=False,
            session_id=session.session_id,
        )

        assert response.session_id == session.session_id
        assert repository.sessions[session.session_id].session_version == 3

    async def test_restore_legacy_session_raises_runtime_conflict(self):
        session = SessionData(global_goal="legacy 会话", status=SessionStatus.PAUSED)
        session.token_accounting_version = 1
        session.add_node(
            Node(
                id=session.root_node_id,
                depth=0,
                interaction=QAInteraction(question="legacy 会话", answer="探索起点"),
            )
        )
        repository = FakeRepository(
            sessions={session.session_id: session},
            reports={},
        )
        service = SessionCommandService(
            repository,
            FakeCoordinator(),
            FakeModuleFactory(),
        )

        with pytest.raises(RuntimeConflictError) as exc_info:
            await service.start_session(
                goal="恢复 legacy",
                use_mock=False,
                session_id=session.session_id,
            )

        assert exc_info.value.code == "legacy_session_resume_unsupported"

    async def test_restore_session_clears_previous_error_message(self):
        session = SessionData(
            global_goal="旧会话",
            status=SessionStatus.ERROR,
            error_message="上次运行失败",
        )
        session.add_node(
            Node(
                id=session.root_node_id,
                depth=0,
                interaction=QAInteraction(question="旧会话", answer="探索起点"),
            )
        )
        repository = FakeRepository(
            sessions={session.session_id: session},
            reports={},
        )
        service = SessionCommandService(
            repository,
            FakeCoordinator(),
            FakeModuleFactory(),
        )

        await service.start_session(
            goal="恢复旧会话",
            use_mock=False,
            session_id=session.session_id,
        )

        restored = repository.sessions[session.session_id]
        assert restored.status == SessionStatus.RUNNING
        assert restored.error_message is None


@pytest.mark.unit
@pytest.mark.asyncio
class TestSessionQueryService:
    async def test_get_status_uses_runtime_single_session_mode(self):
        repository = FakeRepository(sessions={}, reports={})
        service = SessionQueryService(
            repository,
            FakeCoordinator(single_session_mode=False),
        )

        status = await service.get_status()

        assert status.single_session_mode is False

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
            repository.reports[session.session_id]["report"]["error_message"]
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
        assert (
            repository.reports[session.session_id]["report"]["error_message"]
            == "llm exploded"
        )

    async def test_report_service_uses_cached_report_for_same_session_version(self):
        session = SessionData(global_goal="缓存命中")
        session.add_node(
            Node(
                id=session.root_node_id,
                depth=0,
                interaction=QAInteraction(question="root", answer="answer"),
            )
        )
        session.session_version = 4
        cached_generated_at = datetime.now(UTC).isoformat()
        repository = FakeRepository(
            sessions={session.session_id: session},
            reports={
                session.session_id: {
                    "source_session_version": 4,
                    "report": {
                        "session_id": session.session_id,
                        "goal": session.global_goal,
                        "executive_summary": "cached",
                        "generated_at": cached_generated_at,
                    },
                }
            },
        )
        integrator = FakeIntegrator(
            {
                "session_id": session.session_id,
                "goal": session.global_goal,
                "executive_summary": "fresh",
                "generated_at": datetime.now(UTC).isoformat(),
            }
        )
        service = ReportService(
            repository,
            FakeCoordinator(active_session=session),
            FakeModuleFactory(integrator=integrator),
        )

        report = await service.get_report(session.session_id)

        assert report.executive_summary == "cached"
        assert report.generated_at == cached_generated_at
        assert integrator.calls == 0

    async def test_report_service_regenerates_when_session_version_changes(self):
        session = SessionData(global_goal="缓存失效")
        session.add_node(
            Node(
                id=session.root_node_id,
                depth=0,
                interaction=QAInteraction(question="root", answer="answer"),
            )
        )
        session.session_version = 5
        repository = FakeRepository(
            sessions={session.session_id: session},
            reports={
                session.session_id: {
                    "source_session_version": 4,
                    "report": {
                        "session_id": session.session_id,
                        "goal": session.global_goal,
                        "executive_summary": "stale",
                        "generated_at": "2026-04-01T00:00:00+00:00",
                    },
                }
            },
        )
        integrator = FakeIntegrator(
            lambda snapshot, call_count: {
                "session_id": snapshot.session_id,
                "goal": snapshot.global_goal,
                "executive_summary": f"fresh-{call_count}",
                "statistics": {
                    "total_simulations": snapshot.total_simulations,
                    "total_nodes": snapshot.get_total_nodes(),
                    "tree_depth": snapshot.get_tree_depth(),
                    "total_facts": len(snapshot.global_facts),
                    "active_nodes": len(snapshot.get_active_nodes()),
                    "pruned_nodes": 0,
                },
                "generated_at": datetime.now(UTC).isoformat(),
            }
        )
        service = ReportService(
            repository,
            FakeCoordinator(active_session=session),
            FakeModuleFactory(integrator=integrator),
        )

        report = await service.get_report(session.session_id)

        assert report.executive_summary == "fresh-1"
        assert repository.reports[session.session_id]["source_session_version"] == 5
        assert integrator.calls == 1

    async def test_report_service_records_report_generation_usage_in_session_ledger(self):
        session = SessionData(global_goal="统计报告 token")
        session.add_node(
            Node(
                id=session.root_node_id,
                depth=0,
                interaction=QAInteraction(question="root", answer="answer"),
            )
        )
        repository = FakeRepository(sessions={session.session_id: session}, reports={})
        integrator = RecordingUsageIntegrator(
            [
                ("insight-model", 11),
                ("report-model", 13),
                ("summary-model", 17),
                ("suggest-model", 19),
            ]
        )
        service = ReportService(
            repository,
            FakeCoordinator(active_session=session),
            FakeModuleFactory(integrator=integrator),
        )

        report = await service.get_report(session.session_id)

        assert report.llm_stats.total_calls == 4
        assert report.llm_stats.total_tokens == 60
        assert report.llm_stats.usage_by_model["insight-model"].tokens == 11
        assert report.llm_stats.usage_by_model["report-model"].tokens == 13
        assert report.llm_stats.usage_by_model["summary-model"].tokens == 17
        assert report.llm_stats.usage_by_model["suggest-model"].tokens == 19
        assert repository.sessions[session.session_id].total_tokens_used == 60
        assert repository.sessions[session.session_id].llm_usage.total_calls == 4

    async def test_report_service_returns_stable_error_for_legacy_session_without_cached_report(
        self,
    ):
        session = SessionData(global_goal="legacy 报告")
        session.token_accounting_version = 1
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
                "executive_summary": "should not run",
                "generated_at": datetime.now(UTC).isoformat(),
            }
        )
        service = ReportService(
            repository,
            FakeCoordinator(active_session=None),
            FakeModuleFactory(integrator=integrator),
        )

        report = await service.get_report(session.session_id)

        assert report.session_id == session.session_id
        assert report.error_message is not None
        assert "legacy" in report.error_message.lower()
        assert integrator.calls == 0
        assert session.session_id not in repository.reports

    async def test_report_service_does_not_cache_when_session_changes_during_generation(
        self,
    ):
        session = SessionData(global_goal="并发变化")
        session.add_node(
            Node(
                id=session.root_node_id,
                depth=0,
                interaction=QAInteraction(question="root", answer="answer"),
            )
        )
        session.session_version = 2
        repository = FakeRepository(
            sessions={session.session_id: session},
            reports={},
        )

        def payload(snapshot: SessionData, _: int) -> dict:
            session.session_version += 1
            session.total_simulations += 1
            return {
                "session_id": snapshot.session_id,
                "goal": snapshot.global_goal,
                "statistics": {
                    "total_simulations": snapshot.total_simulations,
                    "total_nodes": snapshot.get_total_nodes(),
                    "tree_depth": snapshot.get_tree_depth(),
                    "total_facts": len(snapshot.global_facts),
                    "active_nodes": len(snapshot.get_active_nodes()),
                    "pruned_nodes": 0,
                },
                "generated_at": datetime.now(UTC).isoformat(),
            }

        service = ReportService(
            repository,
            FakeCoordinator(active_session=session),
            FakeModuleFactory(integrator=FakeIntegrator(payload)),
        )

        report = await service.get_report(session.session_id)

        assert report.session_id == session.session_id
        assert session.session_id not in repository.reports


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


@pytest.mark.unit
@pytest.mark.asyncio
class TestRuntimeCoordinator:
    async def test_worker_fatal_error_marks_session_as_error(self, monkeypatch):
        session = SessionData(global_goal="协调器错误传播")
        session.add_node(
            Node(
                id=session.root_node_id,
                depth=0,
                interaction=QAInteraction(
                    question="协调器错误传播",
                    answer="探索起点",
                ),
            )
        )
        repository = RecordingRepository()
        coordinator = RuntimeCoordinator(repository)

        monkeypatch.setattr(
            "src.backend.services.coordinator.get_settings",
            lambda: SimpleNamespace(
                mcts=SimpleNamespace(
                    exploration_constant=1.4,
                    branch_factor=1,
                    max_depth=5,
                    max_simulations=5,
                    save_interval_steps=1,
                    parallel_workers=1,
                )
            ),
        )

        async def crashing_worker(worker_id, worker_session, engine):
            del worker_id, worker_session, engine
            raise RuntimeError("fatal worker crash")

        monkeypatch.setattr(coordinator, "_single_mcts_worker", crashing_worker)

        await coordinator.activate_session(
            session=session,
            modules=SimpleNamespace(
                llm_client=None,
                questioner=None,
                compressor=None,
                pruner=None,
                integrator=None,
            ),
            use_mock=True,
        )

        assert coordinator._mcts_task is not None
        await coordinator._mcts_task

        assert session.status == SessionStatus.ERROR
        assert "fatal worker crash" in (session.error_message or "")
        assert coordinator.mcts_running is False
        assert repository.saved_sessions
        assert repository.saved_sessions[-1].status == SessionStatus.ERROR
