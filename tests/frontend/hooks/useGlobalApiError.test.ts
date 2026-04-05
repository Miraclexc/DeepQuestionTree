import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

type Listener = (error: { message: string } | null) => void;

const {
    clearLatestApiErrorMock,
    getLatestApiErrorMock,
    subscribeToApiErrorsMock,
    unsubscribeMock,
} = vi.hoisted(() => ({
    clearLatestApiErrorMock: vi.fn(),
    getLatestApiErrorMock: vi.fn(),
    subscribeToApiErrorsMock: vi.fn(),
    unsubscribeMock: vi.fn(),
}));
let activeListener: Listener | null = null;

vi.mock("@/lib/api-client", () => ({
    clearLatestApiError: clearLatestApiErrorMock,
    getLatestApiError: getLatestApiErrorMock,
    subscribeToApiErrors: subscribeToApiErrorsMock,
}));

import { useGlobalApiError } from "@/hooks/useGlobalApiError";

describe("useGlobalApiError", () => {
    beforeEach(() => {
        activeListener = null;
        clearLatestApiErrorMock.mockReset();
        getLatestApiErrorMock.mockReset();
        subscribeToApiErrorsMock.mockReset();
        unsubscribeMock.mockReset();
        getLatestApiErrorMock.mockReturnValue({ message: "Initial failure" });
        subscribeToApiErrorsMock.mockImplementation((listener: Listener) => {
            activeListener = listener;
            return unsubscribeMock;
        });
    });

    it("reads the latest error and updates when the bus publishes new values", () => {
        const { result } = renderHook(() => useGlobalApiError());

        expect(result.current.error).toBe("Initial failure");

        act(() => {
            activeListener?.({ message: "Updated failure" });
        });
        expect(result.current.error).toBe("Updated failure");

        act(() => {
            activeListener?.(null);
        });
        expect(result.current.error).toBeNull();
    });

    it("clears the error and unsubscribes on unmount", () => {
        const rendered = renderHook(() => useGlobalApiError());

        act(() => {
            rendered.result.current.clearError();
        });
        expect(clearLatestApiErrorMock).toHaveBeenCalled();

        rendered.unmount();
        expect(unsubscribeMock).toHaveBeenCalled();
    });
});
