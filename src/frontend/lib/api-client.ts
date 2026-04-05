"use client";

import { ApiErrorPayload } from "./types";

const API_HOST = process.env.NEXT_PUBLIC_API_HOST || "http://localhost";
const API_PORT = process.env.NEXT_PUBLIC_API_PORT || "8001";
const API_BASE = `${API_HOST}:${API_PORT}/api`;
const API_TOKEN_KEY = "dqt.apiToken";
const DEFAULT_API_TOKEN = process.env.NEXT_PUBLIC_API_TOKEN || "dev-token";

export class ApiClientError extends Error {
    status: number;
    code: string;

    constructor(message: string, status: number, code = "request_error") {
        super(message);
        this.name = "ApiClientError";
        this.status = status;
        this.code = code;
    }
}

type ApiErrorListener = (error: ApiClientError | null) => void;
type Normalizer<T> = (payload: unknown) => T;

const listeners = new Set<ApiErrorListener>();
let latestError: ApiClientError | null = null;

function emitApiError(error: ApiClientError | null) {
    latestError = error;
    for (const listener of Array.from(listeners)) {
        listener(error);
    }
}

function resolveToken(): string {
    if (typeof window !== "undefined") {
        const storedToken = window.localStorage.getItem(API_TOKEN_KEY);
        if (storedToken) {
            return storedToken;
        }
    }
    return DEFAULT_API_TOKEN;
}

function buildHeaders(headers?: HeadersInit): Headers {
    const nextHeaders = new Headers(headers);
    nextHeaders.set("Accept", "application/json");

    if (!nextHeaders.has("Content-Type")) {
        nextHeaders.set("Content-Type", "application/json");
    }

    nextHeaders.set("Authorization", `Bearer ${resolveToken()}`);
    return nextHeaders;
}

async function readErrorPayload(response: Response): Promise<ApiErrorPayload | null> {
    try {
        const payload = (await response.json()) as ApiErrorPayload;
        if (payload && typeof payload.detail === "string" && typeof payload.code === "string") {
            return payload;
        }
    } catch {
        return null;
    }

    return null;
}

async function request<T>(
    path: string,
    options: RequestInit,
    normalize?: Normalizer<T>,
): Promise<T> {
    const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers: buildHeaders(options.headers),
    });

    if (!response.ok) {
        const payload = await readErrorPayload(response);
        const error = new ApiClientError(
            payload?.detail || `Request failed: ${response.status}`,
            response.status,
            payload?.code || "request_error",
        );
        emitApiError(error);
        throw error;
    }

    if (response.status === 204) {
        emitApiError(null);
        return undefined as T;
    }

    const payload = (await response.json()) as unknown;
    const data = normalize ? normalize(payload) : (payload as T);
    emitApiError(null);
    return data;
}

export const apiClient = {
    get<T>(path: string, normalize?: Normalizer<T>) {
        return request<T>(path, { method: "GET" }, normalize);
    },
    post<T>(path: string, body?: unknown, normalize?: Normalizer<T>) {
        return request<T>(
            path,
            {
                method: "POST",
                body: body === undefined ? undefined : JSON.stringify(body),
            },
            normalize,
        );
    },
    delete(path: string) {
        return request<void>(path, { method: "DELETE" });
    },
};

export function subscribeToApiErrors(listener: ApiErrorListener): () => void {
    listeners.add(listener);
    return () => {
        listeners.delete(listener);
    };
}

export function getLatestApiError(): ApiClientError | null {
    return latestError;
}

export function clearLatestApiError(): void {
    emitApiError(null);
}
