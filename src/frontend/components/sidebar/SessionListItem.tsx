import { Clock, Trash2 } from "lucide-react";

import { SessionSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

interface SessionListItemProps {
    session: SessionSummary;
    selected: boolean;
    onSelect: (id: string) => void;
    onDelete: (id: string) => void;
}

export function SessionListItem({
    session,
    selected,
    onSelect,
    onDelete,
}: SessionListItemProps) {
    return (
        <div
            className={cn(
                "group flex items-center rounded-lg pr-2 transition-colors hover:bg-accent",
                selected
                    ? "bg-accent text-accent-foreground font-medium"
                    : "text-muted-foreground",
            )}
        >
            <button
                onClick={() => onSelect(session.session_id)}
                className="flex-1 flex items-start gap-2 px-3 py-2 text-sm text-left truncate"
            >
                <div className="mt-1 shrink-0">
                    {session.status === "running" ? (
                        <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" title="Running" />
                    ) : session.status === "completed" ? (
                        <div className="w-2 h-2 rounded-full bg-green-500" title="Completed" />
                    ) : (
                        <Clock className="h-4 w-4 opacity-50" />
                    )}
                </div>
                <div className="flex-1 truncate">
                    <div className="truncate font-medium">
                        {session.global_goal || "Untitled Exploration"}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground/70">
                        <span>{new Date(session.updated_at).toLocaleDateString()}</span>
                        {session.status && (
                            <span className="capitalize opacity-75">• {session.status}</span>
                        )}
                    </div>
                </div>
            </button>
            <button
                onClick={(event) => {
                    event.stopPropagation();
                    if (confirm("Are you sure you want to delete this session?")) {
                        onDelete(session.session_id);
                    }
                }}
                className="opacity-0 group-hover:opacity-100 p-1.5 hover:bg-destructive/10 hover:text-destructive rounded-md transition-all"
                title="Delete Session"
            >
                <Trash2 className="h-4 w-4" />
            </button>
        </div>
    );
}

