import {
    FactReadModel,
    LlmUsageStats,
    NodeDetail,
    ReportData,
    SessionDetails,
    SessionSummary,
    StartSessionResponse,
    StopSessionResponse,
    SystemStatus,
    TreeFlowEdge,
    TreeFlowNode,
    TreeResponse,
} from "./types";

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asString(value: unknown, fallback = ""): string {
    return typeof value === "string" ? value : fallback;
}

function asNullableString(value: unknown): string | null {
    return typeof value === "string" ? value : null;
}

function asNumber(value: unknown, fallback = 0): number {
    return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function asBoolean(value: unknown, fallback = false): boolean {
    return typeof value === "boolean" ? value : fallback;
}

function asStringArray(value: unknown): string[] {
    if (!Array.isArray(value)) {
        return [];
    }
    return value.map((entry) => String(entry));
}

function asFacts(value: unknown): FactReadModel[] {
    if (!Array.isArray(value)) {
        return [];
    }

    return value.map((entry) => {
        const record = isRecord(entry) ? entry : {};
        return {
            id: asString(record.id),
            content: asString(record.content),
            confidence: asNumber(record.confidence),
            created_at: asString(record.created_at),
        };
    });
}

function asLlmUsageStatsRecord(value: unknown): Record<string, LlmUsageStats> {
    if (!isRecord(value)) {
        return {};
    }

    return Object.fromEntries(
        Object.entries(value).map(([model, stats]) => {
            const record = isRecord(stats) ? stats : {};
            return [
                model,
                {
                    calls: asNumber(record.calls),
                    tokens: asNumber(record.tokens),
                },
            ];
        }),
    );
}

export function normalizeSessionSummaries(payload: unknown): SessionSummary[] {
    if (!Array.isArray(payload)) {
        return [];
    }

    return payload.map((entry) => {
        const record = isRecord(entry) ? entry : {};
        return {
            session_id: asString(record.session_id),
            global_goal: asString(record.global_goal),
            created_at: asString(record.created_at),
            updated_at: asString(record.updated_at),
            status: asString(record.status),
            total_simulations: asNumber(record.total_simulations),
            total_nodes: asNumber(record.total_nodes),
            total_facts: asNumber(record.total_facts),
            file_size: asNumber(record.file_size),
        };
    });
}

export function normalizeSessionDetails(payload: unknown): SessionDetails {
    const record = isRecord(payload) ? payload : {};
    return {
        session_id: asString(record.session_id),
        root_node_id: asString(record.root_node_id),
        global_goal: asString(record.global_goal),
        total_simulations: asNumber(record.total_simulations),
        total_tokens_used: asNumber(record.total_tokens_used),
        created_at: asString(record.created_at),
        updated_at: asString(record.updated_at),
        status: asString(record.status),
        error_message: asNullableString(record.error_message),
        total_nodes: asNumber(record.total_nodes),
        total_facts: asNumber(record.total_facts),
        report_available: asBoolean(record.report_available),
        is_active: asBoolean(record.is_active),
    };
}

export function normalizeSystemStatus(payload: unknown): SystemStatus {
    const record = isRecord(payload) ? payload : {};
    return {
        single_session_mode: asBoolean(record.single_session_mode, true),
        mcts_running: asBoolean(record.mcts_running),
        has_active_session: asBoolean(record.has_active_session),
        active_session_id: asNullableString(record.active_session_id),
        environment: asString(record.environment, "development"),
        session_status: asNullableString(record.session_status),
        session_revision:
            typeof record.session_revision === "number"
                ? record.session_revision
                : null,
        session_error_message: asNullableString(record.session_error_message),
        total_simulations:
            typeof record.total_simulations === "number"
                ? record.total_simulations
                : null,
        tree_depth:
            typeof record.tree_depth === "number" ? record.tree_depth : null,
        total_nodes:
            typeof record.total_nodes === "number" ? record.total_nodes : null,
    };
}

function normalizeTreeNodes(payload: unknown): TreeFlowNode[] {
    if (!Array.isArray(payload)) {
        return [];
    }

    return payload.map((entry) => {
        const record = isRecord(entry) ? entry : {};
        const position = isRecord(record.position) ? record.position : {};
        const data = isRecord(record.data) ? record.data : {};

        return {
            id: asString(record.id),
            type: asString(record.type, "custom"),
            position: {
                x: asNumber(position.x),
                y: asNumber(position.y),
            },
            data: {
                label: asString(data.label),
                full_question: asString(data.full_question),
                visits: asNumber(data.visits),
                value: asNumber(data.value),
                depth: asNumber(data.depth),
                isPruned: asBoolean(data.isPruned),
                isTerminal: asBoolean(data.isTerminal),
                isProcessing: asBoolean(data.isProcessing),
                factsCount: asNumber(data.factsCount),
                answer: asString(data.answer),
            },
        };
    });
}

function normalizeTreeEdges(payload: unknown): TreeFlowEdge[] {
    if (!Array.isArray(payload)) {
        return [];
    }

    return payload.map((entry) => {
        const record = isRecord(entry) ? entry : {};
        return {
            id: asString(record.id),
            source: asString(record.source),
            target: asString(record.target),
            type: asString(record.type, "smoothstep"),
            animated: asBoolean(record.animated),
        };
    });
}

export function normalizeTreeResponse(payload: unknown): TreeResponse {
    const record = isRecord(payload) ? payload : {};
    const statistics = isRecord(record.statistics) ? record.statistics : {};

    return {
        session_id: asString(record.session_id),
        session_revision: asNumber(record.session_revision),
        nodes: normalizeTreeNodes(record.nodes),
        edges: normalizeTreeEdges(record.edges),
        statistics: Object.fromEntries(
            Object.entries(statistics)
                .filter(([, value]) => typeof value === "number")
                .map(([key, value]) => [key, value as number]),
        ),
    };
}

export function normalizeNodeDetail(payload: unknown): NodeDetail {
    const record = isRecord(payload) ? payload : {};
    const state = isRecord(record.state) ? record.state : {};
    const interaction = isRecord(record.interaction) ? record.interaction : null;
    const path = Array.isArray(record.path) ? record.path : [];

    return {
        id: asString(record.id),
        parent_id: asNullableString(record.parent_id),
        depth: asNumber(record.depth),
        state: {
            visit_count: asNumber(state.visit_count),
            value_sum: asNumber(state.value_sum),
            average_value: asNumber(state.average_value),
        },
        interaction: interaction
            ? {
                  question: asString(interaction.question),
                  answer: asString(interaction.answer),
                  summary: asNullableString(interaction.summary),
                  tokens_used: asNumber(interaction.tokens_used),
                  model_used: asNullableString(interaction.model_used),
                  created_at: asString(interaction.created_at),
              }
            : null,
        new_facts: asFacts(record.new_facts),
        is_terminal: asBoolean(record.is_terminal),
        is_pruned: asBoolean(record.is_pruned),
        prune_reason: asNullableString(record.prune_reason),
        created_at: asString(record.created_at),
        updated_at: asString(record.updated_at),
        path: path.map((entry) => {
            const pathRecord = isRecord(entry) ? entry : {};
            return {
                id: asString(pathRecord.id),
                depth: asNumber(pathRecord.depth),
                question: asNullableString(pathRecord.question),
                visits: asNumber(pathRecord.visits),
                value: asNumber(pathRecord.value),
            };
        }),
    };
}

export function normalizeStartSessionResponse(payload: unknown): StartSessionResponse {
    const record = isRecord(payload) ? payload : {};
    return {
        session_id: asString(record.session_id),
        message: asString(record.message),
        status: asString(record.status),
    };
}

export function normalizeStopSessionResponse(payload: unknown): StopSessionResponse {
    const record = isRecord(payload) ? payload : {};
    return {
        message: asString(record.message),
        active_session_id: asNullableString(record.active_session_id),
        status: asNullableString(record.status),
    };
}

export function normalizeReportData(payload: unknown): ReportData {
    const record = isRecord(payload) ? payload : {};
    const partialData = isRecord(record.partial_data) ? record.partial_data : {};
    const statistics = isRecord(record.statistics) ? record.statistics : {};
    const llmStats = isRecord(record.llm_stats) ? record.llm_stats : {};

    return {
        session_id: asString(record.session_id),
        goal: asString(record.goal),
        executive_summary: asString(record.executive_summary),
        full_report: asString(record.full_report),
        key_insights: asStringArray(record.key_insights),
        pruned_insights: asStringArray(record.pruned_insights),
        statistics: {
            total_nodes: asNumber(
                statistics.total_nodes,
                asNumber(partialData.nodes_count),
            ),
            total_simulations: asNumber(
                statistics.total_simulations,
                asNumber(partialData.simulations),
            ),
            tree_depth: asNumber(statistics.tree_depth),
            total_facts: asNumber(
                statistics.total_facts,
                asNumber(partialData.facts_count),
            ),
            active_nodes: asNumber(statistics.active_nodes),
            pruned_nodes: asNumber(statistics.pruned_nodes),
        },
        llm_stats: {
            total_calls: asNumber(llmStats.total_calls),
            total_tokens: asNumber(llmStats.total_tokens),
            usage_by_model: asLlmUsageStatsRecord(llmStats.usage_by_model),
        },
        suggestions: asStringArray(record.suggestions),
        generated_at: asString(record.generated_at),
        error_message: asNullableString(record.error_message ?? record.error),
    };
}
