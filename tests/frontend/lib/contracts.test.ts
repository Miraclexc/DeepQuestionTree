import { describe, expect, it } from "vitest";

import {
    normalizeNodeDetail,
    normalizeReportData,
    normalizeSessionSummaries,
    normalizeSystemStatus,
    normalizeTreeResponse,
} from "@/lib/contracts";

describe("contracts normalization", () => {
    it("normalizes session summaries and falls back for invalid fields", () => {
        const summaries = normalizeSessionSummaries([
            {
                session_id: "session-1",
                global_goal: "goal",
                created_at: "2026-04-04T10:00:00Z",
                updated_at: "2026-04-04T10:05:00Z",
                status: "running",
                total_simulations: 2,
                total_nodes: 3,
                total_facts: 4,
                file_size: 5,
            },
            {
                session_id: 123,
                global_goal: null,
                total_nodes: "bad",
            },
        ]);

        expect(summaries).toEqual([
            expect.objectContaining({
                session_id: "session-1",
                total_nodes: 3,
            }),
            {
                session_id: "",
                global_goal: "",
                created_at: "",
                updated_at: "",
                status: "",
                total_simulations: 0,
                total_nodes: 0,
                total_facts: 0,
                file_size: 0,
            },
        ]);
        expect(normalizeSessionSummaries({ foo: "bar" })).toEqual([]);
    });

    it("normalizes tree payloads and drops non-number statistics", () => {
        const tree = normalizeTreeResponse({
            session_id: "session-1",
            session_revision: 4,
            nodes: [
                {
                    id: "root",
                    position: { x: 1, y: "bad" },
                    data: {
                        label: "Root",
                        full_question: "Root question",
                        visits: 2,
                        value: 0.5,
                        depth: 0,
                        isPruned: "bad",
                    },
                },
            ],
            edges: [{ id: "e1", source: "root", target: "child", animated: true }],
            statistics: {
                total_nodes: 2,
                environment: "test",
                tree_depth: 1,
            },
        });

        expect(tree.nodes[0]).toEqual({
            id: "root",
            type: "custom",
            position: { x: 1, y: 0 },
            data: {
                label: "Root",
                full_question: "Root question",
                visits: 2,
                value: 0.5,
                depth: 0,
                isPruned: false,
                isTerminal: false,
                isProcessing: false,
                factsCount: 0,
                answer: "",
            },
        });
        expect(tree.statistics).toEqual({
            total_nodes: 2,
            tree_depth: 1,
        });
        expect((tree as any).session_revision).toBe(4);
    });

    it("normalizes system status revision and active error message", () => {
        const status = normalizeSystemStatus({
            single_session_mode: true,
            mcts_running: true,
            has_active_session: true,
            active_session_id: "session-1",
            environment: "test",
            session_status: "error",
            session_revision: 9,
            session_error_message: "fatal runtime failure",
        });

        expect((status as any).session_revision).toBe(9);
        expect((status as any).session_error_message).toBe(
            "fatal runtime failure",
        );
    });

    it("normalizes node details with null-safe interaction and path fallbacks", () => {
        const node = normalizeNodeDetail({
            id: "child",
            parent_id: "root",
            depth: 1,
            state: {
                visit_count: 3,
                value_sum: 1.5,
            },
            interaction: null,
            new_facts: [{ id: "f1", content: "fact", confidence: "bad" }],
            path: [{ id: "root", visits: 1 }],
        });

        expect(node.interaction).toBeNull();
        expect(node.state).toEqual({
            visit_count: 3,
            value_sum: 1.5,
            average_value: 0,
        });
        expect(node.new_facts[0]).toEqual({
            id: "f1",
            content: "fact",
            confidence: 0,
            created_at: "",
        });
        expect(node.path[0]).toEqual({
            id: "root",
            depth: 0,
            question: null,
            visits: 1,
            value: 0,
        });
    });

    it("normalizes report data with legacy partial payload fallback", () => {
        const report = normalizeReportData({
            session_id: "session-1",
            goal: "goal",
            key_insights: ["one", 2],
            pruned_insights: "bad",
            partial_data: {
                nodes_count: 7,
                simulations: 9,
                facts_count: 11,
            },
            llm_stats: {
                total_calls: 3,
                total_tokens: 100,
                usage_by_model: {
                    "mock-model": {
                        calls: 3,
                        tokens: 100,
                    },
                },
            },
            error: "legacy error",
        });

        expect(report.statistics).toEqual({
            total_nodes: 7,
            total_simulations: 9,
            tree_depth: 0,
            total_facts: 11,
            active_nodes: 0,
            pruned_nodes: 0,
        });
        expect(report.key_insights).toEqual(["one", "2"]);
        expect(report.pruned_insights).toEqual([]);
        expect(report.error_message).toBe("legacy error");
    });
});
