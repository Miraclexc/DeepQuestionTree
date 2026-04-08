export interface FactReadModel {
    id: string;
    content: string;
    confidence: number;
    created_at: string;
}

export interface InteractionReadModel {
    question: string;
    answer: string;
    summary?: string | null;
    tokens_used: number;
    model_used?: string | null;
    created_at: string;
}

export interface NodeStateReadModel {
    visit_count: number;
    value_sum: number;
    average_value: number;
}

export interface NodePathEntry {
    id: string;
    depth: number;
    question?: string | null;
    visits: number;
    value: number;
}

export interface NodeDetail {
    id: string;
    parent_id?: string | null;
    depth: number;
    state: NodeStateReadModel;
    interaction?: InteractionReadModel | null;
    new_facts: FactReadModel[];
    is_terminal: boolean;
    is_pruned: boolean;
    prune_reason?: string | null;
    created_at: string;
    updated_at: string;
    path: NodePathEntry[];
}

export interface SessionSummary {
    session_id: string;
    global_goal: string;
    created_at: string;
    updated_at: string;
    status: string;
    total_simulations: number;
    total_nodes: number;
    total_facts: number;
    file_size: number;
}

export interface SessionDetails {
    session_id: string;
    root_node_id: string;
    global_goal: string;
    total_simulations: number;
    total_tokens_used: number;
    created_at: string;
    updated_at: string;
    status: string;
    error_message?: string | null;
    total_nodes: number;
    total_facts: number;
    report_available: boolean;
    is_active: boolean;
}

export interface TreeNodeData {
    label: string;
    full_question: string;
    visits: number;
    value: number;
    depth: number;
    isPruned: boolean;
    isTerminal: boolean;
    isProcessing: boolean;
    factsCount: number;
    answer?: string;
}

export interface TreeFlowNode {
    id: string;
    type: string;
    position: {
        x: number;
        y: number;
    };
    data: TreeNodeData;
}

export interface TreeFlowEdge {
    id: string;
    source: string;
    target: string;
    type: string;
    animated: boolean;
}

export interface TreeResponse {
    session_id: string;
    session_revision: number;
    nodes: TreeFlowNode[];
    edges: TreeFlowEdge[];
    statistics: Record<string, number>;
}

export interface SystemStatus {
    single_session_mode: boolean;
    mcts_running: boolean;
    has_active_session: boolean;
    active_session_id?: string | null;
    environment: string;
    session_status?: string | null;
    session_revision?: number | null;
    session_error_message?: string | null;
    total_simulations?: number | null;
    tree_depth?: number | null;
    total_nodes?: number | null;
}

export interface StartSessionResponse {
    session_id: string;
    message: string;
    status: string;
}

export interface StopSessionResponse {
    message: string;
    active_session_id?: string | null;
    status?: string | null;
}

export interface SessionStatistics {
    total_nodes: number;
    total_simulations: number;
    tree_depth: number;
    total_facts: number;
    active_nodes: number;
    pruned_nodes: number;
}

export interface LlmUsageStats {
    calls: number;
    tokens: number;
}

export interface ReportData {
    session_id: string;
    goal: string;
    executive_summary: string;
    full_report: string;
    key_insights: string[];
    pruned_insights: string[];
    statistics: SessionStatistics;
    llm_stats: {
        total_calls: number;
        total_tokens: number;
        usage_by_model: Record<string, LlmUsageStats>;
    };
    suggestions: string[];
    generated_at: string;
    error_message?: string | null;
}

export interface ApiErrorPayload {
    detail: string;
    code: string;
    extra?: Record<string, unknown>;
}
