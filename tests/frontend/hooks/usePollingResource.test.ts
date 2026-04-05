import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
    invalidateResource,
    usePollingResource,
} from "@/hooks/usePollingResource";

let keyCounter = 0;

function nextKey() {
    keyCounter += 1;
    return `test-resource-${keyCounter}`;
}

describe("usePollingResource", () => {
    beforeEach(() => {
        vi.useRealTimers();
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    it("loads data once and reuses cached data for the same key", async () => {
        const key = nextKey();
        const firstFetcher = vi.fn().mockResolvedValue(["first"]);

        const first = renderHook(() =>
            usePollingResource(key, firstFetcher, {
                initialData: [],
            }),
        );

        await waitFor(() => {
            expect(first.result.current.data).toEqual(["first"]);
        });
        expect(firstFetcher).toHaveBeenCalledTimes(1);
        first.unmount();

        const secondFetcher = vi.fn().mockResolvedValue(["second"]);
        const second = renderHook(() =>
            usePollingResource(key, secondFetcher, {
                initialData: [],
            }),
        );

        expect(second.result.current.data).toEqual(["first"]);
        expect(secondFetcher).not.toHaveBeenCalled();
    });

    it("polls on the configured interval", async () => {
        vi.useFakeTimers();
        const key = nextKey();
        const fetcher = vi
            .fn()
            .mockResolvedValueOnce(1)
            .mockResolvedValueOnce(2);

        const { result } = renderHook(() =>
            usePollingResource(key, fetcher, {
                initialData: 0,
                pollMs: 1000,
            }),
        );

        await act(async () => {
            await Promise.resolve();
            await Promise.resolve();
        });
        expect(result.current.data).toBe(1);

        await act(async () => {
            vi.advanceTimersByTime(1000);
            await Promise.resolve();
            await Promise.resolve();
        });

        expect(result.current.data).toBe(2);
    });

    it("refresh invalidates the cache and refetches the resource", async () => {
        const key = nextKey();
        const fetcher = vi
            .fn()
            .mockResolvedValueOnce("cached")
            .mockResolvedValueOnce("fresh");

        const { result } = renderHook(() =>
            usePollingResource(key, fetcher, {
                initialData: "",
            }),
        );

        await waitFor(() => {
            expect(result.current.data).toBe("cached");
        });

        await act(async () => {
            await result.current.refresh();
        });

        expect(result.current.data).toBe("fresh");
        expect(fetcher).toHaveBeenCalledTimes(2);
        invalidateResource(key);
    });

    it("does not fetch when disabled and keeps the initial value", async () => {
        const fetcher = vi.fn().mockResolvedValue("server");

        const { result } = renderHook(() =>
            usePollingResource(nextKey(), fetcher, {
                enabled: false,
                initialData: "initial",
            }),
        );

        expect(result.current.data).toBe("initial");
        expect(result.current.isLoading).toBe(false);
        expect(fetcher).not.toHaveBeenCalled();

        await act(async () => {
            await result.current.refresh();
        });

        expect(fetcher).not.toHaveBeenCalled();
        expect(result.current.data).toBe("initial");
    });

    it("clears its interval when the hook unmounts", async () => {
        vi.useFakeTimers();
        const key = nextKey();
        const fetcher = vi.fn().mockResolvedValue("value");

        const rendered = renderHook(() =>
            usePollingResource(key, fetcher, {
                initialData: "",
                pollMs: 1000,
            }),
        );

        await act(async () => {
            await Promise.resolve();
            await Promise.resolve();
        });
        expect(rendered.result.current.data).toBe("value");
        expect(fetcher).toHaveBeenCalledTimes(1);

        rendered.unmount();

        await act(async () => {
            vi.advanceTimersByTime(5000);
            await Promise.resolve();
        });

        expect(fetcher).toHaveBeenCalledTimes(1);
    });
});
