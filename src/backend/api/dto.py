from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


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
