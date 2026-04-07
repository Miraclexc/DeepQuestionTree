from __future__ import annotations

from ..api.dto import StartResponse, StopResponse
from ..config_loader import get_settings
from ..core.schema import Node, QAInteraction, SessionData, SessionStatus
from ..utils.logger import get_logger
from .coordinator import RuntimeCoordinator
from .module_factory import RuntimeModuleFactory
from .session_repository import SessionRepository

logger = get_logger(__name__)


class SessionCommandService:
    """处理会话命令操作。"""

    def __init__(
        self,
        repository: SessionRepository,
        coordinator: RuntimeCoordinator,
        module_factory: RuntimeModuleFactory,
    ) -> None:
        self._repository = repository
        self._coordinator = coordinator
        self._module_factory = module_factory

    async def start_session(
        self,
        *,
        goal: str,
        use_mock: bool = False,
        session_id: str | None = None,
    ) -> StartResponse:
        if self._coordinator.mcts_running:
            await self._coordinator.stop(
                status=SessionStatus.PAUSED,
                clear_active=False,
            )

        modules = self._module_factory.build(use_mock=use_mock)

        if session_id:
            session = await self._repository.get_session(session_id)
            session.bump_session_version()
            session.status = SessionStatus.RUNNING
            logger.info("恢复会话: %s", session_id)
        else:
            session = self._create_session(goal)
            logger.info("创建新会话: %s", session.session_id)

        await self._repository.save_session(session)
        await self._coordinator.activate_session(
            session=session,
            modules=modules,
            use_mock=use_mock,
        )

        return StartResponse(
            session_id=session.session_id,
            message="探索已启动",
            status=session.status.value,
        )

    async def stop_session(self) -> StopResponse:
        active_session = self._coordinator.active_session
        if active_session is None:
            return StopResponse(message="没有活跃会话")

        if not self._coordinator.mcts_running:
            return StopResponse(
                message="没有正在运行的探索",
                active_session_id=active_session.session_id,
                status=active_session.status.value,
            )

        await self._coordinator.stop(
            status=SessionStatus.PAUSED,
            clear_active=False,
        )
        active_session = self._coordinator.active_session

        return StopResponse(
            message="探索已停止",
            active_session_id=active_session.session_id if active_session else None,
            status=active_session.status.value if active_session else None,
        )

    async def delete_session(self, session_id: str) -> None:
        active_session = self._coordinator.active_session
        if active_session is not None and active_session.session_id == session_id:
            await self._coordinator.stop(
                status=SessionStatus.PAUSED,
                clear_active=True,
            )

        await self._repository.delete_session(session_id)

    @staticmethod
    def _create_session(goal: str) -> SessionData:
        session = SessionData(
            global_goal=goal,
            status=SessionStatus.RUNNING,
            mcts_config=get_settings().mcts.model_dump(),
            error_message=None,
        )
        root_node = Node(
            id=session.root_node_id,
            parent_id=None,
            depth=0,
            prune_reason=None,
            interaction=QAInteraction(
                question=goal,
                answer="探索起点",
                summary="用户提出的问题",
                model_used="System",
            ),
        )
        session.add_node(root_node)
        session.bump_session_version()
        return session
