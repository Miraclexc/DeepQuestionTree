"use client";

import { useEffect, useMemo, useState } from "react";

import {
    fetchSessions,
    fetchTree,
    getSystemStatus,
} from "@/lib/api";
import {
    SessionSummary,
    SystemStatus,
    TreeResponse,
} from "@/lib/types";

import {
    usePollingResource,
} from "./usePollingResource";
import { useGlobalApiError } from "./useGlobalApiError";
import { useNodeDetails } from "./useNodeDetails";
import { useReportState } from "./useReportState";
import { useSessionCommands } from "./useSessionCommands";

const EMPTY_TREE: TreeResponse = {
    session_id: "",
    nodes: [],
    edges: [],
    statistics: {},
};

const EMPTY_STATUS: SystemStatus = {
    single_session_mode: true,
    mcts_running: false,
    has_active_session: false,
    active_session_id: null,
    environment: "development",
    session_status: null,
    total_simulations: null,
    tree_depth: null,
    total_nodes: null,
};

export type ConnectionState = "connected" | "disconnected" | "unknown";

export function useDeepQuestionTree() {
    const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
    const [hasLoadedStatus, setHasLoadedStatus] = useState(false);

    const sessionsQuery = usePollingResource<SessionSummary[]>(
        "sessions",
        fetchSessions,
        {
            initialData: [],
            pollMs: 10000,
        },
    );
    const statusQuery = usePollingResource<SystemStatus>(
        "system-status",
        getSystemStatus,
        {
            initialData: EMPTY_STATUS,
            pollMs: 5000,
        },
    );
    const treeQuery = usePollingResource<TreeResponse>(
        currentSessionId ? `tree:${currentSessionId}` : "tree:none",
        () => fetchTree(currentSessionId as string),
        {
            enabled: Boolean(currentSessionId),
            initialData: EMPTY_TREE,
            pollMs: 2000,
        },
    );
    const { error, clearError } = useGlobalApiError();
    const nodeDetails = useNodeDetails(currentSessionId);
    const reportState = useReportState(currentSessionId);
    const sessionCommands = useSessionCommands({
        currentSessionId,
        refreshSessions: sessionsQuery.refresh,
        refreshStatus: statusQuery.refresh,
        onSelectSession: setCurrentSessionId,
        onOpenReport: reportState.openReport,
        onResetCurrentSession: () => {
            setCurrentSessionId(null);
            reportState.closeReport();
            nodeDetails.clearNode();
        },
    });

    useEffect(() => {
        if (!statusQuery.isLoading && !statusQuery.error) {
            setHasLoadedStatus(true);
        }
    }, [statusQuery.error, statusQuery.isLoading]);

    const currentSession = useMemo(
        () =>
            sessionsQuery.data.find(
                (session) => session.session_id === currentSessionId,
            ) ?? null,
        [currentSessionId, sessionsQuery.data],
    );

    const systemStatus: ConnectionState = statusQuery.error
        ? "disconnected"
        : hasLoadedStatus
          ? "connected"
          : "unknown";

    return {
        currentSession,
        currentSessionId,
        draftGoal: sessionCommands.draftGoal,
        error,
        isGeneratingReport: reportState.isGeneratingReport,
        isNewSessionDialogOpen: sessionCommands.isNewSessionDialogOpen,
        isLoadingTree: treeQuery.isLoading,
        isNodePanelOpen: nodeDetails.isNodePanelOpen,
        isStarting: sessionCommands.isStarting,
        reportData: reportState.reportData,
        selectedNode: nodeDetails.selectedNode,
        sessions: sessionsQuery.data,
        showReport: reportState.showReport,
        systemStatus,
        treeData: treeQuery.data,
        onChangeNewSessionGoal: sessionCommands.changeNewSessionGoal,
        onClearError: clearError,
        onCloseNodePanel: nodeDetails.closeNode,
        onCloseNewSessionDialog: sessionCommands.closeNewSessionDialog,
        onCloseReport: reportState.closeReport,
        onDeleteSession: sessionCommands.deleteSession,
        onGenerateReport: reportState.openReport,
        onOpenNewSessionDialog: sessionCommands.openNewSessionDialog,
        onNodeClick: nodeDetails.openNode,
        onSelectSession: setCurrentSessionId,
        onStartSession: sessionCommands.startSession,
        onStopAndReport: sessionCommands.stopAndReport,
    };
}
