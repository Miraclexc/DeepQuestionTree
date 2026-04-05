import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ReportView } from "@/components/ReportView";

import { reportFixture } from "../fixtures/data";
import {
    html2pdfFromMock,
    html2pdfSaveMock,
    html2pdfSetMock,
    resetHtml2pdfMocks,
} from "../setup/stubs/html2pdf";

describe("ReportView", () => {
    beforeEach(() => {
        resetHtml2pdfMocks();
    });

    it("stays hidden when there is no report and no loading state", () => {
        const { container } = render(
            React.createElement(ReportView, {
                report: null,
                isLoading: false,
                onClose: vi.fn(),
            }),
        );

        expect(container).toBeEmptyDOMElement();
    });

    it("renders loading feedback", () => {
        render(
            React.createElement(ReportView, {
                report: null,
                isLoading: true,
                onClose: vi.fn(),
            }),
        );

        expect(
            screen.getByText("Compiling insights and analyzing paths..."),
        ).toBeInTheDocument();
    });

    it("renders report content, switches tabs and exports artifacts", async () => {
        const user = userEvent.setup();

        render(
            React.createElement(ReportView, {
                report: reportFixture,
                isLoading: false,
                onClose: vi.fn(),
            }),
        );

        expect(screen.getByText("Exploration Report")).toBeInTheDocument();
        expect(screen.getByText("Executive Summary")).toBeInTheDocument();

        await user.click(screen.getByRole("button", { name: /Pruned Paths/i }));
        expect(screen.getByText("Pruned Paths & Dead Ends")).toBeInTheDocument();

        await user.click(screen.getByRole("button", { name: /LLM Usage/i }));
        expect(screen.getByText("LLM Utilization")).toBeInTheDocument();

        await user.click(screen.getByTitle("Export PDF"));
        await user.click(screen.getByTitle("Download JSON"));

        await waitFor(() => {
            expect(html2pdfSetMock).toHaveBeenCalled();
        });
        expect(html2pdfFromMock).toHaveBeenCalled();
        expect(html2pdfSaveMock).toHaveBeenCalled();
        expect(URL.createObjectURL).toHaveBeenCalled();
        expect(URL.revokeObjectURL).toHaveBeenCalled();
    });
});
