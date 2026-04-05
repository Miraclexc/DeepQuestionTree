from __future__ import annotations

from ..api.dto import (
    MessageResponse,
    NodeDetailResponse,
    ReportResponse,
    SessionReadModel,
    SessionSummary,
    StartResponse,
    StopResponse,
    SystemStatusResponse,
    TreeResponse,
)
from .configuration_service import ConfigurationService
from .coordinator import RuntimeCoordinator
from .module_factory import RuntimeModuleFactory
from .report_service import ReportService
from .session_command_service import SessionCommandService
from .session_query_service import SessionQueryService
from .session_repository import JsonSessionRepository, SessionRepository


class ExplorationRuntime:
    """向 FastAPI 暴露的应用层门面。"""

    def __init__(
        self,
        repository: SessionRepository | None = None,
        module_factory: RuntimeModuleFactory | None = None,
    ) -> None:
        self.repository = repository or JsonSessionRepository()
        self.module_factory = module_factory or RuntimeModuleFactory()
        self.coordinator = RuntimeCoordinator(self.repository)
        self.command_service = SessionCommandService(
            self.repository,
            self.coordinator,
            self.module_factory,
        )
        self.query_service = SessionQueryService(
            self.repository,
            self.coordinator,
        )
        self.report_service = ReportService(
            self.repository,
            self.coordinator,
            self.module_factory,
        )
        self.configuration_service = ConfigurationService(
            self.coordinator,
            self.module_factory,
        )

    @property
    def active_session(self):
        return self.coordinator.active_session

    @property
    def _active_session(self):
        return self.coordinator.active_session

    async def shutdown(self) -> None:
        await self.coordinator.shutdown()

    async def start_session(
        self,
        *,
        goal: str,
        use_mock: bool = False,
        session_id: str | None = None,
    ) -> StartResponse:
        return await self.command_service.start_session(
            goal=goal,
            use_mock=use_mock,
            session_id=session_id,
        )

    async def stop_session(self) -> StopResponse:
        return await self.command_service.stop_session()

    async def delete_session(self, session_id: str) -> None:
        await self.command_service.delete_session(session_id)

    async def get_status(self) -> SystemStatusResponse:
        return await self.query_service.get_status()

    async def list_sessions(self) -> list[SessionSummary]:
        return await self.query_service.list_sessions()

    async def get_session(self, session_id: str) -> SessionReadModel:
        return await self.query_service.get_session(session_id)

    async def get_tree(self, session_id: str) -> TreeResponse:
        return await self.query_service.get_tree(session_id)

    async def get_node_detail(
        self, session_id: str, node_id: str
    ) -> NodeDetailResponse:
        return await self.query_service.get_node_detail(session_id, node_id)

    async def get_report(self, session_id: str) -> ReportResponse:
        return await self.report_service.get_report(session_id)

    async def reload_configuration(self) -> MessageResponse:
        return self.configuration_service.reload_configuration()
