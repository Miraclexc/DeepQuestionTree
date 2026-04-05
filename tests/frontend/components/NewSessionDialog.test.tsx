import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { NewSessionDialog } from "@/components/workspace/NewSessionDialog";

describe("NewSessionDialog", () => {
    it("stays hidden when closed", () => {
        const { container } = render(
            React.createElement(NewSessionDialog, {
                open: false,
                draftGoal: "",
                isStarting: false,
                onClose: vi.fn(),
                onStart: vi.fn(),
                onChangeGoal: vi.fn(),
            }),
        );

        expect(container).toBeEmptyDOMElement();
    });

    it("updates the draft goal and triggers the start and close handlers", async () => {
        const user = userEvent.setup();
        const onClose = vi.fn();
        const onChangeGoal = vi.fn();
        const onStart = vi.fn().mockResolvedValue(undefined);

        render(
            React.createElement(NewSessionDialog, {
                open: true,
                draftGoal: "Current draft",
                isStarting: false,
                onClose,
                onStart,
                onChangeGoal,
            }),
        );

        await user.type(
            screen.getByPlaceholderText(
                "e.g. Analyze the impact of quantum computing on cryptography...",
            ),
            " extended",
        );
        await user.click(screen.getByRole("button", { name: "Cancel" }));
        await user.click(screen.getByRole("button", { name: "Start Analysis" }));

        expect(onChangeGoal).toHaveBeenCalled();
        expect(onClose).toHaveBeenCalled();
        expect(onStart).toHaveBeenCalled();
    });

    it("disables the start button for blank goals or while starting", () => {
        const { rerender } = render(
            React.createElement(NewSessionDialog, {
                open: true,
                draftGoal: "   ",
                isStarting: false,
                onClose: vi.fn(),
                onStart: vi.fn(),
                onChangeGoal: vi.fn(),
            }),
        );

        expect(screen.getByRole("button", { name: "Start Analysis" })).toBeDisabled();

        rerender(
            React.createElement(NewSessionDialog, {
                open: true,
                draftGoal: "Valid goal",
                isStarting: true,
                onClose: vi.fn(),
                onStart: vi.fn(),
                onChangeGoal: vi.fn(),
            }),
        );

        expect(screen.getByRole("button", { name: "Start Analysis" })).toBeDisabled();
    });
});
