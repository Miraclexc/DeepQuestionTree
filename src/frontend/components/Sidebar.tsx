import { cn } from "@/lib/utils";
import { MessageSquarePlus, Clock, ChevronRight, Trash2 } from "lucide-react";

interface SidebarProps {
    sessions: any[];
    selectedSessionId: string | null;
    onSelectSession: (id: string) => void;
    onDeleteSession: (id: string) => void;
    onNewSession: () => void;
    systemStatus: 'connected' | 'disconnected' | 'unknown';
    className?: string;
}

export function Sidebar({
    sessions,
    selectedSessionId,
    onSelectSession,
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
                <div className="px-4 pb-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    History
                </div>
                <div className="space-y-1 px-2">
                    {sessions.map((session) => (
                        <div
                            key={session.session_id}
                            className={cn(
                                "group flex items-center rounded-lg pr-2 transition-colors hover:bg-accent",
                                selectedSessionId === session.session_id
                                    ? "bg-accent text-accent-foreground font-medium"
                                    : "text-muted-foreground"
                            )}
                        >
                            <button
                                onClick={() => onSelectSession(session.session_id)}
                                className="flex-1 flex items-start gap-2 px-3 py-2 text-sm text-left truncate"
                            >
                                <div className="mt-1 shrink-0">
                                    {session.status === 'running' ? (
                                        <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" title="Running" />
                                    ) : session.status === 'completed' ? (
                                        <div className="w-2 h-2 rounded-full bg-green-500" title="Completed" />
                                    ) : (
                                        <Clock className="h-4 w-4 opacity-50" />
                                    )}
                                </div>
                                <div className="flex-1 truncate">
                                    <div className="truncate font-medium">{session.global_goal || "Untitled Exploration"}</div>
                                    <div className="flex items-center gap-2 text-xs text-muted-foreground/70">
                                        <span>{new Date(session.updated_at).toLocaleDateString()}</span>
                                        {session.status && (
                                            <span className="capitalize opacity-75">• {session.status}</span>
                                        )}
                                    </div>
                                </div>
                            </button>
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    if (confirm("Are you sure you want to delete this session?")) {
                                        onDeleteSession(session.session_id);
                                    }
                                }}
                                className="opacity-0 group-hover:opacity-100 p-1.5 hover:bg-destructive/10 hover:text-destructive rounded-md transition-all"
                                title="Delete Session"
                            >
                                <Trash2 className="h-4 w-4" />
                            </button>
                        </div>
                    ))}

                    {sessions.length === 0 && (
                        <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                            No history yet
                        </div>
                    )}
                </div>
            </div>

            <div className="p-4 border-t bg-background/50 backdrop-blur">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <div className={cn(
                        "w-2 h-2 rounded-full animate-pulse",
                        systemStatus === 'connected' ? "bg-green-500" :
                            systemStatus === 'disconnected' ? "bg-red-500" : "bg-gray-400"
                    )} />
                    {systemStatus === 'connected' ? "System Ready" :
                        systemStatus === 'disconnected' ? "Disconnected" : "Checking..."}
                </div>
            </div>
        </div>
    );
}
