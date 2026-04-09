from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Mapping, Optional

from pydantic import BaseModel, Field

from ..core.schema import Node, SessionData


class MessageResponse(BaseModel):
    message: str


class StartRequest(BaseModel):
    goal: str = Field(..., description="探索目标问题")
    session_id: Optional[str] = Field(None, description="恢复的会话 ID（可选）")
    use_mock: bool = Field(False, description="是否使用 Mock 客户端")


class StartResponse(BaseModel):
    session_id: str
    message: str
    status: str


class StopResponse(BaseModel):
    message: str
    active_session_id: Optional[str] = None
    status: Optional[str] = None


class SystemStatusResponse(BaseModel):
    single_session_mode: bool = True
    mcts_running: bool
    has_active_session: bool
    active_session_id: Optional[str] = None
    environment: str
    session_status: Optional[str] = None
    session_revision: Optional[int] = None
    session_error_message: Optional[str] = None
    total_simulations: Optional[int] = None
    tree_depth: Optional[int] = None
    total_nodes: Optional[int] = None


class SessionSummary(BaseModel):
    session_id: str
    global_goal: str
    created_at: datetime
    updated_at: datetime
    status: str
    is_legacy_token_accounting: bool = False
    total_simulations: int
    total_nodes: int
    total_facts: int
    file_size: int


class SessionReadModel(BaseModel):
    session_id: str
    root_node_id: str
    global_goal: str
    total_simulations: int
    total_tokens_used: int
    is_legacy_token_accounting: bool = False
    created_at: datetime
    updated_at: datetime
    status: str
    error_message: Optional[str] = None
    total_nodes: int
    total_facts: int
    report_available: bool
    is_active: bool


class TreeNodePayload(BaseModel):
    label: str
    full_question: str
    visits: int
    value: float
    depth: int
    isPruned: bool
    isTerminal: bool
    isProcessing: bool
    factsCount: int
    answer: str = ""


class TreeNodeReadModel(BaseModel):
    id: str
    type: str = "custom"
    position: dict[str, float]
    data: TreeNodePayload


class TreeEdgeReadModel(BaseModel):
    id: str
    source: str
    target: str
    type: str = "smoothstep"
    animated: bool = False


class TreeResponse(BaseModel):
    session_id: str
    session_revision: int = 0
    nodes: list[TreeNodeReadModel]
    edges: list[TreeEdgeReadModel]
    statistics: dict[str, Any]


class NodeStateReadModel(BaseModel):
    visit_count: int
    value_sum: float
    average_value: float


class InteractionReadModel(BaseModel):
    question: str
    answer: str
    summary: Optional[str] = None
    tokens_used: int
    model_used: Optional[str] = None
    created_at: datetime


class FactReadModel(BaseModel):
    id: str
    content: str
    confidence: float
    created_at: datetime


class NodePathEntry(BaseModel):
    id: str
    depth: int
    question: Optional[str] = None
    visits: int
    value: float


class NodeDetailResponse(BaseModel):
    id: str
    parent_id: Optional[str] = None
    depth: int
    state: NodeStateReadModel
    interaction: Optional[InteractionReadModel] = None
    new_facts: list[FactReadModel]
    is_terminal: bool
    is_pruned: bool
    prune_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    path: list[NodePathEntry]


class ReportStatisticsResponse(BaseModel):
    total_nodes: int = 0
    total_simulations: int = 0
    tree_depth: int = 0
    total_facts: int = 0
    active_nodes: int = 0
    pruned_nodes: int = 0


class LlmUsageStatsResponse(BaseModel):
    calls: int = 0
    tokens: int = 0


class ReportLlmStatsResponse(BaseModel):
    total_calls: int = 0
    total_tokens: int = 0
    usage_by_model: dict[str, LlmUsageStatsResponse] = Field(default_factory=dict)


