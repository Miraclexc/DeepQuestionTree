"use client";

import { useState } from "react";

import { deleteSession, startSession, stopSession } from "@/lib/api";

import { invalidateResource, invalidateResourcePrefix } from "./usePollingResource";

type SessionCommandOptions = {
    currentSessionId: string | null;
    refreshSessions: () => Promise<void>;
    refreshStatus: () => Promise<void>;
    onSelectSession: (sessionId: string | null) => void;
    onOpenReport: () => void;
    onResetCurrentSession: () => void;
};

export function useSessionCommands(options: SessionCommandOptions) {
    const {
        currentSessionId,
        refreshSessions,
        refreshStatus,
        onSelectSession,
        onOpenReport,
        onResetCurrentSession,
    } = options;

    const [isNewSessionDialogOpen, setIsNewSessionDialogOpen] = useState(false);
    const [draftGoal, setDraftGoal] = useState("");
    const [isStarting, setIsStarting] = useState(false);

    const handleStartSession = async () => {
        if (!draftGoal.trim()) {
            return;
        }

        setIsStarting(true);
        try {
            const response = await startSession(draftGoal);
            invalidateResource("system-status");
            invalidateResource("sessions");
            invalidateResourcePrefix("tree:");
            invalidateResourcePrefix("report:");
            await Promise.all([refreshSessions(), refreshStatus()]);
            onSelectSession(response.session_id);
            setIsNewSessionDialogOpen(false);
            setDraftGoal("");
        } finally {
            setIsStarting(false);
        }
    };

    const handleDeleteSession = async (sessionId: string) => {
        await deleteSession(sessionId);
        invalidateResource("sessions");
        invalidateResourcePrefix(`tree:${sessionId}`);
        invalidateResourcePrefix(`report:${sessionId}`);
        await refreshSessions();
        if (currentSessionId === sessionId) {
            onResetCurrentSession();
        }
    };

    const handleStopAndReport = async () => {
        await stopSession();
        invalidateResource("system-status");
        invalidateResource("sessions");
        await Promise.all([refreshStatus(), refreshSessions()]);
        onOpenReport();
    };

    return {
        isNewSessionDialogOpen,
        draftGoal,
        isStarting,
        openNewSessionDialog: () => setIsNewSessionDialogOpen(true),
        closeNewSessionDialog: () => setIsNewSessionDialogOpen(false),
        changeNewSessionGoal: setDraftGoal,
        startSession: handleStartSession,
        deleteSession: handleDeleteSession,
        stopAndReport: handleStopAndReport,
    };
}
