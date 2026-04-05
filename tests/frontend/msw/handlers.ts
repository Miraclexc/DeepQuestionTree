import { http, HttpResponse } from "../../../src/frontend/node_modules/msw/lib/core/index.mjs";

import {
    nodeDetailFixture,
    reportFixture,
    sessionSummariesFixture,
    systemStatusFixture,
    treeResponseFixture,
} from "../fixtures/data";

const API_BASE = "http://localhost:8001/api";

export const handlers = [
    http.get(`${API_BASE}/status`, () => HttpResponse.json(systemStatusFixture)),
    http.get(`${API_BASE}/sessions`, () => HttpResponse.json(sessionSummariesFixture)),
    http.post(`${API_BASE}/start`, async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({
            session_id: "session-1",
            message: `started:${String(body.goal ?? "")}`,
            status: "running",
        });
    }),
    http.post(`${API_BASE}/stop`, () =>
        HttpResponse.json({
            message: "探索已停止",
            active_session_id: "session-1",
            status: "paused",
        }),
    ),
    http.get(`${API_BASE}/sessions/:sessionId`, ({ params }) =>
        HttpResponse.json({
            session_id: params.sessionId,
            root_node_id: "root-node",
            global_goal: sessionSummariesFixture[0].global_goal,
            total_simulations: 2,
            total_tokens_used: 256,
            created_at: sessionSummariesFixture[0].created_at,
            updated_at: sessionSummariesFixture[0].updated_at,
            status: "running",
            error_message: null,
            total_nodes: 3,
            total_facts: 4,
            report_available: true,
            is_active: true,
        }),
    ),
    http.delete(`${API_BASE}/sessions/:sessionId`, () => new HttpResponse(null, { status: 204 })),
    http.get(`${API_BASE}/sessions/:sessionId/tree`, ({ params }) =>
        HttpResponse.json({
            ...treeResponseFixture,
            session_id: params.sessionId,
        }),
    ),
    http.get(`${API_BASE}/sessions/:sessionId/nodes/:nodeId`, ({ params }) =>
        HttpResponse.json({
            ...nodeDetailFixture,
            id: params.nodeId,
        }),
    ),
    http.get(`${API_BASE}/sessions/:sessionId/report`, ({ params }) =>
        HttpResponse.json({
            ...reportFixture,
            session_id: params.sessionId,
        }),
    ),
];
