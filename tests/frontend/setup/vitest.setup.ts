import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, beforeEach, vi } from "vitest";

import { server } from "../msw/server";

const originalCreateObjectURL = globalThis.URL.createObjectURL;
const originalRevokeObjectURL = globalThis.URL.revokeObjectURL;

beforeAll(() => {
    server.listen({ onUnhandledRequest: "error" });
});

beforeEach(() => {
    vi.stubGlobal("confirm", vi.fn(() => true));
    vi.stubGlobal("alert", vi.fn());
    Object.defineProperty(globalThis.navigator, "clipboard", {
        configurable: true,
        value: {
            writeText: vi.fn().mockResolvedValue(undefined),
        },
    });
    globalThis.URL.createObjectURL = vi.fn(() => "blob:test-url");
    globalThis.URL.revokeObjectURL = vi.fn();
});

afterEach(() => {
    cleanup();
    server.resetHandlers();
    window.localStorage.clear();
    vi.clearAllMocks();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    globalThis.URL.createObjectURL = originalCreateObjectURL;
    globalThis.URL.revokeObjectURL = originalRevokeObjectURL;
});

afterAll(() => {
    server.close();
});
