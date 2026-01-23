export interface Fact {
    id: string;
    content: string;
    source_node_id: string;
    confidence: number;
    created_at: string;
}

export interface QAInteraction {
    question: string;
    answer: string;
    summary?: string;
    tokens_used: number;
    model_used?: string;
    created_at: string;
}

export interface NodeState {
    visit_count: number;
    value_sum: number;
    average_value: number;
}

export interface Node {
    id: string;
    parent_id?: string;
    children_ids: string[];
    depth: number;
    interaction?: QAInteraction;
    new_facts: Fact[];
    state: NodeState;
    is_terminal: boolean;
    is_pruned: boolean;
    prune_reason?: string;
    created_at: string;
    updated_at: string;
}

export interface SessionData {
    session_id: string;
    root_node_id: string;
    global_facts: Fact[];
    global_goal: string;
    total_simulations: number;
    total_tokens_used: number;
    created_at: string;
    updated_at: string;
    status: string;
    error_message?: string;
}

export interface TreeNodeData {
    label: string;
    full_question: string;
    visits: number;
    value: number;
    depth: number;
    isPruned: boolean;
    isTerminal: boolean;
    factsCount: number;
    answer?: string;
}

export interface TreeResponse {
    nodes: any[]; // React Flow nodes
    edges: any[]; // React Flow edges
}
