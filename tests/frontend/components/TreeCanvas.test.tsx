import React from "react";
import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { treeResponseFixture } from "../fixtures/data";

vi.mock("@/components/tree/TreeNodeCard", () => ({
    TreeNodeCard: () =>
        React.createElement("div", { "data-testid": "tree-node-card" }),
}));

describe("TreeCanvas", () => {
    beforeEach(() => {
        vi.stubGlobal(
            "ResizeObserver",
            class ResizeObserver {
                observe() {}
                unobserve() {}
                disconnect() {}
            },
        );
    });

    it("does not schedule another viewport fit when only node payload changes", async () => {
        const requestAnimationFrameMock = vi.fn(
            (callback: FrameRequestCallback) => {
                callback(0);
                return 1;
            },
        );
        vi.stubGlobal("requestAnimationFrame", requestAnimationFrameMock);

        const { TreeCanvas } = await import("@/components/TreeCanvas");
        const initialNodes = treeResponseFixture.nodes;
        const initialEdges = treeResponseFixture.edges;
        const updatedNodes = initialNodes.map((node) =>
            node.id === "child-node"
                ? {
                      ...node,
                      data: {
                          ...node.data,
                          visits: node.data.visits + 1,
                          answer: "Updated answer",
                      },
                  }
                : node,
        );

        const { rerender } = render(
            <TreeCanvas
                nodes={initialNodes}
                edges={initialEdges}
                onNodeClick={vi.fn()}
            />,
        );

        await waitFor(() => {
            expect(requestAnimationFrameMock.mock.calls.length).toBeGreaterThan(0);
        });
        const initialCallCount = requestAnimationFrameMock.mock.calls.length;

        rerender(
            <TreeCanvas
                nodes={updatedNodes}
                edges={initialEdges}
                onNodeClick={vi.fn()}
            />,
        );

        await waitFor(() => {
            expect(requestAnimationFrameMock.mock.calls.length).toBe(
                initialCallCount,
            );
        });
    });
});
