import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MarkdownRenderer } from "@/components/MarkdownRenderer";

describe("MarkdownRenderer", () => {
    it("renders markdown content and copies the raw source", async () => {
        const user = userEvent.setup();
        const markdown = "# Heading\n\n`inline`\n\n```ts\nconst value = 1;\n```";
        const writeTextMock = vi.spyOn(navigator.clipboard, "writeText");

        render(
            React.createElement(MarkdownRenderer, {
                content: markdown,
            }),
        );

        expect(screen.getByText("Heading")).toBeInTheDocument();
        expect(screen.getByText("inline")).toBeInTheDocument();
        expect(screen.getByText("const value = 1;")).toBeInTheDocument();

        await user.click(screen.getByTitle("Copy raw content"));

        expect(writeTextMock).toHaveBeenCalledWith(markdown);
    });
});
