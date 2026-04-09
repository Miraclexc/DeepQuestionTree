import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
    invalidateResource,
    invalidateResourcePrefix,
} from "@/hooks/usePollingResource";

import {
    sessionSummariesFixture,
    systemStatusFixture,
    treeResponseFixture,
} from "../fixtures/data";

const {
    fetchSessionMock,
    fetchSessionsMock,
    fetchTreeMock,
    getSystemStatusMock,
    useGlobalApiErrorMock,
    useNodeDetailsMock,
    useReportStateMock,
    useSessionCommandsMock,
} = vi.hoisted(() => ({
    fetchSessionMock: vi.fn(),
    fetchSessionsMock: vi.fn(),
    fetchTreeMock: vi.fn(),
    getSystemStatusMock: vi.fn(),
    useGlobalApiErrorMock: vi.fn(),
    useNodeDetailsMock: vi.fn(),
    useReportStateMock: vi.fn(),
    useSessionCommandsMock: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
    fetchSession: fetchSessionMock,
    fetchSessions: fetchSessionsMock,
    fetchTree: fetchTreeMock,
    getSystemStatus: getSystemStatusMock,
}));

vi.mock("@/hooks/useGlobalApiError", () => ({
    useGlobalApiError: useGlobalApiErrorMock,
}));

vi.mock("@/hooks/useNodeDetails", () => ({
    useNodeDetails: useNodeDetailsMock,
}));

vi.mock("@/hooks/useReportState", () => ({
    useReportState: useReportStateMock,
}));

vi.mock("@/hooks/useSessionCommands", () => ({
    useSessionCommands: useSessionCommandsMock,
}));

function flushMicrotasks() {
    return act(async () => {
        await Promise.resolve();
        await Promise.resolve();
    });
}

describe("useDeepQuestionTree", () => {
    beforeEach(() => {
        vi.useFakeTimers();
        fetchSessionsMock.mockReset();
        fetchSessionMock.mockReset();
        fetchTreeMock.mockReset();
        getSystemStatusMock.mockReset();
        useGlobalApiErrorMock.mockReturnValue({
            error: null,
            clearError: vi.fn(),
        });
        useNodeDetailsMock.mockReturnValue({
            isNodePanelOpen: false,
            selectedNode: null,
            openNode: vi.fn(),
            closeNode: vi.fn(),
            clearNode: vi.fn(),
        });
        useReportStateMock.mockReturnValue({
            isGeneratingReport: false,
            reportData: null,
            showReport: false,
            openReport: vi.fn(),
            closeReport: vi.fn(),
        });
        useSessionCommandsMock.mockReturnValue({
            draftGoal: "",
            isNewSessionDialogOpen: false,
            isStarting: false,
            changeNewSessionGoal: vi.fn(),
            closeNewSessionDialog: vi.fn(),
            deleteSession: vi.fn(),
            openNewSessionDialog: vi.fn(),
            startSession: vi.fn(),
            stopAndReport: vi.fn(),
        });
        fetchSessionsMock.mockResolvedValue(sessionSummariesFixture);
        fetchSessionMock.mockResolvedValue({
            session_id: "session-1",
            root_node_id: "root-node",
            global_goal: sessionSummariesFixture[0].global_goal,
            total_simulations: 2,
            total_tokens_used: 0,
            is_legacy_token_accounting: false,
            created_at: sessionSummariesFixture[0].created_at,
            updated_at: sessionSummariesFixture[0].updated_at,
            status: sessionSummariesFixture[0].status,
            error_message: null,
            total_nodes: 3,
            total_facts: 4,
            report_available: false,
            is_active: true,
        });
        invalidateResource("sessions");
        invalidateResource("system-status");
        invalidateResourcePrefix("session:");
        invalidateResourcePrefix("tree:");
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    it("does not refetch the tree when the active session revision stays the same", async () => {
        const { useDeepQuestionTree } = await import("@/hooks/useDeepQuestionTree");
        const stableStatus = {
            ...systemStatusFixture,
            session_revision: 1,
            session_error_message: null,
        };
        getSystemStatusMock.mockResolvedValue(stableStatus);
        fetchTreeMock.mockResolvedValue({
            ...treeResponseFixture,
            session_revision: 1,
        });

        const { result } = renderHook(() => useDeepQuestionTree());
        await flushMicrotasks();

        act(() => {
            result.current.onSelectSession("session-1");
        });
        await flushMicrotasks();
        expect(fetchTreeMock).toHaveBeenCalledTimes(1);

        await act(async () => {
            vi.advanceTimersByTime(5000);
            await Promise.resolve();
            await Promise.resolve();
        });

        expect(fetchTreeMock).toHaveBeenCalledTimes(1);
    });

    it("refetches the tree exactly once when the active session revision changes", async () => {
        const { useDeepQuestionTree } = await import("@/hooks/useDeepQuestionTree");
        let statusCall = 0;
        getSystemStatusMock.mockImplementation(async () => {
            statusCall += 1;
            return {
                ...systemStatusFixture,
                session_revision: statusCall >= 2 ? 2 : 1,
                session_error_message: null,
            };
        });
        fetchTreeMock
            .mockResolvedValueOnce({
                ...treeResponseFixture,
                session_revision: 1,
            })
            .mockResolvedValueOnce({
                ...treeResponseFixture,
                session_revision: 2,
            });

        const { result } = renderHook(() => useDeepQuestionTree());
        await flushMicrotasks();

        act(() => {
            result.current.onSelectSession("session-1");
        });
        await flushMicrotasks();
        expect(fetchTreeMock).toHaveBeenCalledTimes(1);

        await act(async () => {
            vi.advanceTimersByTime(5000);
            await Promise.resolve();
            await Promise.resolve();
        });

        expect(fetchTreeMock).toHaveBeenCalledTimes(2);
    });
});
