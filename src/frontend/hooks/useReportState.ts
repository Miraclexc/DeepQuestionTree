"use client";

import { useEffect, useRef, useState } from "react";

import { fetchReport } from "@/lib/api";
import { ReportData } from "@/lib/types";

import { invalidateResource, usePollingResource } from "./usePollingResource";

const EMPTY_REPORT: ReportData = {
    session_id: "",
    goal: "",
    executive_summary: "",
    full_report: "",
    key_insights: [],
    pruned_insights: [],
    statistics: {
        total_nodes: 0,
        total_simulations: 0,
        tree_depth: 0,
        total_facts: 0,
        active_nodes: 0,
        pruned_nodes: 0,
    },
    llm_stats: {
        total_calls: 0,
        total_tokens: 0,
        usage_by_model: {},
    },
    suggestions: [],
    generated_at: "",
    error_message: null,
};

export function useReportState(currentSessionId: string | null) {
    const [showReport, setShowReport] = useState(false);
    const previousSessionIdRef = useRef<string | null>(currentSessionId);
    const reportQuery = usePollingResource<ReportData>(
        currentSessionId ? `report:${currentSessionId}` : "report:none",
        () => fetchReport(currentSessionId as string),
        {
            enabled: Boolean(currentSessionId) && showReport,
            initialData: EMPTY_REPORT,
        },
    );

    const openReport = () => {
        if (!currentSessionId) {
            return;
        }

        invalidateResource(`report:${currentSessionId}`);
        setShowReport(true);
    };

    useEffect(() => {
        const previousSessionId = previousSessionIdRef.current;

        if (previousSessionId !== currentSessionId) {
            setShowReport(false);
        }

        previousSessionIdRef.current = currentSessionId;
    }, [currentSessionId]);

    return {
        showReport,
        reportData: reportQuery.data,
        isGeneratingReport: reportQuery.isLoading,
        openReport,
        closeReport: () => setShowReport(false),
    };
}
