import type {
    NodeDetail,
    ReportData,
    SessionSummary,
    SystemStatus,
    TreeResponse,
} from "@/lib/types";

export const sessionSummariesFixture: SessionSummary[] = [
    {
        session_id: "session-1",
        global_goal: "Assess battery recycling policy impacts",
        created_at: "2026-04-04T10:00:00Z",
        updated_at: "2026-04-04T10:05:00Z",
        status: "running",
        total_simulations: 2,
        total_nodes: 3,
        total_facts: 4,
        file_size: 2048,
    },
    {
        session_id: "session-2",
        global_goal: "Map data center power constraints",
        created_at: "2026-04-03T10:00:00Z",
        updated_at: "2026-04-03T11:00:00Z",
        status: "completed",
        total_simulations: 7,
        total_nodes: 8,
        total_facts: 9,
        file_size: 4096,
    },
];

export const systemStatusFixture: SystemStatus = {
    single_session_mode: true,
    mcts_running: true,
    has_active_session: true,
    active_session_id: "session-1",
    environment: "test",
    session_status: "running",
    session_revision: 1,
    session_error_message: null,
    total_simulations: 2,
    tree_depth: 1,
    total_nodes: 3,
};

export const treeResponseFixture: TreeResponse = {
    session_id: "session-1",
    session_revision: 1,
    nodes: [
        {
            id: "root-node",
            type: "custom",
            position: { x: 0, y: 0 },
            data: {
                label: "Assess battery recycling policy impacts",
                full_question: "Assess battery recycling policy impacts",
                visits: 2,
                value: 0.8,
                depth: 0,
                isPruned: false,
                isTerminal: false,
                isProcessing: false,
                factsCount: 2,
                answer: "Exploration starting point",
            },
        },
        {
            id: "child-node",
            type: "custom",
            position: { x: 0, y: 0 },
            data: {
                label: "Which regulations drive collection?",
                full_question: "Which regulations drive battery collection behavior?",
                visits: 1,
                value: 0.6,
                depth: 1,
                isPruned: false,
                isTerminal: false,
                isProcessing: false,
                factsCount: 1,
                answer: "Collection is shaped by EPR and landfill bans.",
            },
        },
    ],
    edges: [
        {
            id: "root-node-child-node",
            source: "root-node",
            target: "child-node",
            type: "smoothstep",
            animated: false,
        },
    ],
    statistics: {
        total_nodes: 3,
        total_simulations: 2,
        tree_depth: 1,
    },
};

export const nodeDetailFixture: NodeDetail = {
    id: "child-node",
    parent_id: "root-node",
    depth: 1,
    state: {
        visit_count: 1,
        value_sum: 0.6,
        average_value: 0.6,
    },
    interaction: {
        question: "Which regulations drive battery collection behavior?",
        answer: "Collection is shaped by EPR and landfill bans.",
        summary: "Policy and disposal rules drive collection.",
        tokens_used: 123,
        model_used: "mock-model",
        created_at: "2026-04-04T10:01:00Z",
    },
    new_facts: [
        {
            id: "fact-1",
            content: "Extended producer responsibility increases collection rates.",
            confidence: 0.9,
            created_at: "2026-04-04T10:02:00Z",
        },
    ],
    is_terminal: false,
    is_pruned: false,
    prune_reason: null,
    created_at: "2026-04-04T10:01:00Z",
    updated_at: "2026-04-04T10:02:00Z",
    path: [
        {
            id: "root-node",
            depth: 0,
            question: "Assess battery recycling policy impacts",
            visits: 2,
            value: 0.8,
        },
        {
            id: "child-node",
            depth: 1,
            question: "Which regulations drive battery collection behavior?",
            visits: 1,
            value: 0.6,
        },
    ],
};

export const reportFixture: ReportData = {
    session_id: "session-1",
    goal: "Assess battery recycling policy impacts",
    executive_summary:
        "Battery recycling outcomes depend on collection mandates, processing incentives and commodity pricing.",
    full_report:
        "# Detailed Report\n\n## Findings\n\nBattery recycling improves when collection is mandatory.",
    key_insights: [
        "Collection mandates reduce drop-off friction.",
        "Processing subsidies stabilize recycler economics.",
    ],
    pruned_insights: [
        "Unsubsidized voluntary drop-off alone showed weak evidence.",
    ],
    statistics: {
        total_nodes: 3,
        total_simulations: 2,
        tree_depth: 1,
        total_facts: 4,
        active_nodes: 2,
        pruned_nodes: 1,
    },
    llm_stats: {
        total_calls: 4,
        total_tokens: 512,
        usage_by_model: {
            "mock-model": {
                calls: 4,
                tokens: 512,
            },
        },
    },
    suggestions: ["Compare EU and US enforcement patterns."],
    generated_at: "2026-04-04T10:06:00Z",
    error_message: null,
};
