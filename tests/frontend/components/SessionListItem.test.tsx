import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SessionListItem } from "@/components/sidebar/SessionListItem";

import { sessionSummariesFixture } from "../fixtures/data";

describe("SessionListItem", () => {
    beforeEach(() => {
        vi.mocked(confirm).mockReturnValue(true);
    });

    it("selects the session when its main area is clicked", async () => {
        const user = userEvent.setup();
        const onSelect = vi.fn();

        render(
            React.createElement(SessionListItem, {
                session: sessionSummariesFixture[0],
                selected: false,
                onSelect,
                onResume: vi.fn(),
                onDelete: vi.fn(),
            }),
        );

        await user.click(
            screen.getByRole("button", {
                name: /Assess battery recycling policy impacts/i,
            }),
        );

        expect(onSelect).toHaveBeenCalledWith("session-1");
    });

    it("deletes the session after a positive confirmation", async () => {
        const user = userEvent.setup();
        const onDelete = vi.fn();

        render(
            React.createElement(SessionListItem, {
                session: sessionSummariesFixture[0],
                selected: true,
                onSelect: vi.fn(),
                onResume: vi.fn(),
                onDelete,
            }),
        );

        await user.click(screen.getByTitle("Delete Session"));

        expect(confirm).toHaveBeenCalled();
        expect(onDelete).toHaveBeenCalledWith("session-1");
    });

    it("shows resume for resumable sessions and calls onResume", async () => {
        const user = userEvent.setup();
        const onResume = vi.fn();

        render(
            React.createElement(SessionListItem, {
                session: sessionSummariesFixture[1],
                selected: false,
                onSelect: vi.fn(),
                onResume,
                onDelete: vi.fn(),
            }),
        );

        await user.click(screen.getByTitle("Resume Session"));

        expect(onResume).toHaveBeenCalledWith("session-2");
    });

    it("does not show resume for running sessions", () => {
        render(
            React.createElement(SessionListItem, {
                session: sessionSummariesFixture[0],
                selected: false,
                onSelect: vi.fn(),
                onResume: vi.fn(),
                onDelete: vi.fn(),
            }),
        );

        expect(screen.queryByTitle("Resume Session")).not.toBeInTheDocument();
    });
});
