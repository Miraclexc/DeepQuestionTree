import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ErrorBanner } from "@/components/workspace/ErrorBanner";

describe("ErrorBanner", () => {
    it("stays hidden when no message is provided", () => {
        const { container } = render(
            React.createElement(ErrorBanner, {
                message: null,
                onDismiss: vi.fn(),
            }),
        );

        expect(container).toBeEmptyDOMElement();
    });

    it("renders the error and dismisses it", async () => {
        const user = userEvent.setup();
        const onDismiss = vi.fn();

        render(
            React.createElement(ErrorBanner, {
                message: "Request failed",
                onDismiss,
            }),
        );

        expect(screen.getByText("Request failed")).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Dismiss" }));
        expect(onDismiss).toHaveBeenCalled();
    });
});
