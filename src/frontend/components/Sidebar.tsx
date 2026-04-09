import { cn } from "@/lib/utils";
import { SessionSummary } from "@/lib/types";
import { MessageSquarePlus } from "lucide-react";

import { ConnectionIndicator } from "./sidebar/ConnectionIndicator";
import { SessionList } from "./sidebar/SessionList";

interface SidebarProps {
    sessions: SessionSummary[];
    selectedSessionId: string | null;
    onSelectSession: (id: string) => void;
    onResumeSession: (session: SessionSummary) => void | Promise<void>;
    onDeleteSession: (id: string) => void;
    onNewSession: () => void;
    systemStatus: 'connected' | 'disconnected' | 'unknown';
    className?: string;
}

export function Sidebar({
    sessions,
    selectedSessionId,
    onSelectSession,
    onResumeSession,
    onDeleteSession,
    onNewSession,
    systemStatus,
    className
}: SidebarProps) {
    return (
        <div className={cn("flex flex-col border-r bg-muted/30 w-64 h-full", className)}>
            <div className="p-4 border-b">
                <button
                    onClick={onNewSession}
                    className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
                >
                    <MessageSquarePlus className="h-4 w-4" />
                    New Exploration
                </button>
            </div>

            <div className="flex-1 overflow-auto py-2">
                <SessionList
                    sessions={sessions}
                    selectedSessionId={selectedSessionId}
                    onSelectSession={onSelectSession}
                    onResumeSession={onResumeSession}
                    onDeleteSession={onDeleteSession}
                />
            </div>

            <div className="p-4 border-t bg-background/50 backdrop-blur">
                <ConnectionIndicator systemStatus={systemStatus} />
            </div>
        </div>
    );
}
