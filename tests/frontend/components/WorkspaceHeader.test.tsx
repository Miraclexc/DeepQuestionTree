import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspaceHeader } from "@/components/workspace/WorkspaceHeader";

import { sessionSummariesFixture } from "../fixtures/data";

describe("WorkspaceHeader", () => {
    beforeEach(() => {
        vi.mocked(confirm).mockReturnValue(true);
    });

    it("shows the active session metadata and routes header actions", async () => {
        const user = userEvent.setup();
        const onGenerateReport = vi.fn();
        const onStopAndReport = vi.fn().mockResolvedValue(undefined);

        render(
            React.createElement(WorkspaceHeader, {
                currentSession: sessionSummariesFixture[0],
                currentSessionId: "session-1",
                canGenerateReport: true,
                onGenerateReport,
                onStopAndReport,
            }),
        );

        await user.click(screen.getByRole("button", { name: "Stop & Report" }));
        await user.click(screen.getByRole("button", { name: "Generate Report" }));

        expect(confirm).toHaveBeenCalled();
        expect(onStopAndReport).toHaveBeenCalled();
        expect(onGenerateReport).toHaveBeenCalled();
        expect(screen.getByText("Running Explorations")).toBeInTheDocument();
        expect(screen.getByText("ID: session-")).toBeInTheDocument();
    });

    it("blocks stop-and-report when the confirmation is rejected", async () => {
        vi.mocked(confirm).mockReturnValue(false);
        const user = userEvent.setup();
        const onStopAndReport = vi.fn().mockResolvedValue(undefined);

        render(
            React.createElement(WorkspaceHeader, {
                currentSession: sessionSummariesFixture[0],
                currentSessionId: "session-1",
                canGenerateReport: true,
                onGenerateReport: vi.fn(),
                onStopAndReport,
            }),
        );

        await user.click(screen.getByRole("button", { name: "Stop & Report" }));

        expect(onStopAndReport).not.toHaveBeenCalled();
    });

    it("shows the empty workspace title when no session is selected", () => {
        render(
            React.createElement(WorkspaceHeader, {
                currentSession: null,
                currentSessionId: null,
                canGenerateReport: false,
                onGenerateReport: vi.fn(),
                onStopAndReport: vi.fn(),
            }),
        );

        expect(screen.getByText("Deep Question Tree")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Generate Report" })).not.toBeInTheDocument();
    });

    it("disables generate report when legacy session has no reusable report", () => {
        render(
            React.createElement(WorkspaceHeader, {
                currentSession: {
                    ...sessionSummariesFixture[1],
                    is_legacy_token_accounting: true,
                },
                currentSessionId: "session-2",
                canGenerateReport: false,
                generateReportDisabledReason: "Legacy sessions without cached reports are read-only.",
                onGenerateReport: vi.fn(),
                onStopAndReport: vi.fn(),
            }),
        );

        expect(screen.getByRole("button", { name: "Generate Report" })).toBeDisabled();
        expect(
            screen.getByRole("button", { name: "Generate Report" }),
        ).toHaveAttribute(
            "title",
            "Legacy sessions without cached reports are read-only.",
        );
    });
});
