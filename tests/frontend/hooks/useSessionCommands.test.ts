import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const {
    deleteSessionMock,
    startSessionApiMock,
    stopSessionMock,
    invalidateResourceMock,
    invalidateResourcePrefixMock,
} = vi.hoisted(() => ({
    deleteSessionMock: vi.fn(),
    startSessionApiMock: vi.fn(),
    stopSessionMock: vi.fn(),
    invalidateResourceMock: vi.fn(),
    invalidateResourcePrefixMock: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
    deleteSession: deleteSessionMock,
    startSession: startSessionApiMock,
    stopSession: stopSessionMock,
}));

vi.mock("@/hooks/usePollingResource", () => ({
    invalidateResource: invalidateResourceMock,
    invalidateResourcePrefix: invalidateResourcePrefixMock,
}));

import { useSessionCommands } from "@/hooks/useSessionCommands";

describe("useSessionCommands", () => {
    beforeEach(() => {
        deleteSessionMock.mockReset();
        invalidateResourceMock.mockReset();
        invalidateResourcePrefixMock.mockReset();
        startSessionApiMock.mockReset();
        stopSessionMock.mockReset();
    });

    it("starts a session, refreshes cache and selects the new session", async () => {
        startSessionApiMock.mockResolvedValue({
            session_id: "session-9",
        });

        const refreshSessions = vi.fn().mockResolvedValue(undefined);
        const refreshStatus = vi.fn().mockResolvedValue(undefined);
        const onSelectSession = vi.fn();
        const onResetWorkspacePanels = vi.fn();

        const { result } = renderHook(() =>
            useSessionCommands({
                currentSessionId: null,
                refreshSessions,
                refreshStatus,
                onSelectSession,
                onOpenReport: vi.fn(),
                onResetWorkspacePanels,
                onResetCurrentSession: vi.fn(),
            }),
        );

        act(() => {
            result.current.openNewSessionDialog();
            result.current.changeNewSessionGoal("Assess solid-state battery risks");
        });

        await act(async () => {
            await result.current.startSession();
        });

        expect(startSessionApiMock).toHaveBeenCalledWith(
            "Assess solid-state battery risks",
        );
        expect(invalidateResourceMock).toHaveBeenCalledWith("system-status");
        expect(invalidateResourceMock).toHaveBeenCalledWith("sessions");
        expect(invalidateResourcePrefixMock).toHaveBeenCalledWith("tree:");
        expect(invalidateResourcePrefixMock).toHaveBeenCalledWith("report:");
        expect(refreshSessions).toHaveBeenCalled();
        expect(refreshStatus).toHaveBeenCalled();
        expect(onSelectSession).toHaveBeenCalledWith("session-9");
        expect(onResetWorkspacePanels).not.toHaveBeenCalled();
        expect(result.current.isNewSessionDialogOpen).toBe(false);
        expect(result.current.draftGoal).toBe("");
    });

    it("deletes the active session and resets current selection", async () => {
        deleteSessionMock.mockResolvedValue(undefined);
        const refreshSessions = vi.fn().mockResolvedValue(undefined);
        const onResetCurrentSession = vi.fn();

        const { result } = renderHook(() =>
            useSessionCommands({
                currentSessionId: "session-1",
                refreshSessions,
                refreshStatus: vi.fn().mockResolvedValue(undefined),
                onSelectSession: vi.fn(),
                onOpenReport: vi.fn(),
                onResetWorkspacePanels: vi.fn(),
                onResetCurrentSession,
            }),
        );

        await act(async () => {
            await result.current.deleteSession("session-1");
        });

        expect(deleteSessionMock).toHaveBeenCalledWith("session-1");
        expect(invalidateResourceMock).toHaveBeenCalledWith("sessions");
        expect(invalidateResourcePrefixMock).toHaveBeenCalledWith("tree:session-1");
        expect(invalidateResourcePrefixMock).toHaveBeenCalledWith("report:session-1");
        expect(refreshSessions).toHaveBeenCalled();
        expect(onResetCurrentSession).toHaveBeenCalled();
    });

    it("stops the active session and opens the report flow", async () => {
        stopSessionMock.mockResolvedValue(undefined);
        const refreshSessions = vi.fn().mockResolvedValue(undefined);
        const refreshStatus = vi.fn().mockResolvedValue(undefined);
        const onOpenReport = vi.fn();

        const { result } = renderHook(() =>
            useSessionCommands({
                currentSessionId: "session-1",
                refreshSessions,
                refreshStatus,
                onSelectSession: vi.fn(),
                onOpenReport,
                onResetWorkspacePanels: vi.fn(),
                onResetCurrentSession: vi.fn(),
            }),
        );

        await act(async () => {
            await result.current.stopAndReport();
        });

        expect(stopSessionMock).toHaveBeenCalled();
        expect(invalidateResourceMock).toHaveBeenCalledWith("system-status");
        expect(invalidateResourceMock).toHaveBeenCalledWith("sessions");
        expect(refreshStatus).toHaveBeenCalled();
        expect(refreshSessions).toHaveBeenCalled();
        expect(onOpenReport).toHaveBeenCalled();
    });

    it("resumes an existing session, clears transient panels and reselects it", async () => {
        startSessionApiMock.mockResolvedValue({
            session_id: "session-2",
        });
        const refreshSessions = vi.fn().mockResolvedValue(undefined);
        const refreshStatus = vi.fn().mockResolvedValue(undefined);
        const onSelectSession = vi.fn();
        const onResetWorkspacePanels = vi.fn();

        const { result } = renderHook(() =>
            useSessionCommands({
                currentSessionId: "session-1",
                refreshSessions,
                refreshStatus,
                onSelectSession,
                onOpenReport: vi.fn(),
                onResetWorkspacePanels,
                onResetCurrentSession: vi.fn(),
            }),
        );

        await act(async () => {
            await result.current.resumeSession({
                session_id: "session-2",
                global_goal: "Map data center power constraints",
            });
        });

        expect(startSessionApiMock).toHaveBeenCalledWith(
            "Map data center power constraints",
            false,
            "session-2",
        );
        expect(invalidateResourceMock).toHaveBeenCalledWith("system-status");
        expect(invalidateResourceMock).toHaveBeenCalledWith("sessions");
        expect(invalidateResourcePrefixMock).toHaveBeenCalledWith("tree:");
        expect(invalidateResourcePrefixMock).toHaveBeenCalledWith("report:");
        expect(refreshSessions).toHaveBeenCalled();
        expect(refreshStatus).toHaveBeenCalled();
        expect(onResetWorkspacePanels).toHaveBeenCalled();
        expect(onSelectSession).toHaveBeenCalledWith("session-2");
    });
});
