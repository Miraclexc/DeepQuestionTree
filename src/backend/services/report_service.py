from __future__ import annotations

from datetime import UTC, datetime

from ..api.dto import ReportResponse, build_report_response
from ..config_loader import get_settings
from ..core.schema import SessionData
from ..utils.logger import get_logger
from .coordinator import RuntimeCoordinator
from .errors import ReportGenerationError
from .module_factory import RuntimeModuleFactory
from .session_query_service import SessionQueryService
from .session_repository import SessionRepository

logger = get_logger(__name__)


class ReportService:
    """负责报告查询、生成与契约归一化。"""

    def __init__(
        self,
        repository: SessionRepository,
        coordinator: RuntimeCoordinator,
        module_factory: RuntimeModuleFactory,
    ) -> None:
        self._repository = repository
        self._coordinator = coordinator
        self._module_factory = module_factory
        self._query_service = SessionQueryService(repository, coordinator)

    async def get_report(self, session_id: str) -> ReportResponse:
        session = await self._query_service.load_session(session_id)
        cached_report = await self._repository.load_report(session_id)
        if cached_report is not None:
            return build_report_response(session, cached_report)

        try:
            raw_report = await self._generate_report_payload(session_id, session)
            normalized = build_report_response(session, raw_report)
        except ReportGenerationError as exc:
            logger.warning(
                "报告生成失败，返回稳定 DTO: session_id=%s detail=%s",
                session_id,
                exc.detail,
            )
            normalized = build_report_response(
                session,
                {
                    "session_id": session.session_id,
                    "goal": session.global_goal,
                    "generated_at": datetime.now(UTC).isoformat(),
                    "error_message": exc.detail,
                },
            )

        await self._repository.save_report(
            session_id,
            normalized.model_dump(mode="json"),
        )
        return normalized

    def _resolve_integrator(self, session_id: str):
        active_session = self._coordinator.active_session
        if (
            active_session is not None
            and active_session.session_id == session_id
            and self._coordinator.integrator is not None
        ):
            return self._coordinator.integrator

        modules = self._module_factory.build(
            use_mock=self._coordinator.use_mock or get_settings().app.mock_llm
        )
        return modules.integrator

    async def _generate_report_payload(
        self,
        session_id: str,
        session: SessionData,
    ) -> dict[str, object]:
        integrator = self._resolve_integrator(session_id)
        try:
            return await integrator.generate_final_report(session)
        except (
            Exception
        ) as exc:  # pragma: no cover - exercised via service-level behavior
            message = str(exc).strip() or "Failed to generate report"
            raise ReportGenerationError(message) from exc
