"use client";

import { useEffect, useState } from "react";

import {
    clearLatestApiError,
    getLatestApiError,
    subscribeToApiErrors,
} from "@/lib/api-client";

export function useGlobalApiError() {
    const [error, setError] = useState(() => getLatestApiError());

    useEffect(() => {
        return subscribeToApiErrors(setError);
    }, []);

    return {
        error: error?.message ?? null,
        clearError: () => clearLatestApiError(),
    };
}

