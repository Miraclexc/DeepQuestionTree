import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useNodeDetails } from "@/hooks/useNodeDetails";

import { nodeDetailFixture } from "../fixtures/data";

const { fetchNodeMock } = vi.hoisted(() => ({
    fetchNodeMock: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
    fetchNode: fetchNodeMock,
}));

describe("useNodeDetails", () => {
    beforeEach(() => {
        fetchNodeMock.mockReset();
    });

    it("refuses to fetch node details when there is no active session", async () => {
        const { result } = renderHook(() => useNodeDetails(null));

        await act(async () => {
            await result.current.openNode("node-1");
        });

        expect(fetchNodeMock).not.toHaveBeenCalled();
        expect(result.current.selectedNode).toBeNull();
        expect(result.current.isNodePanelOpen).toBe(false);
    });

    it("opens the node panel after fetching node details", async () => {
        fetchNodeMock.mockResolvedValue(nodeDetailFixture);

        const { result } = renderHook(() => useNodeDetails("session-1"));

        await act(async () => {
            await result.current.openNode("child-node");
        });

        await waitFor(() => {
            expect(result.current.selectedNode).toEqual(nodeDetailFixture);
        });
        expect(fetchNodeMock).toHaveBeenCalledWith("session-1", "child-node");
        expect(result.current.isNodePanelOpen).toBe(true);
    });

    it("clears the selected node when the session changes", async () => {
        fetchNodeMock.mockResolvedValue(nodeDetailFixture);

        const { result, rerender } = renderHook(
            ({ sessionId }) => useNodeDetails(sessionId),
            {
                initialProps: {
                    sessionId: "session-1" as string | null,
                },
            },
        );

        await act(async () => {
            await result.current.openNode("child-node");
        });
        expect(result.current.selectedNode?.id).toBe("child-node");
        expect(result.current.isNodePanelOpen).toBe(true);

        rerender({ sessionId: "session-2" });

        expect(result.current.selectedNode).toBeNull();
        expect(result.current.isNodePanelOpen).toBe(false);
    });
});
