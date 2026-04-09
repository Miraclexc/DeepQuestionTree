"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import {
    fetchSession,
    fetchSessions,
    fetchTree,
    getSystemStatus,
} from "@/lib/api";
import {
    SessionDetails,
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
    session_revision: 0,
    nodes: [],
    edges: [],
    statistics: {},
};

const EMPTY_SESSION_DETAILS: SessionDetails | null = null;

const EMPTY_STATUS: SystemStatus = {
    single_session_mode: true,
    mcts_running: false,
    has_active_session: false,
    active_session_id: null,
    environment: "development",
    session_status: null,
    session_revision: null,
    session_error_message: null,
    total_simulations: null,
    tree_depth: null,
    total_nodes: null,
};

export type ConnectionState = "connected" | "disconnected" | "unknown";

export function useDeepQuestionTree() {
    const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
    const [hasLoadedStatus, setHasLoadedStatus] = useState(false);
    const pendingTreeRefreshRevisionRef = useRef<string | null>(null);

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
        },
    );
    const sessionDetailsQuery = usePollingResource<SessionDetails | null>(
        currentSessionId ? `session:${currentSessionId}` : "session:none",
        async () => fetchSession(currentSessionId as string),
        {
            enabled: Boolean(currentSessionId),
            initialData: EMPTY_SESSION_DETAILS,
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
        onResetWorkspacePanels: () => {
            reportState.closeReport();
            nodeDetails.closeNode();
            nodeDetails.clearNode();
        },
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

    useEffect(() => {
        if (!currentSessionId) {
            pendingTreeRefreshRevisionRef.current = null;
        }
    }, [currentSessionId]);

    useEffect(() => {
        if (!currentSessionId) {
            return;
        }

        if (statusQuery.isLoading || statusQuery.error) {
            return;
        }

        if (statusQuery.data.active_session_id !== currentSessionId) {
            return;
        }

        const statusRevision = statusQuery.data.session_revision;
        const treeRevision =
            treeQuery.data?.session_id === currentSessionId
                ? treeQuery.data.session_revision
                : null;
        const refreshKey =
            typeof statusRevision === "number"
                ? `${currentSessionId}:${statusRevision}`
                : null;

        if (
            typeof statusRevision !== "number"
            || typeof treeRevision !== "number"
            || statusRevision === treeRevision
        ) {
            if (
                typeof statusRevision === "number"
                && typeof treeRevision === "number"
                && statusRevision === treeRevision
            ) {
                pendingTreeRefreshRevisionRef.current = null;
            }
            return;
        }

        if (refreshKey && pendingTreeRefreshRevisionRef.current === refreshKey) {
            return;
        }

        pendingTreeRefreshRevisionRef.current = refreshKey;
        void treeQuery.refresh();
    }, [
        currentSessionId,
        statusQuery.data.active_session_id,
        statusQuery.data.session_revision,
        statusQuery.error,
        statusQuery.isLoading,
        treeQuery.data,
        treeQuery.refresh,
    ]);

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
    const currentSessionDetails = sessionDetailsQuery.data;
    const isLegacyTokenAccounting =
        currentSessionDetails?.is_legacy_token_accounting ??
        currentSession?.is_legacy_token_accounting ??
        false;
    const canGenerateReport =
        currentSessionId !== null &&
        (!isLegacyTokenAccounting ||
            Boolean(currentSessionDetails?.report_available));
    const generateReportDisabledReason =
        isLegacyTokenAccounting && !currentSessionDetails?.report_available
            ? "Legacy sessions without cached reports are read-only."
            : undefined;

    return {
        currentSession,
        currentSessionDetails,
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
        onResumeSession: sessionCommands.resumeSession,
        onStartSession: sessionCommands.startSession,
        onStopAndReport: sessionCommands.stopAndReport,
        canGenerateReport,
        generateReportDisabledReason,
    };
}
