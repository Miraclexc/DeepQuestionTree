import { NodeDetail } from "@/lib/types";
import { Brain, ExternalLink, Target, X } from "lucide-react";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { NodeFactsSection } from "./node-panel/NodeFactsSection";
import { NodeMetadataSection } from "./node-panel/NodeMetadataSection";
import { NodePathSection } from "./node-panel/NodePathSection";
import { NodeStatistics } from "./node-panel/NodeStatistics";

interface NodePanelProps {
    node: NodeDetail | null;
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
                    aria-label="Close node details"
                    className="rounded-full p-1 hover:bg-muted transition-colors"
                >
                    <X className="h-4 w-4 text-muted-foreground" />
                </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-6">
                <NodeStatistics node={node} />

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

                <NodeFactsSection facts={node.new_facts} />
                <NodePathSection path={node.path} />
                <NodeMetadataSection node={node} />
            </div>
        </div>
    );
}
