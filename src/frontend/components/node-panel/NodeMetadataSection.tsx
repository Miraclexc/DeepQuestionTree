import { NodeDetail } from "@/lib/types";

interface NodeMetadataSectionProps {
    node: NodeDetail;
}

export function NodeMetadataSection({ node }: NodeMetadataSectionProps) {
    return (
        <div className="pt-4 border-t text-xs text-muted-foreground space-y-1">
            <div className="flex justify-between">
                <span>ID:</span>
                <span className="font-mono">{node.id.slice(0, 8)}...</span>
            </div>
            <div className="flex justify-between">
                <span>Parent ID:</span>
                <span className="font-mono">
                    {node.parent_id ? `${node.parent_id.slice(0, 8)}...` : "None"}
                </span>
            </div>
            <div className="flex justify-between">
                <span>Created:</span>
                <span>{new Date(node.created_at).toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
                <span>Pruned:</span>
                <span className={node.is_pruned ? "text-destructive font-bold" : ""}>
                    {node.is_pruned ? "YES" : "NO"}
                </span>
            </div>
            {node.prune_reason && (
                <div className="flex justify-between text-destructive">
                    <span>Reason:</span>
                    <span>{node.prune_reason}</span>
                </div>
            )}
            {node.interaction?.model_used && (
                <div className="flex justify-between">
                    <span>Model:</span>
                    <span>{node.interaction.model_used}</span>
                </div>
            )}
        </div>
    );
}

