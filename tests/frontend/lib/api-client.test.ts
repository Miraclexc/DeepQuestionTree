import {
    http,
    HttpResponse,
} from "../../../src/frontend/node_modules/msw/lib/core/index.mjs";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { server } from "../msw/server";

describe("apiClient", () => {
    beforeEach(() => {
        vi.resetModules();
    });

    it("prefers localStorage token over NEXT_PUBLIC_API_TOKEN", async () => {
        vi.stubEnv("NEXT_PUBLIC_API_TOKEN", "env-token");
        window.localStorage.setItem("dqt.apiToken", "local-token");

        let authorizationHeader = "";
        server.use(
            http.get("http://localhost:8001/api/status", ({ request }) => {
                authorizationHeader = request.headers.get("authorization") ?? "";
                return HttpResponse.json({ ok: true });
            }),
        );

        const { apiClient } = await import("@/lib/api-client");
        await apiClient.get("/status");

        expect(authorizationHeader).toBe("Bearer local-token");
    });

    it("returns undefined for 204 delete responses", async () => {
        server.use(
            http.delete("http://localhost:8001/api/sessions/session-1", () => {
                return new HttpResponse(null, { status: 204 });
            }),
        );

        const { apiClient } = await import("@/lib/api-client");

        await expect(apiClient.delete("/sessions/session-1")).resolves.toBeUndefined();
    });

    it("maps error payloads to ApiClientError and clears the bus after a later success", async () => {
        server.use(
            http.post("http://localhost:8001/api/start", () =>
                HttpResponse.json(
                    {
                        detail: "Bad token",
                        code: "invalid_token",
                    },
                    { status: 401 },
                ),
            ),
        );

        const {
            ApiClientError,
            apiClient,
            getLatestApiError,
            subscribeToApiErrors,
        } = await import("@/lib/api-client");
        const listener = vi.fn();
        const unsubscribe = subscribeToApiErrors(listener);

        await expect(apiClient.post("/start", { goal: "x" })).rejects.toBeInstanceOf(
            ApiClientError,
        );
        expect(getLatestApiError()).toMatchObject({
            message: "Bad token",
            status: 401,
            code: "invalid_token",
        });

        server.use(
            http.get("http://localhost:8001/api/status", () =>
                HttpResponse.json({ ready: true }),
            ),
        );

        await apiClient.get("/status");

        expect(listener).toHaveBeenNthCalledWith(
            1,
            expect.objectContaining({
                message: "Bad token",
                status: 401,
            }),
        );
        expect(listener).toHaveBeenLastCalledWith(null);
        expect(getLatestApiError()).toBeNull();
        unsubscribe();
    });
});
