from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from src.backend.core.schema import Node, QAInteraction, SessionData
from src.backend.services.errors import ContractError, NotFoundError
from src.backend.services.session_repository import (
    SessionSummaryRecord,
    SqliteSessionRepository,
)


def _build_session(goal: str = "研究目标") -> SessionData:
    session = SessionData(global_goal=goal)
    session.add_node(
        Node(
            id=session.root_node_id,
            depth=0,
            interaction=QAInteraction(question=goal, answer="探索起点"),
        )
    )
    session.bump_session_version()
    return session


@pytest.mark.unit
class TestSqliteSessionRepository:
    @pytest.fixture
    def repository(self, tmp_path: Path) -> SqliteSessionRepository:
        return SqliteSessionRepository(db_path=tmp_path / "sessions.sqlite3")

    @pytest.mark.asyncio
    async def test_get_session_raises_not_found_for_missing_session(self, repository):
        with pytest.raises(NotFoundError):
            await repository.get_session("missing-session")

    @pytest.mark.asyncio
    async def test_delete_session_raises_not_found_for_missing_session(
        self, repository
    ):
        with pytest.raises(NotFoundError):
            await repository.delete_session("missing-session")

    @pytest.mark.asyncio
    async def test_save_and_get_session_roundtrip(self, repository):
        session = _build_session("SQLite roundtrip")

        await repository.save_session(session)
        loaded = await repository.get_session(session.session_id)

        assert loaded.session_id == session.session_id
        assert loaded.global_goal == "SQLite roundtrip"
        assert loaded.session_version == session.session_version

    @pytest.mark.asyncio
    async def test_delete_session_cascades_report_cache(self, repository):
        session = _build_session("级联删除")
        await repository.save_session(session)
        await repository.save_report(
            session.session_id,
            session.session_version,
            {
                "session_id": session.session_id,
                "goal": session.global_goal,
                "generated_at": session.updated_at.isoformat(),
            },
        )

        await repository.delete_session(session.session_id)

        assert await repository.load_report(session.session_id) is None

    async def test_list_sessions_returns_typed_records_sorted_by_updated_at(
        self,
        repository,
    ):
        older = _build_session("较早会话")
        newer = _build_session("较新会话")
        older.created_at = datetime.fromisoformat("2026-04-04T12:00:00")
        older.updated_at = datetime.fromisoformat("2026-04-04T12:05:00")
        newer.created_at = datetime.fromisoformat("2026-04-04T13:00:00")
        newer.updated_at = datetime.fromisoformat("2026-04-04T13:05:00")

        await repository.save_session(older)
        await repository.save_session(newer)

        records = repository.list_sessions()

        assert [record.session_id for record in records] == [
            newer.session_id,
            older.session_id,
        ]
        assert records[0].global_goal == "较新会话"
        assert records[1].global_goal == "较早会话"
        assert records[0].file_size > 0
        assert records[1].file_size > 0

    @pytest.mark.asyncio
    async def test_has_fresh_report_depends_on_session_version(self, repository):
        session = _build_session("报告版本")
        await repository.save_session(session)
        await repository.save_report(
            session.session_id,
            session.session_version,
            {
                "session_id": session.session_id,
                "goal": session.global_goal,
                "generated_at": session.updated_at.isoformat(),
            },
        )

        assert (
            await repository.has_fresh_report(
                session.session_id, session.session_version
            )
            is True
        )
        assert (
            await repository.has_fresh_report(
                session.session_id, session.session_version + 1
            )
            is False
        )

    def test_schema_bootstrap_creates_expected_tables(self, repository, tmp_path: Path):
        db_path = tmp_path / "sessions.sqlite3"
        SqliteSessionRepository(db_path=db_path)

        with sqlite3.connect(db_path) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }

        assert {"sessions", "reports"} <= tables

    def test_list_sessions_raises_contract_error_for_invalid_summary_shape(
        self, tmp_path: Path
    ):
        db_path = tmp_path / "broken.sqlite3"
        repository = SqliteSessionRepository(db_path=db_path)

        with sqlite3.connect(db_path) as connection:
            connection.execute(
                """
                INSERT INTO sessions (
                    session_id,
                    session_json,
                    global_goal,
                    root_node_id,
                    status,
                    error_message,
                    created_at,
                    updated_at,
                    session_version,
                    total_simulations,
                    total_tokens_used,
                    total_nodes,
                    total_facts
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "session-1",
                    "{}",
                    "目标",
                    "root-1",
                    "running",
                    None,
                    "not-a-datetime",
                    "not-a-datetime",
                    1,
                    0,
                    0,
                    0,
                    0,
                ),
            )
            connection.commit()

        with pytest.raises(ContractError):
            repository.list_sessions()
