from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from datetime import datetime

from ..config_loader import get_settings
from ..core.mcts_engine import MCTSEngine
from ..core.schema import SessionData, SessionStatus
from ..utils.logger import get_logger, session_id_ctx
from .errors import RuntimeConflictError
from .module_factory import RuntimeModules
from .session_repository import SessionRepository

logger = get_logger(__name__)


class RuntimeCoordinator:
    """仅负责活跃会话与后台 MCTS 生命周期。"""

    single_session_mode = True

    def __init__(self, repository: SessionRepository) -> None:
        self._repository = repository
        self._state_lock = asyncio.Lock()
        self._commit_lock = asyncio.Lock()
        self._active_session: SessionData | None = None
        self._modules: RuntimeModules | None = None
        self._mcts_engine: MCTSEngine | None = None
        self._mcts_task: asyncio.Task[None] | None = None
        self._mcts_running = False
        self._use_mock = False

    @property
    def active_session(self) -> SessionData | None:
        return self._active_session

    @property
    def mcts_running(self) -> bool:
        return self._mcts_running

    @property
    def use_mock(self) -> bool:
        return self._use_mock

    @property
    def modules(self) -> RuntimeModules | None:
        return self._modules

    @property
    def integrator(self):
        return self._modules.integrator if self._modules is not None else None

    async def activate_session(
        self,
        *,
        session: SessionData,
        modules: RuntimeModules,
        use_mock: bool,
    ) -> None:
        async with self._state_lock:
            if (
                self._active_session is not None
                and self._active_session.session_id != session.session_id
                and (self._mcts_running or self._mcts_task is not None)
            ):
                raise RuntimeConflictError(
                    (
                        "Cannot activate a new session while another session "
                        f"({self._active_session.session_id}) is still running"
                    )
                )

            self._modules = modules
            self._use_mock = use_mock
            self._active_session = session
            self._mcts_engine = self._build_engine(session, modules)
            self._mcts_running = True
            self._mcts_task = asyncio.create_task(
                self._run_mcts_loop(session, self._mcts_engine),
                name=f"mcts-{session.session_id}",
            )

    async def stop(
        self,
        *,
        status: SessionStatus,
        clear_active: bool,
    ) -> None:
        async with self._state_lock:
            await self._stop_locked(status=status, clear_active=clear_active)

    async def shutdown(self) -> None:
        await self.stop(status=SessionStatus.PAUSED, clear_active=False)

    def reconfigure(self, modules: RuntimeModules) -> None:
        self._modules = modules
        if self._active_session is not None:
            self._mcts_engine = self._build_engine(self._active_session, modules)

    def get_tree_statistics(
        self, session: SessionData
    ) -> dict[str, int | float] | None:
        if (
            self._active_session is not None
            and self._active_session.session_id == session.session_id
            and self._mcts_engine is not None
        ):
            return self._mcts_engine.get_tree_statistics()
        return None

    def _build_engine(
        self, session: SessionData, modules: RuntimeModules
    ) -> MCTSEngine:
        return MCTSEngine(
            session=session,
            questioner=modules.questioner,
            pruner=modules.pruner,
            compressor=modules.compressor,
            settings=get_settings(),
            commit_lock=self._commit_lock,
        )

    async def _run_mcts_loop(
        self,
        session: SessionData,
        engine: MCTSEngine,
    ) -> None:
        session_token = session_id_ctx.set(session.session_id)
        settings = get_settings()
        num_workers = settings.mcts.parallel_workers
        logger.info(
            "Starting MCTS loop for session %s with %s workers",
            session.session_id,
            num_workers,
        )

        tasks = [
            asyncio.create_task(self._single_mcts_worker(worker_id, session, engine))
            for worker_id in range(num_workers)
        ]

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("MCTS loop cancelled for session %s", session.session_id)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
        except Exception as exc:
            logger.exception(
                "MCTS loop failed for session %s: %s",
                session.session_id,
                exc,
            )
            self._mcts_running = False
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            session.status = SessionStatus.ERROR
            session.error_message = str(exc)
            session.updated_at = datetime.now()
            session.bump_session_version()
            session.increment_revision()
            await self._repository.save_session(session)
        finally:
            if session.status == SessionStatus.RUNNING:
                session.status = SessionStatus.COMPLETED
                session.error_message = None
                session.updated_at = datetime.now()
                session.bump_session_version()
                session.increment_revision()

            if session.status != SessionStatus.ERROR:
                await self._repository.save_session(session)

            if self._mcts_engine is engine:
                self._mcts_running = False
                self._mcts_task = None

            session_id_ctx.reset(session_token)
            logger.info(
                "Session %s finished with status: %s",
                session.session_id,
                session.status.value,
            )

    async def _single_mcts_worker(
        self,
        worker_id: int,
        session: SessionData,
        engine: MCTSEngine,
    ) -> None:
        logger.info("Worker %s started for session %s", worker_id, session.session_id)

        while (
            self._mcts_running
            and self._mcts_engine is engine
            and self._active_session is session
        ):
            try:
                new_node_id = await engine.run_step()
                if new_node_id:
                    logger.debug(
                        "[Worker %s] 扩展新节点: %s",
                        worker_id,
                        new_node_id,
                    )

                if engine.should_stop():
                    logger.info("[Worker %s] 检测到停止条件", worker_id)
                    self._mcts_running = False
                    break

                if (
                    worker_id == 0
                    and new_node_id
                    and session.total_simulations
                    % get_settings().mcts.save_interval_steps
                    == 0
                ):
                    await self._repository.save_session(session)

                await asyncio.sleep(0.1)
            except Exception as exc:  # pragma: no cover - 由上层统一接管
                logger.exception("[Worker %s] 致命错误: %s", worker_id, exc)
                raise

        logger.info("Worker %s stopped for session %s", worker_id, session.session_id)

    async def _stop_locked(
        self,
        *,
        status: SessionStatus,
        clear_active: bool,
    ) -> None:
        task = self._mcts_task
        session = self._active_session

        self._mcts_running = False
        self._mcts_task = None
        self._mcts_engine = None

        if session is not None and session.status == SessionStatus.RUNNING:
            session.status = status
            if status != SessionStatus.ERROR:
                session.error_message = None
            session.updated_at = datetime.now()
            session.bump_session_version()
            session.increment_revision()
            await self._repository.save_session(session)

        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        if clear_active:
            self._active_session = None
