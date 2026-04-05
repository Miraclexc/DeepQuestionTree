"use client";

import { startTransition, useEffect, useRef, useState } from "react";

type QueryOptions<T> = {
    enabled?: boolean;
    initialData: T;
    pollMs?: number;
};

type QueryResult<T> = {
    data: T;
    error: string | null;
    isLoading: boolean;
    refresh: () => Promise<void>;
};

const resourceCache = new Map<string, unknown>();

export function invalidateResource(key: string) {
    resourceCache.delete(key);
}

export function invalidateResourcePrefix(prefix: string) {
    for (const key of Array.from(resourceCache.keys())) {
        if (key.startsWith(prefix)) {
            resourceCache.delete(key);
        }
    }
}

export function usePollingResource<T>(
    key: string,
    fetcher: () => Promise<T>,
    options: QueryOptions<T>,
): QueryResult<T> {
    const { enabled = true, initialData, pollMs } = options;
    const fetcherRef = useRef(fetcher);
    fetcherRef.current = fetcher;

    const [data, setData] = useState<T>(() => {
        if (resourceCache.has(key)) {
            return resourceCache.get(key) as T;
        }
        return initialData;
    });
    const [error, setError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(enabled && !resourceCache.has(key));

    useEffect(() => {
        if (!enabled) {
            setData(initialData);
            setError(null);
            setIsLoading(false);
            return;
        }

        let cancelled = false;

        const run = async (showLoading: boolean) => {
            if (showLoading && !resourceCache.has(key)) {
                setIsLoading(true);
            }

            try {
                const result = await fetcherRef.current();
                if (cancelled) {
                    return;
                }
                resourceCache.set(key, result);
                startTransition(() => {
                    setData(result);
                });
                setError(null);
            } catch (requestError) {
                if (cancelled) {
                    return;
                }
                setError(
                    requestError instanceof Error
                        ? requestError.message
                        : "Unknown request error",
                );
            } finally {
                if (!cancelled) {
                    setIsLoading(false);
                }
            }
        };

        const cached = resourceCache.get(key);
        if (cached !== undefined) {
            setData(cached as T);
            setIsLoading(false);
        } else {
            void run(true);
        }

        if (!pollMs) {
            return () => {
                cancelled = true;
            };
        }

        const intervalId = window.setInterval(() => {
            void run(false);
        }, pollMs);

        return () => {
            cancelled = true;
            window.clearInterval(intervalId);
        };
    }, [enabled, initialData, key, pollMs]);

    const refresh = async () => {
        if (!enabled) {
            return;
        }

        setIsLoading(true);
        invalidateResource(key);
        try {
            const result = await fetcherRef.current();
            resourceCache.set(key, result);
            startTransition(() => {
                setData(result);
            });
            setError(null);
        } catch (requestError) {
            setError(
                requestError instanceof Error
                    ? requestError.message
                    : "Unknown request error",
            );
        } finally {
            setIsLoading(false);
        }
    };

    return {
        data,
        error,
        isLoading,
        refresh,
    };
}
