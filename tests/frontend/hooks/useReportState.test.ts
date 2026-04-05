import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { invalidateResourceMock, usePollingResourceMock } = vi.hoisted(() => ({
    invalidateResourceMock: vi.fn(),
    usePollingResourceMock: vi.fn(),
}));

vi.mock("@/hooks/usePollingResource", () => ({
    invalidateResource: invalidateResourceMock,
    usePollingResource: usePollingResourceMock,
}));

import { useReportState } from "@/hooks/useReportState";

describe("useReportState", () => {
    beforeEach(() => {
        invalidateResourceMock.mockReset();
        usePollingResourceMock.mockReset();
        usePollingResourceMock.mockReturnValue({
            data: {
                session_id: "session-1",
            },
            isLoading: false,
        });
    });

    it("keeps report fetching disabled until the report is opened", () => {
        const { result } = renderHook(() => useReportState("session-1"));

        expect(usePollingResourceMock).toHaveBeenLastCalledWith(
            "report:session-1",
            expect.any(Function),
            expect.objectContaining({
                enabled: false,
            }),
        );

        act(() => {
            result.current.openReport();
        });

        expect(invalidateResourceMock).toHaveBeenCalledWith("report:session-1");
        expect(usePollingResourceMock).toHaveBeenLastCalledWith(
            "report:session-1",
            expect.any(Function),
            expect.objectContaining({
                enabled: true,
            }),
        );
    });

    it("does nothing when openReport is called without a session", () => {
        const { result } = renderHook(() => useReportState(null));

        act(() => {
            result.current.openReport();
        });

        expect(result.current.showReport).toBe(false);
        expect(invalidateResourceMock).not.toHaveBeenCalled();
        expect(usePollingResourceMock).toHaveBeenLastCalledWith(
            "report:none",
            expect.any(Function),
            expect.objectContaining({
                enabled: false,
            }),
        );
    });

    it("closes the report when the session changes", () => {
        const { result, rerender } = renderHook(
            ({ sessionId }) => useReportState(sessionId),
            {
                initialProps: {
                    sessionId: "session-1" as string | null,
                },
            },
        );

        act(() => {
            result.current.openReport();
        });
        expect(result.current.showReport).toBe(true);

        rerender({ sessionId: "session-2" });

        expect(result.current.showReport).toBe(false);
    });
});
