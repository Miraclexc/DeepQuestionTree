"use client";

import { useState } from "react";

import { deleteSession, startSession, stopSession } from "@/lib/api";
import { SessionSummary } from "@/lib/types";

import { invalidateResource, invalidateResourcePrefix } from "./usePollingResource";

type SessionCommandOptions = {
    currentSessionId: string | null;
    refreshSessions: () => Promise<void>;
    refreshStatus: () => Promise<void>;
    onSelectSession: (sessionId: string | null) => void;
    onOpenReport: () => void;
    onResetWorkspacePanels: () => void;
    onResetCurrentSession: () => void;
};

type ResumableSession = Pick<
    SessionSummary,
    "session_id" | "global_goal" | "is_legacy_token_accounting"
>;

export function useSessionCommands(options: SessionCommandOptions) {
    const {
        currentSessionId,
        refreshSessions,
        refreshStatus,
        onSelectSession,
        onOpenReport,
        onResetWorkspacePanels,
        onResetCurrentSession,
    } = options;

    const [isNewSessionDialogOpen, setIsNewSessionDialogOpen] = useState(false);
    const [draftGoal, setDraftGoal] = useState("");
    const [isStarting, setIsStarting] = useState(false);

    const invalidateSessionViews = () => {
        invalidateResource("system-status");
        invalidateResource("sessions");
        invalidateResourcePrefix("session:");
        invalidateResourcePrefix("tree:");
        invalidateResourcePrefix("report:");
    };

    const handleStartSession = async () => {
        if (!draftGoal.trim()) {
            return;
        }

        setIsStarting(true);
        try {
            const response = await startSession(draftGoal);
            invalidateSessionViews();
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

    const handleResumeSession = async (session: ResumableSession) => {
        if (session.is_legacy_token_accounting) {
            return;
        }
        const response = await startSession(
            session.global_goal,
            false,
            session.session_id,
        );
        invalidateSessionViews();
        await Promise.all([refreshSessions(), refreshStatus()]);
        onResetWorkspacePanels();
        onSelectSession(response.session_id);
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
        resumeSession: handleResumeSession,
        stopAndReport: handleStopAndReport,
    };
}
