import { Activity, Lightbulb } from "lucide-react";

import { ReportData } from "@/lib/types";

interface ReportSidebarProps {
    report: ReportData;
}

export function ReportSidebar({ report }: ReportSidebarProps) {
    return (
        <div className="w-full md:w-64 bg-muted/10 border-r p-6 space-y-6 overflow-y-auto">
            <div className="space-y-2">
                <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Session Stats
                </h3>
                <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 bg-card rounded border text-center">
                        <div className="text-xl font-bold text-primary">
                            {report.statistics.total_facts}
                        </div>
                        <div className="text-[10px] text-muted-foreground">Facts Found</div>
                    </div>
                    <div className="p-3 bg-card rounded border text-center">
                        <div className="text-xl font-bold text-primary">
                            {report.statistics.tree_depth}
                        </div>
                        <div className="text-[10px] text-muted-foreground">Max Depth</div>
                    </div>
                </div>
            </div>

            <div className="space-y-4">
                <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
                    <Lightbulb className="h-3 w-3" />
                    Key Insights
                </h3>
                <ul className="space-y-3">
                    {report.key_insights.map((insight, index) => (
                        <li
                            key={`${insight}-${index}`}
                            className="text-xs text-foreground bg-primary/5 p-2 rounded border border-primary/10 leading-relaxed"
                        >
                            {insight}
                        </li>
                    ))}
                </ul>
            </div>

            {report.suggestions.length > 0 && (
                <div className="space-y-4">
                    <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
                        <Activity className="h-3 w-3" />
                        Next Steps
                    </h3>
                    <ul className="space-y-2">
                        {report.suggestions.map((suggestion, index) => (
                            <li
                                key={`${suggestion}-${index}`}
                                className="text-xs text-muted-foreground pl-2 border-l-2 border-primary/30"
                            >
                                {suggestion}
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
}

