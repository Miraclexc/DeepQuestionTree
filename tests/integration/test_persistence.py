"""
集成测试 - SQLite 持久化模块
测试会话与报告在 SQLite 中的保存、加载和失效行为
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from src.backend.core.schema import Fact, Node, QAInteraction, SessionData
from src.backend.modules.persistence import SessionManager


def _db_row_count(db_path: Path, table: str) -> int:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    assert row is not None
    return int(row[0])


@pytest.mark.integration
class TestPersistence:
    """测试 SQLite 持久化功能"""

    @pytest.fixture
    def db_path(self, temp_session_dir: Path) -> Path:
        return temp_session_dir / "sessions.sqlite3"

    @pytest.fixture
    def session_manager(self, db_path: Path):
        return SessionManager(db_path=db_path)

    @pytest.fixture
    def sample_session_with_data(self):
        session = SessionData(global_goal="测试持久化功能")
        root = Node(
            id=session.root_node_id,
            depth=0,
            interaction=QAInteraction(
                question="测试持久化功能",
                answer="这是一个测试会话",
                summary="测试会话",
            ),
        )
        session.add_node(root)

        child = Node(
            parent_id=root.id,
            depth=1,
            interaction=QAInteraction(
                question="子节点问题",
                answer="子节点回答",
                tokens_used=150,
            ),
        )
        child.state.visit_count = 5
        child.state.value_sum = 35.0
        session.add_node(child)
        root.children_ids.append(child.id)

        fact1 = Fact(content="测试事实1", source_node_id=child.id, confidence=0.9)
        fact2 = Fact(content="测试事实2", source_node_id=child.id, confidence=0.85)
        session.add_global_fact(fact1)
        session.add_global_fact(fact2)

        session.total_simulations = 10
        session.total_tokens_used = 500
        session.session_version = 7

        return session

    async def test_save_session_persists_sqlite_row(
        self,
        session_manager,
        sample_session_with_data,
        db_path: Path,
    ):
        session = sample_session_with_data

        result = await session_manager.save_session(session)

        assert result is True
        assert db_path.exists()
        assert _db_row_count(db_path, "sessions") == 1

    async def test_save_and_load_session(
        self,
        session_manager,
        sample_session_with_data,
    ):
        original_session = sample_session_with_data

        await session_manager.save_session(original_session)
        loaded_session = await session_manager.load_session(original_session.session_id)

        assert loaded_session is not None
        assert loaded_session.session_id == original_session.session_id
        assert loaded_session.global_goal == original_session.global_goal
        assert len(loaded_session.nodes) == len(original_session.nodes)
        assert len(loaded_session.global_facts) == len(original_session.global_facts)
        assert loaded_session.total_simulations == original_session.total_simulations
        assert loaded_session.session_version == 7

    async def test_load_session_recalculates_stale_total_tokens(
        self,
        session_manager,
        sample_session_with_data,
    ):
        session = sample_session_with_data
        session.nodes[session.root_node_id].interaction.tokens_used = 30
        session.total_tokens_used = 999

        await session_manager.save_session(session)
        loaded_session = await session_manager.load_session(session.session_id)

        assert loaded_session is not None
        assert loaded_session.total_tokens_used == 180

    async def test_load_nonexistent_session(self, session_manager):
        result = await session_manager.load_session("nonexistent_session_id")
        assert result is None

    async def test_delete_session_removes_report_cache(
        self,
        session_manager,
        sample_session_with_data,
        db_path: Path,
    ):
        session = sample_session_with_data
        await session_manager.save_session(session)
        await session_manager.save_report(
            session.session_id,
            session.session_version,
            {
                "session_id": session.session_id,
                "goal": session.global_goal,
                "generated_at": session.updated_at.isoformat(),
            },
        )

        result = await session_manager.delete_session(session.session_id)

        assert result is True
        assert _db_row_count(db_path, "sessions") == 0
        assert _db_row_count(db_path, "reports") == 0

    async def test_list_sessions(self, session_manager, sample_session_with_data):
        session1 = sample_session_with_data
        await session_manager.save_session(session1)

        session2 = SessionData(global_goal="第二个测试会话")
        root2 = Node(
            id=session2.root_node_id,
            depth=0,
            interaction=QAInteraction(question="第二个测试会话", answer="探索起点"),
        )
        session2.add_node(root2)
        session2.session_version = 1
        await session_manager.save_session(session2)

        sessions = session_manager.list_sessions()

        assert len(sessions) >= 2
        session_ids = [s["session_id"] for s in sessions]
        assert session1.session_id in session_ids
        assert session2.session_id in session_ids

    async def test_save_report_and_load_report(
        self,
        session_manager,
        sample_session_with_data,
    ):
        session = sample_session_with_data
        await session_manager.save_session(session)

        payload = {
            "session_id": session.session_id,
            "goal": session.global_goal,
            "executive_summary": "SQLite 报告",
            "generated_at": session.updated_at.isoformat(),
        }
        saved = await session_manager.save_report(
            session.session_id,
            session.session_version,
            payload,
        )
        loaded = await session_manager.load_report(session.session_id)

        assert saved is True
        assert loaded is not None
        assert loaded["source_session_version"] == session.session_version
        assert loaded["report"]["executive_summary"] == "SQLite 报告"

    async def test_has_fresh_report_checks_exact_session_version(
        self,
        session_manager,
        sample_session_with_data,
    ):
        session = sample_session_with_data
        await session_manager.save_session(session)
        await session_manager.save_report(
            session.session_id,
            session.session_version,
            {
                "session_id": session.session_id,
                "goal": session.global_goal,
                "generated_at": session.updated_at.isoformat(),
            },
        )

        assert (
            await session_manager.has_fresh_report(
                session.session_id,
                session.session_version,
            )
            is True
        )
        assert (
            await session_manager.has_fresh_report(
                session.session_id,
                session.session_version + 1,
            )
            is False
        )


@pytest.mark.integration
class TestPersistenceEdgeCases:
    @pytest.fixture
    def db_path(self, temp_session_dir: Path) -> Path:
        return temp_session_dir / "sessions.sqlite3"

    @pytest.fixture
    def session_manager(self, db_path: Path):
        return SessionManager(db_path=db_path)

    async def test_save_empty_session(self, session_manager):
        session = SessionData(global_goal="空会话")

        result = await session_manager.save_session(session)
        assert result is True

    async def test_load_invalid_session_payload_returns_none(
        self,
        session_manager,
        db_path: Path,
    ):
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
                    "broken-session",
                    "{invalid-json",
                    "损坏数据",
                    "root",
                    "running",
                    None,
                    "2026-04-04T12:00:00",
                    "2026-04-04T12:00:00",
                    1,
                    0,
                    0,
                    0,
                    0,
                ),
            )
            connection.commit()

        result = await session_manager.load_session("broken-session")
        assert result is None

    async def test_list_sessions_empty_database(self, session_manager):
        sessions = session_manager.list_sessions()

        assert isinstance(sessions, list)
        assert len(sessions) == 0
