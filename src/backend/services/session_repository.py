from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Protocol

from ..core.schema import CURRENT_TOKEN_ACCOUNTING_VERSION, SessionData
from ..modules.persistence import SessionManager, get_session_manager
from .errors import ContractError, NotFoundError, PersistenceError


@dataclass(frozen=True, slots=True)
class SessionSummaryRecord:
    session_id: str
    global_goal: str
    created_at: datetime
    updated_at: datetime
    status: str
    is_legacy_token_accounting: bool
    total_simulations: int
    total_nodes: int
    total_facts: int
    file_size: int

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> SessionSummaryRecord:
        try:
            return cls(
                session_id=_require_str(payload, "session_id"),
                global_goal=_require_str(payload, "global_goal"),
                created_at=_parse_datetime(payload.get("created_at"), "created_at"),
                updated_at=_parse_datetime(payload.get("updated_at"), "updated_at"),
                status=_require_str(payload, "status"),
                is_legacy_token_accounting=_require_int(
                    payload.get("token_accounting_version"),
                    "token_accounting_version",
                )
                < CURRENT_TOKEN_ACCOUNTING_VERSION,
                total_simulations=_require_int(
                    payload.get("total_simulations"), "total_simulations"
                ),
                total_nodes=_require_int(payload.get("total_nodes"), "total_nodes"),
                total_facts=_require_int(payload.get("total_facts"), "total_facts"),
                file_size=_require_int(payload.get("file_size"), "file_size"),
            )
        except ContractError:
            raise
        except Exception as exc:  # pragma: no cover - 防御性边界
            raise ContractError(
                "Session summary payload is invalid",
                status_code=500,
            ) from exc

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "global_goal": self.global_goal,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "is_legacy_token_accounting": self.is_legacy_token_accounting,
            "total_simulations": self.total_simulations,
            "total_nodes": self.total_nodes,
            "total_facts": self.total_facts,
            "file_size": self.file_size,
        }


@dataclass(frozen=True, slots=True)
class StoredReportRecord:
    session_id: str
    source_session_version: int
    generated_at: str
    report: dict[str, Any]

    @classmethod
    def from_payload(
        cls,
        session_id: str,
        payload: Mapping[str, Any],
    ) -> StoredReportRecord:
        report_payload = payload.get("report")
        if not isinstance(report_payload, Mapping):
            raise ContractError(
                "Stored report payload is invalid",
                status_code=500,
            )

        return cls(
            session_id=session_id,
            source_session_version=_require_int(
                payload.get("source_session_version"),
                "source_session_version",
            ),
            generated_at=_require_str(payload, "generated_at"),
            report=dict(report_payload),
        )


class SessionRepository(Protocol):
    async def save_session(self, session: SessionData) -> None: ...

    async def get_session(self, session_id: str) -> SessionData: ...

    async def delete_session(self, session_id: str) -> None: ...

    def list_sessions(self) -> list[SessionSummaryRecord]: ...

    async def save_report(
        self,
        session_id: str,
        source_session_version: int,
        report: dict[str, Any],
    ) -> None: ...

    async def load_report(self, session_id: str) -> StoredReportRecord | None: ...

    async def has_fresh_report(self, session_id: str, session_version: int) -> bool: ...


class SqliteSessionRepository:
    """基于 SQLite 的仓储实现。"""

    def __init__(
        self,
        manager: SessionManager | None = None,
        *,
        db_path: str | Path | None = None,
    ) -> None:
        if manager is not None:
            self._manager = manager
        elif db_path is not None:
            self._manager = SessionManager(db_path=db_path)
        else:
            self._manager = get_session_manager()

    async def save_session(self, session: SessionData) -> None:
        saved = await self._manager.save_session(session)
        if not saved:
            raise PersistenceError(f"保存会话失败: {session.session_id}")

    async def get_session(self, session_id: str) -> SessionData:
        session = await self._manager.load_session(session_id)
        if session is None:
            raise NotFoundError(f"Session {session_id} not found")
        return session

    async def delete_session(self, session_id: str) -> None:
        deleted = await self._manager.delete_session(session_id)
        if not deleted:
            raise NotFoundError(f"Session {session_id} not found")

    def list_sessions(self) -> list[SessionSummaryRecord]:
        return [
            SessionSummaryRecord.from_payload(session)
            for session in self._manager.list_sessions()
        ]

    async def save_report(
        self,
        session_id: str,
        source_session_version: int,
        report: dict[str, Any],
    ) -> None:
        saved = await self._manager.save_report(
            session_id,
            source_session_version,
            report,
        )
        if not saved:
            raise PersistenceError(f"保存报告失败: {session_id}")

    async def load_report(self, session_id: str) -> StoredReportRecord | None:
        payload = await self._manager.load_report(session_id)
        if payload is None:
            return None
        return StoredReportRecord.from_payload(session_id, payload)

    async def has_fresh_report(self, session_id: str, session_version: int) -> bool:
        return await self._manager.has_fresh_report(session_id, session_version)


def _require_str(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if isinstance(value, str) and value.strip():
        return value
    raise ContractError(
        f"Session summary field '{key}' is invalid",
        status_code=500,
    )


def _require_int(value: Any, key: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ContractError(
            f"Session summary field '{key}' is invalid",
            status_code=500,
        ) from exc


def _parse_datetime(value: Any, key: str) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError as exc:
            raise ContractError(
                f"Session summary field '{key}' is invalid",
                status_code=500,
            ) from exc
    raise ContractError(
        f"Session summary field '{key}' is invalid",
        status_code=500,
    )
