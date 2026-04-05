"""
DeepQuestionTree FastAPI 应用入口。
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.router import router
from .config_loader import get_settings
from .services.errors import ApplicationError
from .services.runtime import ExplorationRuntime
from .utils.logger import get_logger, request_id_ctx, session_id_ctx, setup_logging

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("DeepQuestionTree 启动中...")
    yield
    logger.info("DeepQuestionTree 正在关闭...")
    await app.state.runtime.shutdown()


def register_exception_handlers(application: FastAPI) -> None:
    @application.exception_handler(ApplicationError)
    async def handle_application_error(
        _: Request, exc: ApplicationError
    ) -> JSONResponse:
        payload: dict[str, Any] = {
            "detail": exc.detail,
            "code": exc.code,
        }
        if exc.extra:
            payload["extra"] = exc.extra
        return JSONResponse(status_code=exc.status_code, content=payload)

    @application.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        _: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Request validation failed",
                "code": "request_validation_error",
                "errors": exc.errors(),
            },
        )

    @application.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "code": "internal_error",
            },
        )


def create_app() -> FastAPI:
    settings = get_settings()

    application = FastAPI(
        title="DeepQuestionTree API",
        description="基于 MCTS 和 LLM 的深度问题探索系统",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.state.runtime = ExplorationRuntime()
    register_exception_handlers(application)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            f"{settings.app.frontend_host}:{settings.app.frontend_port}",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = str(uuid.uuid4())
        request_token = request_id_ctx.set(request_id)

        runtime = getattr(request.app.state, "runtime", None)
        session_token = None
        active_session = getattr(runtime, "active_session", None)
        if active_session is not None:
            session_token = session_id_ctx.set(active_session.session_id)

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_ctx.reset(request_token)
            if session_token is not None:
                session_id_ctx.reset(session_token)

    application.include_router(router)
    return application


app = create_app()


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "src.backend.main:app",
        host="0.0.0.0",
        port=settings.app.api_port,
        reload=settings.app.debug,
        log_level="info",
    )


if __name__ == "__main__":
    main()
