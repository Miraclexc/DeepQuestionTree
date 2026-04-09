import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import DeepQuestionTree from "@/components/DeepQuestionTree";

import {
    nodeDetailFixture,
    reportFixture,
    sessionSummariesFixture,
    treeResponseFixture,
} from "../fixtures/data";

const { useDeepQuestionTreeMock } = vi.hoisted(() => ({
    useDeepQuestionTreeMock: vi.fn(),
}));

vi.mock("@/hooks/useDeepQuestionTree", () => ({
    useDeepQuestionTree: useDeepQuestionTreeMock,
}));

describe("DeepQuestionTree", () => {
    beforeEach(() => {
        useDeepQuestionTreeMock.mockReturnValue({
            currentSession: sessionSummariesFixture[0],
            currentSessionId: null,
            canGenerateReport: true,
            draftGoal: "Draft goal",
            error: "Something failed",
            generateReportDisabledReason: undefined,
            isGeneratingReport: false,
            isNewSessionDialogOpen: true,
            isLoadingTree: false,
            isNodePanelOpen: true,
            isStarting: false,
            reportData: reportFixture,
            selectedNode: nodeDetailFixture,
            sessions: sessionSummariesFixture,
            showReport: true,
            systemStatus: "connected",
            treeData: treeResponseFixture,
            onChangeNewSessionGoal: vi.fn(),
            onClearError: vi.fn(),
            onCloseNodePanel: vi.fn(),
            onCloseNewSessionDialog: vi.fn(),
            onCloseReport: vi.fn(),
            onDeleteSession: vi.fn(),
            onGenerateReport: vi.fn(),
            onOpenNewSessionDialog: vi.fn(),
            onNodeClick: vi.fn(),
            onSelectSession: vi.fn(),
            onResumeSession: vi.fn().mockResolvedValue(undefined),
            onStartSession: vi.fn().mockResolvedValue(undefined),
            onStopAndReport: vi.fn().mockResolvedValue(undefined),
        });
    });

    it("assembles the workspace shell and wires child actions to hook callbacks", async () => {
        const user = userEvent.setup();
        render(React.createElement(DeepQuestionTree));

        expect(screen.getByText("Deep Question Tree")).toBeInTheDocument();
        expect(screen.getByText("Start New Exploration")).toBeInTheDocument();
        expect(screen.getByText("Exploration Report")).toBeInTheDocument();
        expect(screen.getByText("Node Details")).toBeInTheDocument();
        expect(screen.getByText("Something failed")).toBeInTheDocument();

        await user.click(screen.getByRole("button", { name: "Dismiss" }));
        await user.click(screen.getByRole("button", { name: "Cancel" }));

        const treeState = useDeepQuestionTreeMock.mock.results[0].value;
        expect(treeState.onClearError).toHaveBeenCalled();
        expect(treeState.onCloseNewSessionDialog).toHaveBeenCalled();
    });
});
