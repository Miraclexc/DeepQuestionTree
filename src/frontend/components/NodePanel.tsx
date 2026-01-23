import { Node } from "@/lib/types";
import { X, Brain, ExternalLink, Lightbulb, Target } from "lucide-react";
import { MarkdownRenderer } from "./MarkdownRenderer";

interface NodePanelProps {
    node: Node | null;
    onClose: () => void;
}

export function NodePanel({ node, onClose }: NodePanelProps) {
    if (!node) return null;

    return (
        <div className="flex h-full w-96 flex-col border-l bg-background shadow-xl">
            <div className="flex items-center justify-between border-b px-4 py-3">
                <h3 className="font-semibold flex items-center gap-2">
                    <Target className="h-4 w-4 text-primary" />
                    Node Details
                </h3>
                <button
                    onClick={onClose}
                    className="rounded-full p-1 hover:bg-muted transition-colors"
                >
                    <X className="h-4 w-4 text-muted-foreground" />
                </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-6">
                {/* Basic Stats */}
                <div className="grid grid-cols-2 gap-4">
                    <div className="rounded-lg bg-muted/50 p-3 text-center">
                        <div className="text-xs text-muted-foreground uppercase">Visits</div>
                        <div className="text-xl font-bold text-primary">{node.state?.visit_count ?? 0}</div>
                    </div>
                    <div className="rounded-lg bg-muted/50 p-3 text-center">
                        <div className="text-xs text-muted-foreground uppercase">Value</div>
                        <div className="text-xl font-bold text-primary">{node.state?.average_value?.toFixed(2) ?? "0.00"}</div>
                    </div>
                </div>

                {/* Question */}
                <div className="space-y-2">
                    <h4 className="flex items-center gap-2 text-sm font-medium text-primary">
                        <Brain className="h-4 w-4" />
                        Question
                    </h4>
                    <div className="rounded-md border bg-card p-3 text-sm shadow-sm">
                        {node.interaction?.question || "Starting Point"}
                    </div>
                </div>

                {/* Answer */}
                <div className="space-y-2">
                    <h4 className="flex items-center gap-2 text-sm font-medium text-primary">
                        <ExternalLink className="h-4 w-4" />
                        Answer
                    </h4>
                    <div className="rounded-md border bg-muted/20 p-3 text-sm leading-relaxed">
                        <MarkdownRenderer content={node.interaction?.answer || "No answer yet."} />
                    </div>
                </div>

                {/* Facts */}
                {node.new_facts && node.new_facts.length > 0 && (
                    <div className="space-y-2">
                        <h4 className="flex items-center gap-2 text-sm font-medium text-primary">
                            <Lightbulb className="h-4 w-4" />
                            Facts Extracted ({node.new_facts.length})
                        </h4>
                        <ul className="space-y-2">
                            {node.new_facts.map(fact => (
                                <li key={fact.id} className="text-xs bg-yellow-50 dark:bg-yellow-900/20 text-yellow-800 dark:text-yellow-200 p-2 rounded border border-yellow-200 dark:border-yellow-800/50">
                                    <MarkdownRenderer content={fact.content} />
                                </li>
                            ))}
                        </ul>
                    </div>
                )}

                {/* Metadata */}
                <div className="pt-4 border-t text-xs text-muted-foreground space-y-1">
                    <div className="flex justify-between">
                        <span>ID:</span>
                        <span className="font-mono">{node.id.slice(0, 8)}...</span>
                    </div>
                    <div className="flex justify-between">
                        <span>Parent ID:</span>
                        <span className="font-mono">{node.parent_id ? `${node.parent_id.slice(0, 8)}...` : "None"}</span>
                    </div>
                    <div className="flex justify-between">
                        <span>Created:</span>
                        <span>{new Date(node.created_at).toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                        <span>Pruned:</span>
                        <span className={node.is_pruned ? "text-destructive font-bold" : ""}>{node.is_pruned ? "YES" : "NO"}</span>
                    </div>
                    {node.prune_reason && (
                        <div className="flex justify-between text-destructive">
                            <span>Reason:</span>
                            <span>{node.prune_reason}</span>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
