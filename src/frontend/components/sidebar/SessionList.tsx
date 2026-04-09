import { SessionSummary } from "@/lib/types";

import { SessionListItem } from "./SessionListItem";

interface SessionListProps {
    sessions: SessionSummary[];
    selectedSessionId: string | null;
    onSelectSession: (id: string) => void;
    onResumeSession: (session: SessionSummary) => void | Promise<void>;
    onDeleteSession: (id: string) => void;
}

export function SessionList({
    sessions,
    selectedSessionId,
    onSelectSession,
    onResumeSession,
    onDeleteSession,
}: SessionListProps) {
    return (
        <>
            <div className="px-4 pb-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                History
            </div>
            <div className="space-y-1 px-2">
                {sessions.map((session) => (
                    <SessionListItem
                        key={session.session_id}
                        session={session}
                        selected={selectedSessionId === session.session_id}
                        onSelect={onSelectSession}
                        onResume={(sessionId) => {
                            const resumableSession = sessions.find(
                                (item) => item.session_id === sessionId,
                            );
                            if (resumableSession) {
                                return onResumeSession(resumableSession);
                            }
                        }}
                        onDelete={onDeleteSession}
                    />
                ))}

                {sessions.length === 0 && (
                    <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                        No history yet
                    </div>
                )}
            </div>
        </>
    );
}