class ReportResponse(BaseModel):
    session_id: str
    goal: str
    executive_summary: str = ""
    full_report: str = ""
    key_insights: list[str] = Field(default_factory=list)
    pruned_insights: list[str] = Field(default_factory=list)
    statistics: ReportStatisticsResponse = Field(
        default_factory=ReportStatisticsResponse
    )
    llm_stats: ReportLlmStatsResponse = Field(default_factory=ReportLlmStatsResponse)
    suggestions: list[str] = Field(default_factory=list)
    generated_at: str
    error_message: Optional[str] = None


def parse_display_answer(answer: str) -> str:
    if not answer:
        return ""

    try:
        if answer.strip().startswith("[") or answer.strip().startswith("{"):
            data = json.loads(answer)
            if isinstance(data, list):
                contents = [
                    item.get("content", "") for item in data if isinstance(item, dict)
                ]
                normalized = "\n".join(filter(None, contents))
                return normalized or answer

            if isinstance(data, dict):
                return str(data.get("content", answer))
    except json.JSONDecodeError:
        pass

    return answer


def build_session_read_model(
    session: SessionData,
    *,
    is_active: bool,
    report_available: bool,
) -> SessionReadModel:
    return SessionReadModel(
        session_id=session.session_id,
        root_node_id=session.root_node_id,
        global_goal=session.global_goal,
        total_simulations=session.total_simulations,
        total_tokens_used=session.total_tokens_used,
        is_legacy_token_accounting=session.is_legacy_token_accounting,
        created_at=session.created_at,
        updated_at=session.updated_at,
        status=(
            session.status.value
            if hasattr(session.status, "value")
            else str(session.status)
        ),
        error_message=session.error_message,
        total_nodes=session.get_total_nodes(),
        total_facts=len(session.global_facts),
        report_available=report_available,
        is_active=is_active,
    )


def build_tree_response(
    session: SessionData,
    *,
    statistics: dict[str, Any],
) -> TreeResponse:
    nodes: list[TreeNodeReadModel] = []
    edges: list[TreeEdgeReadModel] = []

    for node in session.nodes.values():
        label = "Start"
        question = "Root"
        answer = ""
        if node.interaction:
            question = node.interaction.question
            label = question[:30] + ("..." if len(question) > 30 else "")
            answer = parse_display_answer(node.interaction.answer)

        nodes.append(
            TreeNodeReadModel(
                id=node.id,
                position={"x": 0.0, "y": 0.0},
                data=TreeNodePayload(
                    label=label,
                    full_question=question,
                    visits=node.state.visit_count,
                    value=node.state.average_value,
                    depth=node.depth,
                    isPruned=node.is_pruned,
                    isTerminal=node.is_terminal,
                    isProcessing=node.is_processing,
                    factsCount=len(node.new_facts),
                    answer=answer,
                ),
            )
        )

        for child_id in node.children_ids:
            edges.append(
                TreeEdgeReadModel(
                    id=f"{node.id}-{child_id}",
                    source=node.id,
                    target=child_id,
                )
            )

    return TreeResponse(
        session_id=session.session_id,
        session_revision=session.session_revision,
        nodes=nodes,
        edges=edges,
        statistics=statistics,
    )


def build_node_detail_response(
    session: SessionData,
    node: Node,
) -> NodeDetailResponse:
    path: list[NodePathEntry] = []
    current_id: Optional[str] = node.id
    while current_id:
        path_node = session.nodes[current_id]
        path.append(
            NodePathEntry(
                id=path_node.id,
                depth=path_node.depth,
                question=(
                    path_node.interaction.question if path_node.interaction else None
                ),
                visits=path_node.state.visit_count,
                value=path_node.state.average_value,
            )
        )
        current_id = path_node.parent_id

    interaction = None
    if node.interaction:
        interaction = InteractionReadModel(
            question=node.interaction.question,
            answer=parse_display_answer(node.interaction.answer),
            summary=node.interaction.summary,
            tokens_used=node.interaction.tokens_used,
            model_used=node.interaction.model_used,
            created_at=node.interaction.created_at,
        )

    return NodeDetailResponse(
        id=node.id,
        parent_id=node.parent_id,
        depth=node.depth,
        state=NodeStateReadModel(
            visit_count=node.state.visit_count,
            value_sum=node.state.value_sum,
            average_value=node.state.average_value,
        ),
        interaction=interaction,
        new_facts=[
            FactReadModel(
                id=fact.id,
                content=fact.content,
                confidence=fact.confidence,
                created_at=fact.created_at,
            )
            for fact in node.new_facts
        ],
        is_terminal=node.is_terminal,
        is_pruned=node.is_pruned,
        prune_reason=node.prune_reason,
        created_at=node.created_at,
        updated_at=node.updated_at,
        path=list(reversed(path)),
    )


