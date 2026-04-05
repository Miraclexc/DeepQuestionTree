import { NodeDetail } from "@/lib/types";

interface NodeStatisticsProps {
    node: NodeDetail;
}

export function NodeStatistics({ node }: NodeStatisticsProps) {
    return (
        <div className="grid grid-cols-2 gap-4">
            <div className="rounded-lg bg-muted/50 p-3 text-center">
                <div className="text-xs text-muted-foreground uppercase">Visits</div>
                <div className="text-xl font-bold text-primary">{node.state.visit_count}</div>
            </div>
            <div className="rounded-lg bg-muted/50 p-3 text-center">
                <div className="text-xs text-muted-foreground uppercase">Value</div>
                <div className="text-xl font-bold text-primary">
                    {node.state.average_value.toFixed(2)}
                </div>
            </div>
        </div>
    );
}

