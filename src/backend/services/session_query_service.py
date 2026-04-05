from __future__ import annotations

from typing import Any

from ..api.dto import (
    NodeDetailResponse,
    SessionReadModel,
    SessionSummary,
    SystemStatusResponse,
    TreeResponse,
    build_node_detail_response,
    build_session_read_model,
    build_tree_response,
)
from ..config_loader import get_settings
from ..core.schema import SessionData
from .coordinator import RuntimeCoordinator
from .errors import NotFoundError
from .session_repository import SessionRepository


class SessionQueryService:
    """处理会话查询与 read-model 组装。"""

    def __init__(
        self,
        repository: SessionRepository,
        coordinator: RuntimeCoordinator,
    ) -> None:
        self._repository = repository
        self._coordinator = coordinator

    async def get_status(self) -> SystemStatusResponse:
        active_session = self._coordinator.active_session
        response = SystemStatusResponse(
            mcts_running=self._coordinator.mcts_running,
            has_active_session=active_session is not None,
            active_session_id=active_session.session_id if active_session else None,
            environment=get_settings().app.env,
        )

        if active_session is not None:
            response.session_status = active_session.status.value
            response.total_simulations = active_session.total_simulations
            response.tree_depth = active_session.get_tree_depth()
            response.total_nodes = active_session.get_total_nodes()

        return response

    async def list_sessions(self) -> list[SessionSummary]:
        return [
            SessionSummary.model_validate(session.to_dict())
            for session in self._repository.list_sessions()
        ]

    async def get_session(self, session_id: str) -> SessionReadModel:
        session = await self._load_session_for_read(session_id)
        return build_session_read_model(
            session,
            is_active=(
                self._coordinator.active_session is not None
                and self._coordinator.active_session.session_id == session_id
            ),
        )

    async def get_tree(self, session_id: str) -> TreeResponse:
        session = await self._load_session_for_read(session_id)
        statistics = self._coordinator.get_tree_statistics(session)
        return build_tree_response(
            session,
            statistics=statistics or self._build_tree_statistics(session),
        )

    async def get_node_detail(
        self, session_id: str, node_id: str
    ) -> NodeDetailResponse:
        session = await self._load_session_for_read(session_id)
        node = session.get_node(node_id)
        if node is None:
            raise NotFoundError(f"Node {node_id} not found in session {session_id}")
        return build_node_detail_response(session, node)

    async def load_session(self, session_id: str) -> SessionData:
        return await self._load_session_for_read(session_id)

    async def _load_session_for_read(self, session_id: str) -> SessionData:
        active_session = self._coordinator.active_session
        if active_session is not None and active_session.session_id == session_id:
            return active_session

        return await self._repository.get_session(session_id)

    @staticmethod
    def _build_tree_statistics(session: SessionData) -> dict[str, Any]:
        total_nodes = session.get_total_nodes()
        total_visits = sum(node.state.visit_count for node in session.nodes.values())
        return {
            "total_nodes": total_nodes,
            "total_simulations": session.total_simulations,
            "tree_depth": session.get_tree_depth(),
            "active_nodes": len(session.get_active_nodes()),
            "pruned_nodes": sum(1 for node in session.nodes.values() if node.is_pruned),
            "terminal_nodes": sum(
                1 for node in session.nodes.values() if node.is_terminal
            ),
            "total_facts": len(session.global_facts),
            "average_visits": (total_visits / total_nodes) if total_nodes else 0,
        }
