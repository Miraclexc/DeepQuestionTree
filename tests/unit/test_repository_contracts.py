from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from types import SimpleNamespace

import pytest

from src.backend.core.schema import SessionData, SessionStatus
from src.backend.services.coordinator import RuntimeCoordinator
from src.backend.services.errors import (
    ContractError,
    NotFoundError,
    RuntimeConflictError,
)
from src.backend.services.session_repository import (
    JsonSessionRepository,
    SessionSummaryRecord,
)


@dataclass
class FakeSessionManager:
    loaded_session: SessionData | None = None
    delete_result: bool = True
    session_rows: list[dict[str, object]] = field(default_factory=list)

    async def save_session(self, session: SessionData) -> bool:
        self.loaded_session = session
        return True

    async def load_session(self, session_id: str) -> SessionData | None:
        if self.loaded_session and self.loaded_session.session_id == session_id:
            return self.loaded_session
        return None

    async def delete_session(self, session_id: str) -> bool:
        return self.delete_result

    def list_sessions(self) -> list[dict[str, object]]:
        return self.session_rows

    async def save_report(self, session_id: str, report: dict[str, object]) -> bool:
        return True

    async def load_report(self, session_id: str) -> dict[str, object] | None:
        return None


@pytest.mark.unit
class TestJsonSessionRepository:
    @pytest.mark.asyncio
    async def test_get_session_raises_not_found_for_missing_session(self):
        repository = JsonSessionRepository(
            manager=FakeSessionManager(loaded_session=None)
        )

        with pytest.raises(NotFoundError):
            await repository.get_session("missing-session")

    @pytest.mark.asyncio
    async def test_delete_session_raises_not_found_for_missing_session(self):
        repository = JsonSessionRepository(
            manager=FakeSessionManager(delete_result=False),
        )

        with pytest.raises(NotFoundError):
            await repository.delete_session("missing-session")

    def test_list_sessions_returns_typed_records(self):
        row = {
            "session_id": "session-1",
            "global_goal": "研究目标",
            "created_at": "2026-04-04T12:00:00",
            "updated_at": "2026-04-04T12:05:00",
            "status": "paused",
            "total_simulations": 7,
            "total_nodes": 3,
            "total_facts": 2,
            "file_size": 512,
        }
        repository = JsonSessionRepository(
            manager=FakeSessionManager(session_rows=[row]),
        )

        records = repository.list_sessions()

        assert records == [
            SessionSummaryRecord(
                session_id="session-1",
                global_goal="研究目标",
                created_at=datetime.fromisoformat("2026-04-04T12:00:00"),
                updated_at=datetime.fromisoformat("2026-04-04T12:05:00"),
                status="paused",
                total_simulations=7,
                total_nodes=3,
                total_facts=2,
                file_size=512,
            )
        ]

    def test_list_sessions_raises_contract_error_for_invalid_summary_shape(self):
        repository = JsonSessionRepository(
            manager=FakeSessionManager(
                session_rows=[
                    {
                        "session_id": "session-1",
                        "updated_at": "invalid-date",
                    }
                ]
            ),
        )

        with pytest.raises(ContractError):
            repository.list_sessions()


@pytest.mark.unit
@pytest.mark.asyncio
class TestRuntimeCoordinatorConflicts:
    async def test_activate_session_rejects_parallel_active_session(self, monkeypatch):
        repository = SimpleNamespace(save_session=None)
        coordinator = RuntimeCoordinator(repository=repository)
        active_session = SessionData(
            global_goal="进行中的会话", status=SessionStatus.RUNNING
        )
        next_session = SessionData(global_goal="新的会话", status=SessionStatus.RUNNING)

        coordinator._active_session = active_session
        coordinator._mcts_running = True

        monkeypatch.setattr(
            coordinator,
            "_build_engine",
            lambda session, modules: object(),
        )

        def fake_create_task(coro, *, name=None):
            coro.close()
            return SimpleNamespace(cancel=lambda: None)

        monkeypatch.setattr(asyncio, "create_task", fake_create_task)

        with pytest.raises(RuntimeConflictError):
            await coordinator.activate_session(
                session=next_session,
                modules=SimpleNamespace(
                    questioner=object(),
                    pruner=object(),
                    compressor=object(),
                    integrator=object(),
                ),
                use_mock=False,
            )
