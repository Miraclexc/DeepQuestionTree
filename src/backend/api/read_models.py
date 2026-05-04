from __future__ import annotations

import json
from typing import Any, Mapping, Optional

from ..core.schema import Node, SessionData
from .dto import (
    FactReadModel,
    InteractionReadModel,
    LlmUsageStatsResponse,
    NodeDetailResponse,
    NodePathEntry,
    NodeStateReadModel,
    ReportLlmStatsResponse,
    ReportResponse,
    ReportStatisticsResponse,
    SessionReadModel,
    TreeEdgeReadModel,
    TreeNodePayload,
    TreeNodeReadModel,
    TreeResponse,
)


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
    if isinstance(usage_by_model_payload, Mapping):
        usage_by_model: Mapping[str, Any] = usage_by_model_payload
    else:
        fallback_usage = session.llm_usage.to_report_payload().get(
            "usage_by_model",
            {},
        )
        usage_by_model = fallback_usage if isinstance(fallback_usage, Mapping) else {}

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
