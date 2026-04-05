import {
    normalizeNodeDetail,
    normalizeReportData,
    normalizeSessionDetails,
    normalizeSessionSummaries,
    normalizeStartSessionResponse,
    normalizeStopSessionResponse,
    normalizeSystemStatus,
    normalizeTreeResponse,
} from "./contracts";
import { apiClient } from "./api-client";
import {
    NodeDetail,
    ReportData,
    SessionDetails,
    SessionSummary,
    StartSessionResponse,
    StopSessionResponse,
    SystemStatus,
    TreeResponse,
} from "./types";

export async function fetchSessions(): Promise<SessionSummary[]> {
    return apiClient.get("/sessions", normalizeSessionSummaries);
}

export async function fetchSession(sessionId: string): Promise<SessionDetails> {
    return apiClient.get(`/sessions/${sessionId}`, normalizeSessionDetails);
}

export async function fetchTree(sessionId: string): Promise<TreeResponse> {
    return apiClient.get(`/sessions/${sessionId}/tree`, normalizeTreeResponse);
}

export async function fetchNode(sessionId: string, nodeId: string): Promise<NodeDetail> {
    return apiClient.get(
        `/sessions/${sessionId}/nodes/${nodeId}`,
        normalizeNodeDetail,
    );
}

export async function deleteSession(sessionId: string): Promise<void> {
    await apiClient.delete(`/sessions/${sessionId}`);
}

export async function startSession(
    goal: string,
    useMock = false,
    sessionId?: string,
): Promise<StartSessionResponse> {
    return apiClient.post(
        "/start",
        {
            goal,
            use_mock: useMock,
            session_id: sessionId,
        },
        normalizeStartSessionResponse,
    );
}

export async function stopSession(): Promise<StopSessionResponse> {
    return apiClient.post("/stop", undefined, normalizeStopSessionResponse);
}

export async function getSystemStatus(): Promise<SystemStatus> {
    return apiClient.get("/status", normalizeSystemStatus);
}

export async function fetchReport(sessionId: string): Promise<ReportData> {
    return apiClient.get(`/sessions/${sessionId}/report`, normalizeReportData);
}

export async function reloadConfig(): Promise<{ message: string }> {
    return apiClient.post("/config/reload");
}
