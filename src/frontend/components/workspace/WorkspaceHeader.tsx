import { FileText, Square } from "lucide-react";

import { SessionSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

interface WorkspaceHeaderProps {
    currentSession: SessionSummary | null;
    currentSessionId: string | null;
    canGenerateReport: boolean;
    generateReportDisabledReason?: string;
    onGenerateReport: () => void;
    onStopAndReport: () => Promise<void>;
}

export function WorkspaceHeader({
    currentSession,
    currentSessionId,
    canGenerateReport,
    generateReportDisabledReason,
    onGenerateReport,
    onStopAndReport,
}: WorkspaceHeaderProps) {
    const isRunning = currentSession?.status === "running";

    return (
        <div className="h-14 border-b bg-background/50 backdrop-blur flex items-center justify-between px-4">
            <div className="font-semibold text-lg flex items-center gap-2">
                {currentSessionId
                    ? currentSession?.global_goal || "Unknown Session"
                    : "Deep Question Tree"}
            </div>

            {currentSession && (
                <div className="flex items-center gap-3">
                    <div
                        className={cn(
                            "px-2 py-0.5 rounded-full text-xs font-medium border flex items-center gap-1.5 transition-colors",
                            "bg-muted/40 text-muted-foreground border-transparent",
                        )}
                    >
                        <div
                            className={cn(
                                "w-1.5 h-1.5 rounded-full",
                                isRunning
                                    ? "bg-blue-400/70 animate-pulse"
                                    : "bg-gray-400/70",
                            )}
                        />
                        {isRunning ? "Running Explorations" : "Analysis Completed"}
                    </div>
                </div>
            )}

            {currentSessionId && (
                <div className="flex items-center gap-2">
                    <button
                        onClick={async () => {
                            if (
                                confirm(
                                    "Are you sure you want to stop the exploration and generate the report?",
                                )
                            ) {
                                await onStopAndReport();
                            }
                        }}
                        disabled={!isRunning}
                        className="px-3 py-1.5 text-xs font-medium bg-destructive/10 text-destructive hover:bg-destructive/20 disabled:opacity-50 disabled:cursor-not-allowed rounded-md flex items-center gap-1.5 transition-colors border border-destructive/20"
                    >
                        <Square className="h-3.5 w-3.5 fill-current" />
                        Stop & Report
                    </button>

                    <button
                        onClick={onGenerateReport}
                        disabled={!canGenerateReport}
                        title={generateReportDisabledReason}
                        className="px-3 py-1.5 text-xs font-medium bg-primary/10 text-primary hover:bg-primary/20 rounded-md flex items-center gap-1.5 transition-colors"
                    >
                        <FileText className="h-3.5 w-3.5" />
                        Generate Report
                    </button>

                    <div className="bg-muted px-2 py-1 rounded text-[10px] text-muted-foreground font-mono">
                        ID: {currentSessionId.slice(0, 8)}
                    </div>
                </div>
            )}
        </div>
    );
}
