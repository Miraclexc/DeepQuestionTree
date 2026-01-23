import { SessionData, TreeResponse, Node } from "./types";

const API_HOST = process.env.NEXT_PUBLIC_API_HOST || "http://localhost";
const API_PORT = process.env.NEXT_PUBLIC_API_PORT || "8001";
const API_BASE = `${API_HOST}:${API_PORT}`;
const VISUALIZER_API = `${API_BASE}/api/visualizer`;

export async function fetchSessions(): Promise<any[]> {
    const res = await fetch(`${VISUALIZER_API}/sessions`);
    if (!res.ok) throw new Error("Failed to fetch sessions");
    return res.json();
}

export async function fetchSession(sessionId: string): Promise<SessionData> {
    const res = await fetch(`${VISUALIZER_API}/sessions/${sessionId}`);
    if (!res.ok) throw new Error("Failed to fetch session");
    return res.json();
}

export async function fetchTree(sessionId: string): Promise<TreeResponse> {
    const res = await fetch(`${VISUALIZER_API}/sessions/${sessionId}/tree`);
    if (!res.ok) throw new Error("Failed to fetch tree");
    return res.json();
}

export async function fetchNode(sessionId: string, nodeId: string): Promise<Node> {
    const res = await fetch(`${VISUALIZER_API}/sessions/${sessionId}/nodes/${nodeId}`);
    if (!res.ok) throw new Error("Failed to fetch node");
    return res.json();
}

// 删除会话
export async function deleteSession(sessionId: string): Promise<void> {
    const res = await fetch(`${VISUALIZER_API}/sessions/${sessionId}`, {
        method: "DELETE",
    });
    if (!res.ok) throw new Error("Failed to delete session");
}

export async function startSession(goal: string, useMock: boolean = false): Promise<any> {
    const res = await fetch(`${API_BASE}/api/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal, use_mock: useMock })
    });
    if (!res.ok) throw new Error("Failed to start session");
    return res.json();
}

export async function stopSession(): Promise<any> {
    const res = await fetch(`${API_BASE}/api/stop`, { method: "POST" });
    if (!res.ok) throw new Error("Failed to stop session");
    return res.json();
}

export async function getSystemStatus(): Promise<any> {
    const res = await fetch(`${API_BASE}/api/status`);
    if (!res.ok) throw new Error("Failed to get status");
    return res.json();
}

export async function fetchReport(sessionId?: string): Promise<any> {
    const url = sessionId ? `${API_BASE}/api/report?session_id=${sessionId}` : `${API_BASE}/api/report`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("Failed to fetch report");
    return res.json();
}
