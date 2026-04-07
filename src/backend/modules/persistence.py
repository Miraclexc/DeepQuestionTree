"""
SQLite 持久化模块
负责会话与报告缓存的保存、加载和查询
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

from ..config_loader import get_settings
from ..core.schema import SessionData
from ..utils.logger import get_logger

logger = get_logger(__name__)

SCHEMA_VERSION = 1


class SessionManager:
    """
    SQLite 会话管理器
    负责会话和报告缓存的持久化存储与恢复
    """

    def __init__(self, db_path: str | Path | None = None):
        self.settings = get_settings()
        configured_path = db_path or self.settings.storage.session_db_path
        self.db_path = Path(configured_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    async def save_session(self, session: SessionData) -> bool:
        return await asyncio.to_thread(self._save_session_sync, session)

    def _save_session_sync(self, session: SessionData) -> bool:
        try:
            session_json = session.model_dump_json(ensure_ascii=False)
            payload = (
                session.session_id,
                session_json,
                session.global_goal,
                session.root_node_id,
                (
                    session.status.value
                    if hasattr(session.status, "value")
                    else str(session.status)
                ),
                session.error_message,
                session.created_at.isoformat(),
                session.updated_at.isoformat(),
                session.session_version,
                session.total_simulations,
                session.total_tokens_used,
                session.get_total_nodes(),
                len(session.global_facts),
            )
            with self._connect() as connection:
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
                    ON CONFLICT(session_id) DO UPDATE SET
                        session_json = excluded.session_json,
                        global_goal = excluded.global_goal,
                        root_node_id = excluded.root_node_id,
                        status = excluded.status,
                        error_message = excluded.error_message,
                        created_at = excluded.created_at,
                        updated_at = excluded.updated_at,
                        session_version = excluded.session_version,
                        total_simulations = excluded.total_simulations,
                        total_tokens_used = excluded.total_tokens_used,
                        total_nodes = excluded.total_nodes,
                        total_facts = excluded.total_facts
                    """,
                    payload,
                )
                connection.commit()
            logger.info("会话 %s 已保存到 SQLite", session.session_id)
            return True
        except Exception as exc:  # pragma: no cover - 由上层仓储转换
            logger.error("保存会话失败: %s", exc)
            return False

    async def load_session(self, session_id: str) -> Optional[SessionData]:
        return await asyncio.to_thread(self._load_session_sync, session_id)

    def _load_session_sync(self, session_id: str) -> Optional[SessionData]:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT session_json FROM sessions WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
            if row is None:
                logger.warning("会话不存在: %s", session_id)
                return None

            session_data = json.loads(row["session_json"])
            session = SessionData.model_validate(session_data)
            logger.info("会话 %s 已从 SQLite 加载", session_id)
            return session
        except json.JSONDecodeError as exc:
            logger.error("会话 JSON 格式错误: %s", exc)
            return None
        except Exception as exc:  # pragma: no cover - 防御性日志
            logger.error("加载会话失败: %s", exc)
            return None

    async def delete_session(self, session_id: str) -> bool:
        return await asyncio.to_thread(self._delete_session_sync, session_id)

    def _delete_session_sync(self, session_id: str) -> bool:
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    "DELETE FROM sessions WHERE session_id = ?",
                    (session_id,),
                )
                connection.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info("会话 %s 已删除", session_id)
            else:
                logger.warning("会话不存在: %s", session_id)
            return deleted
        except Exception as exc:  # pragma: no cover - 防御性日志
            logger.error("删除会话失败: %s", exc)
            return False

    def list_sessions(self) -> list[dict[str, Any]]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT
                        session_id,
                        global_goal,
                        created_at,
                        updated_at,
                        status,
                        total_simulations,
                        total_nodes,
                        total_facts,
                        length(CAST(session_json AS BLOB)) AS file_size
                    FROM sessions
                    ORDER BY updated_at DESC
                    """
                ).fetchall()
            return [dict(row) for row in rows]
        except Exception as exc:  # pragma: no cover - 防御性日志
            logger.error("列出会话失败: %s", exc)
            return []

    async def save_report(
        self,
        session_id: str,
        source_session_version: int,
        report_data: dict[str, Any],
    ) -> bool:
        return await asyncio.to_thread(
            self._save_report_sync,
            session_id,
            source_session_version,
            report_data,
        )

    def _save_report_sync(
        self,
        session_id: str,
        source_session_version: int,
        report_data: dict[str, Any],
    ) -> bool:
        try:
            report_json = json.dumps(report_data, ensure_ascii=False)
            generated_at = str(report_data.get("generated_at") or "")
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO reports (
                        session_id,
                        source_session_version,
                        report_json,
                        generated_at
                    )
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        source_session_version = excluded.source_session_version,
                        report_json = excluded.report_json,
                        generated_at = excluded.generated_at
                    """,
                    (
                        session_id,
                        source_session_version,
                        report_json,
                        generated_at,
                    ),
                )
                connection.commit()
            logger.info(
                "会话 %s 的报告缓存已保存到 SQLite (version=%s)",
                session_id,
                source_session_version,
            )
            return True
        except Exception as exc:  # pragma: no cover - 由上层仓储转换
            logger.error("保存报告失败: %s", exc)
            return False

    async def load_report(self, session_id: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._load_report_sync, session_id)

    def _load_report_sync(self, session_id: str) -> dict[str, Any] | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT source_session_version, report_json, generated_at
                    FROM reports
                    WHERE session_id = ?
                    """,
                    (session_id,),
                ).fetchone()
            if row is None:
                return None
            return {
                "source_session_version": int(row["source_session_version"]),
                "generated_at": row["generated_at"],
                "report": json.loads(row["report_json"]),
            }
        except Exception as exc:  # pragma: no cover - 防御性日志
            logger.error("加载报告失败: %s", exc)
            return None

    async def has_fresh_report(self, session_id: str, session_version: int) -> bool:
        return await asyncio.to_thread(
            self._has_fresh_report_sync,
            session_id,
            session_version,
        )

    def _has_fresh_report_sync(self, session_id: str, session_version: int) -> bool:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT 1
                    FROM reports
                    WHERE session_id = ? AND source_session_version = ?
                    """,
                    (session_id, session_version),
                ).fetchone()
            return row is not None
        except Exception as exc:  # pragma: no cover - 防御性日志
            logger.error("检查报告缓存失败: %s", exc)
            return False

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            current_version = int(
                connection.execute("PRAGMA user_version").fetchone()[0]
            )
            if current_version not in (0, SCHEMA_VERSION):
                raise RuntimeError(
                    f"Unsupported SQLite schema version: {current_version}"
                )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    session_json TEXT NOT NULL,
                    global_goal TEXT NOT NULL,
                    root_node_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    session_version INTEGER NOT NULL,
                    total_simulations INTEGER NOT NULL,
                    total_tokens_used INTEGER NOT NULL,
                    total_nodes INTEGER NOT NULL,
                    total_facts INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    session_id TEXT PRIMARY KEY,
                    source_session_version INTEGER NOT NULL,
                    report_json TEXT NOT NULL,
                    generated_at TEXT NOT NULL,
                    FOREIGN KEY (session_id)
                        REFERENCES sessions(session_id)
                        ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_reports_session_version ON reports(session_id, source_session_version)"
            )
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
