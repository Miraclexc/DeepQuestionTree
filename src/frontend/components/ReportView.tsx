"use client";

import React from 'react';
import { MarkdownRenderer } from "./MarkdownRenderer";
import { X, FileText, Download, Lightbulb, Activity, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
// import { Button } from "@/components/ui/button"; // Module not found

interface ReportViewProps {
    report: any | null;
    isLoading: boolean;
    onClose: () => void;
}

export function ReportView({ report, isLoading, onClose }: ReportViewProps) {
    const [activeTab, setActiveTab] = React.useState<"report" | "pruned" | "usage">("report");

    const handleExportPDF = async () => {
        if (!report) return;
        try {
            // Dynamically import html2pdf to avoid server-side issues
            // @ts-ignore
            const html2pdf = (await import('html2pdf.js')).default;
            const element = document.getElementById('report-export-container');
            const opt = {
                margin: 0.5,
                filename: `report-${report.session_id}.pdf`,
                image: { type: 'jpeg', quality: 0.98 },
                html2canvas: { scale: 2, useCORS: true },
                jsPDF: { unit: 'in', format: 'letter', orientation: 'portrait' }
            };
            html2pdf().set(opt).from(element).save();
        } catch (e) {
            console.error("PDF Export failed", e);
            alert("PDF Export failed. Please ensure 'html2pdf.js' is installed.");
        }
    };

    if (!report && !isLoading) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-in fade-in duration-200">
            <div className="flex flex-col w-full max-w-4xl max-h-[90vh] bg-background rounded-lg shadow-2xl overflow-hidden border">
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b bg-muted/40">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-primary/10 rounded-lg">
                            <FileText className="h-5 w-5 text-primary" />
                        </div>
                        <div>
                            <h2 className="text-lg font-semibold text-foreground">Exploration Report</h2>
                            <p className="text-xs text-muted-foreground">{report?.goal || "Generating insights..."}</p>
                        </div>
                    </div>
                </div>

                {/* Tab Navigation */}
                <div className="px-6 border-b flex gap-6 text-sm font-medium">
                    <button
                        onClick={() => setActiveTab("report")}
                        className={cn("py-3 border-b-2 transition-all", activeTab === "report" ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground")}
                    >
                        Full Report
                    </button>
                    <button
                        onClick={() => setActiveTab("pruned")}
                        className={cn("py-3 border-b-2 transition-all flex items-center gap-2", activeTab === "pruned" ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground")}
                    >
                        <AlertTriangle className="w-3 h-3" />
                        Pruned Paths
                    </button>
                    <button
                        onClick={() => setActiveTab("usage")}
                        className={cn("py-3 border-b-2 transition-all flex items-center gap-2", activeTab === "usage" ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground")}
                    >
                        <Activity className="w-3 h-3" />
                        LLM Usage
                    </button>
                    <div className="flex-1"></div>
                    <div className="flex items-center gap-2 py-2">
                        {report && (
                            <>
                                <button
                                    onClick={handleExportPDF}
                                    className="p-2 rounded-md hover:bg-muted transition-colors text-muted-foreground"
                                    title="Export PDF"
                                >
                                    <FileText className="h-4 w-4" />
                                </button>
                                <button
                                    onClick={() => {
                                        const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
                                        const url = URL.createObjectURL(blob);
                                        const a = document.createElement("a");
                                        a.href = url;
                                        a.download = `report-${report.session_id}.json`;
                                        document.body.appendChild(a);
                                        a.click();
                                        document.body.removeChild(a);
                                        URL.revokeObjectURL(url);
                                    }}
                                    className="p-2 rounded-md hover:bg-muted transition-colors text-muted-foreground"
                                    title="Download JSON"
                                >
                                    <Download className="h-4 w-4" />
                                </button>
                            </>
                        )}
                        <button
                            onClick={onClose}
                            className="p-2 rounded-md hover:bg-destructive/10 hover:text-destructive transition-colors text-muted-foreground"
                        >
                            <X className="h-5 w-5" />
                        </button>
                    </div>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-0">
                    {isLoading ? (
                        <div className="flex flex-col items-center justify-center h-96 space-y-4">
                            <div className="relative">
                                <div className="h-12 w-12 rounded-full border-4 border-primary/30 border-t-primary animate-spin"></div>
                                <div className="absolute inset-0 flex items-center justify-center">
                                    <Activity className="h-5 w-5 text-primary animate-pulse" />
                                </div>
                            </div>
                            <p className="text-sm text-muted-foreground animate-pulse">Compiling insights and analyzing paths...</p>
                        </div>
                    ) : (
                        <div className="flex flex-col md:flex-row h-full">
                            {/* Left Sidebar / Quick Stats */}
                            <div className="w-full md:w-64 bg-muted/10 border-r p-6 space-y-6 overflow-y-auto">
                                <div className="space-y-2">
                                    <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Session Stats</h3>
                                    <div className="grid grid-cols-2 gap-3">
                                        <div className="p-3 bg-card rounded border text-center">
                                            <div className="text-xl font-bold text-primary">{report.statistics.total_facts}</div>
                                            <div className="text-[10px] text-muted-foreground">Facts Found</div>
                                        </div>
                                        <div className="p-3 bg-card rounded border text-center">
                                            <div className="text-xl font-bold text-primary">{report.statistics.tree_depth}</div>
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
                                        {report.key_insights.map((insight: string, idx: number) => (
                                            <li key={idx} className="text-xs text-foreground bg-primary/5 p-2 rounded border border-primary/10 leading-relaxed">
                                                {insight}
                                            </li>
                                        ))}
                                    </ul>
                                </div>

                                {report.suggestions && (
                                    <div className="space-y-4">
                                        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
                                            <Activity className="h-3 w-3" />
                                            Next Steps
                                        </h3>
                                        <ul className="space-y-2">
                                            {report.suggestions.map((s: string, idx: number) => (
                                                <li key={idx} className="text-xs text-muted-foreground pl-2 border-l-2 border-primary/30">
                                                    {s}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                            </div>

                            {/* Main Report Area */}
                            <div className="flex-1 p-8 overflow-y-auto bg-card h-full" id="report-export-container">
                                {activeTab === "report" && (
                                    <div className="max-w-3xl mx-auto">
                                        <div className="mb-8 p-6 bg-gradient-to-br from-primary/5 via-transparent to-transparent rounded-xl border border-primary/10">
                                            <h3 className="text-xl font-bold mb-4 flex items-center gap-2 text-primary">
                                                Executive Summary
                                            </h3>
                                            <div className="text-sm leading-relaxed text-muted-foreground">
                                                <MarkdownRenderer content={report.executive_summary} />
                                            </div>
                                        </div>

                                        <hr className="my-8 border-muted" />

                                        <h3 className="text-2xl font-bold mb-6">Detailed Report</h3>
                                        <div className="markdown-content">
                                            <MarkdownRenderer content={report.full_report || ""} />
                                        </div>
                                    </div>
                                )}

                                {activeTab === "pruned" && (
                                    <div className="max-w-3xl mx-auto space-y-6">
                                        <div className="flex items-center gap-3 mb-6">
                                            <div className="p-3 bg-orange-100 dark:bg-orange-950/30 rounded-full">
                                                <AlertTriangle className="w-6 h-6 text-orange-600 dark:text-orange-500" />
                                            </div>
                                            <div>
                                                <h2 className="text-2xl font-bold">Pruned Paths & Dead Ends</h2>
                                                <p className="text-sm text-muted-foreground">
                                                    Explorations stopped early. Lessons on what NOT to do or unfruitful directions.
                                                </p>
                                            </div>
                                        </div>

                                        {report.pruned_insights && report.pruned_insights.length > 0 ? (
                                            <div className="grid gap-4">
                                                {report.pruned_insights.map((insight: string, idx: number) => (
                                                    <div key={idx} className="p-5 border rounded-lg bg-card hover:bg-muted/5 transition-colors shadow-sm">
                                                        <div className="flex gap-3">
                                                            <div className="mt-1 shrink-0">
                                                                <div className="w-6 h-6 rounded-full bg-muted flex items-center justify-center text-xs font-mono text-muted-foreground">
                                                                    {idx + 1}
                                                                </div>
                                                            </div>
                                                            <p className="text-sm leading-relaxed text-foreground/90">
                                                                {insight}
                                                            </p>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        ) : (
                                            <div className="text-center py-12 border-2 border-dashed rounded-xl ">
                                                <p className="text-muted-foreground">No pruned paths recorded in this session yet.</p>
                                            </div>
                                        )}
                                    </div>
                                )}

                                {activeTab === "usage" && report.llm_stats && (
                                    <div className="max-w-3xl mx-auto space-y-8">
                                        <div>
                                            <h2 className="text-2xl font-bold mb-2">LLM Utilization</h2>
                                            <p className="text-sm text-muted-foreground">Resource consumption breakdown by model.</p>
                                        </div>

                                        <div className="grid grid-cols-2 gap-4">
                                            <div className="p-6 border rounded-xl bg-card">
                                                <div className="text-sm text-muted-foreground mb-1">Total API Calls</div>
                                                <div className="text-3xl font-bold text-primary">{report.llm_stats.total_calls}</div>
                                            </div>
                                            <div className="p-6 border rounded-xl bg-card">
                                                <div className="text-sm text-muted-foreground mb-1">Total Tokens Used</div>
                                                <div className="text-3xl font-bold text-primary">{report.llm_stats.total_tokens.toLocaleString()}</div>
                                            </div>
                                        </div>

                                        <div className="border rounded-xl overflow-hidden">
                                            <table className="w-full text-sm text-left">
                                                <thead className="bg-muted/50 text-muted-foreground font-medium">
                                                    <tr>
                                                        <th className="px-6 py-3">Model</th>
                                                        <th className="px-6 py-3 text-right">Calls</th>
                                                        <th className="px-6 py-3 text-right">Tokens</th>
                                                        <th className="px-6 py-3 text-right">Avg. Tokens/Call</th>
                                                    </tr>
                                                </thead>
                                                <tbody className="divide-y">
                                                    {Object.entries(report.llm_stats.usage_by_model).map(([model, stats]: [string, any]) => (
                                                        <tr key={model} className="hover:bg-muted/5">
                                                            <td className="px-6 py-4 font-medium">{model}</td>
                                                            <td className="px-6 py-4 text-right">{stats.calls}</td>
                                                            <td className="px-6 py-4 text-right">{stats.tokens.toLocaleString()}</td>
                                                            <td className="px-6 py-4 text-right">
                                                                {Math.round(stats.tokens / stats.calls).toLocaleString()}
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

// Simple Button component fallback if UI lib is missing
function SimpleButton({ children, className, ...props }: any) {
    return (
        <button
            className={cn("px-4 py-2 rounded bg-primary text-primary-foreground hover:bg-primary/90 transition-colors", className)}
            {...props}
        >
            {children}
        </button>
    );
}
