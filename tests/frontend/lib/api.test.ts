import { beforeEach, describe, expect, it, vi } from "vitest";

const { deleteMock, getMock, postMock } = vi.hoisted(() => ({
    deleteMock: vi.fn(),
    getMock: vi.fn(),
    postMock: vi.fn(),
}));

vi.mock("@/lib/api-client", () => ({
    apiClient: {
        get: getMock,
        post: postMock,
        delete: deleteMock,
    },
}));

describe("api wrappers", () => {
    beforeEach(() => {
        deleteMock.mockReset();
        getMock.mockReset();
        postMock.mockReset();
    });

    it("passes normalized start-session payloads through the api client", async () => {
        const { startSession } = await import("@/lib/api");
        const { normalizeStartSessionResponse } = await import("@/lib/contracts");

        await startSession("Investigate grid storage", true, "session-1");

        expect(postMock).toHaveBeenCalledWith(
            "/start",
            {
                goal: "Investigate grid storage",
                use_mock: true,
                session_id: "session-1",
            },
            normalizeStartSessionResponse,
        );
    });

    it("routes report fetching and delete calls to the expected endpoints", async () => {
        const { deleteSession, fetchReport } = await import("@/lib/api");
        const { normalizeReportData } = await import("@/lib/contracts");

        await fetchReport("session-9");
        await deleteSession("session-9");

        expect(getMock).toHaveBeenCalledWith(
            "/sessions/session-9/report",
            normalizeReportData,
        );
        expect(deleteMock).toHaveBeenCalledWith("/sessions/session-9");
    });
});