def build_report_response(
    session: SessionData,
    report_data: Mapping[str, Any] | None,
) -> ReportResponse:
    payload = dict(report_data or {})
    partial_data = payload.get("partial_data")
    partial = partial_data if isinstance(partial_data, Mapping) else {}

    statistics_payload = payload.get("statistics")
    statistics = statistics_payload if isinstance(statistics_payload, Mapping) else {}

    total_nodes = _safe_int(
        statistics.get("total_nodes"),
        _safe_int(partial.get("nodes_count"), session.get_total_nodes()),
    )
    total_simulations = _safe_int(
        statistics.get("total_simulations"),
        _safe_int(partial.get("simulations"), session.total_simulations),
    )
    tree_depth = _safe_int(statistics.get("tree_depth"), session.get_tree_depth())
    total_facts = _safe_int(
        statistics.get("total_facts"),
        _safe_int(partial.get("facts_count"), len(session.global_facts)),
    )

    llm_stats_payload = payload.get("llm_stats")
    llm_stats = llm_stats_payload if isinstance(llm_stats_payload, Mapping) else {}
    usage_by_model_payload = llm_stats.get("usage_by_model")
    usage_by_model = (
        usage_by_model_payload
        if isinstance(usage_by_model_payload, Mapping)
        else session.llm_usage.to_report_payload().get("usage_by_model", {})
    )

    return ReportResponse(
        session_id=str(payload.get("session_id") or session.session_id),
        goal=str(payload.get("goal") or session.global_goal),
        executive_summary=_safe_str(payload.get("executive_summary")),
        full_report=_safe_str(payload.get("full_report")),
        key_insights=_safe_str_list(payload.get("key_insights")),
        pruned_insights=_safe_str_list(payload.get("pruned_insights")),
        statistics=ReportStatisticsResponse(
            total_nodes=total_nodes,
            total_simulations=total_simulations,
            tree_depth=tree_depth,
            total_facts=total_facts,
            active_nodes=_safe_int(
                statistics.get("active_nodes"),
                len(session.get_active_nodes()),
            ),
            pruned_nodes=_safe_int(
                statistics.get("pruned_nodes"),
                sum(1 for node in session.nodes.values() if node.is_pruned),
            ),
        ),
        llm_stats=ReportLlmStatsResponse(
            total_calls=_safe_int(
                llm_stats.get("total_calls"),
                session.llm_usage.total_calls,
            ),
            total_tokens=_safe_int(
                llm_stats.get("total_tokens"),
                session.llm_usage.total_tokens,
            ),
            usage_by_model={
                str(model): LlmUsageStatsResponse(
                    calls=_safe_int(data.get("calls"), 0),
                    tokens=_safe_int(data.get("tokens"), 0),
                )
                for model, data in usage_by_model.items()
                if isinstance(data, Mapping)
            },
        ),
        suggestions=_safe_str_list(payload.get("suggestions")),
        generated_at=str(payload.get("generated_at") or session.updated_at.isoformat()),
        error_message=_safe_optional_str(
            payload.get("error_message") or payload.get("error")
        ),
    )


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_str(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _safe_optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _safe_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]
