import { Activity, AlertTriangle } from "lucide-react";

import { cn } from "@/lib/utils";

export type ReportTab = "report" | "pruned" | "usage";

interface ReportTabsProps {
    activeTab: ReportTab;
    onChange: (tab: ReportTab) => void;
}

export function ReportTabs({ activeTab, onChange }: ReportTabsProps) {
    return (
        <div className="px-6 border-b flex gap-6 text-sm font-medium">
            <button
                onClick={() => onChange("report")}
                className={cn(
                    "py-3 border-b-2 transition-all",
                    activeTab === "report"
                        ? "border-primary text-primary"
                        : "border-transparent text-muted-foreground hover:text-foreground",
                )}
            >
                Full Report
            </button>
            <button
                onClick={() => onChange("pruned")}
                className={cn(
                    "py-3 border-b-2 transition-all flex items-center gap-2",
                    activeTab === "pruned"
                        ? "border-primary text-primary"
                        : "border-transparent text-muted-foreground hover:text-foreground",
                )}
            >
                <AlertTriangle className="w-3 h-3" />
                Pruned Paths
            </button>
            <button
                onClick={() => onChange("usage")}
                className={cn(
                    "py-3 border-b-2 transition-all flex items-center gap-2",
                    activeTab === "usage"
                        ? "border-primary text-primary"
                        : "border-transparent text-muted-foreground hover:text-foreground",
                )}
            >
                <Activity className="w-3 h-3" />
                LLM Usage
            </button>
        </div>
    );
}

