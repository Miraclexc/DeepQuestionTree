from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status

from ..services.runtime import ExplorationRuntime
from .dependencies import verify_api_token
from .dto import (
    MessageResponse,
    NodeDetailResponse,
    ReportResponse,
    SessionReadModel,
    SessionSummary,
    StartRequest,
    StartResponse,
    StopResponse,
    SystemStatusResponse,
    TreeResponse,
)

router = APIRouter(
    prefix="/api",
    tags=["api"],
    dependencies=[Depends(verify_api_token)],
)


def get_runtime(request: Request) -> ExplorationRuntime:
    return request.app.state.runtime


@router.post("/start", response_model=StartResponse)
async def start_session(request_data: StartRequest, request: Request):
    runtime = get_runtime(request)
    return await runtime.command_service.start_session(
        goal=request_data.goal,
        use_mock=request_data.use_mock,
        session_id=request_data.session_id,
    )


@router.post("/stop", response_model=StopResponse)
async def stop_session(request: Request):
    runtime = get_runtime(request)
    return await runtime.command_service.stop_session()


@router.get("/status", response_model=SystemStatusResponse)
async def get_status(request: Request):
    return await get_runtime(request).query_service.get_status()


@router.get("/sessions", response_model=list[SessionSummary])
async def list_sessions(request: Request):
    return await get_runtime(request).query_service.list_sessions()


@router.get("/sessions/{session_id}", response_model=SessionReadModel)
async def get_session(session_id: str, request: Request):
    return await get_runtime(request).query_service.get_session(session_id)


@router.get("/sessions/{session_id}/tree", response_model=TreeResponse)
async def get_tree(session_id: str, request: Request):
    return await get_runtime(request).query_service.get_tree(session_id)


@router.get(
    "/sessions/{session_id}/nodes/{node_id}",
    response_model=NodeDetailResponse,
)
async def get_node_detail(session_id: str, node_id: str, request: Request):
    return await get_runtime(request).query_service.get_node_detail(session_id, node_id)


@router.get("/sessions/{session_id}/report", response_model=ReportResponse)
async def get_report(session_id: str, request: Request):
    return await get_runtime(request).report_service.get_report(session_id)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: str, request: Request):
    await get_runtime(request).command_service.delete_session(session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/config/reload", response_model=MessageResponse)
async def reload_config(request: Request):
    return await get_runtime(request).reload_configuration()
