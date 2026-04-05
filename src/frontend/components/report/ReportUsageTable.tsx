import { LlmUsageStats } from "@/lib/types";

interface ReportUsageTableProps {
    usageByModel: Record<string, LlmUsageStats>;
}

export function ReportUsageTable({ usageByModel }: ReportUsageTableProps) {
    return (
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
                    {Object.entries(usageByModel).map(([model, stats]) => (
                        <tr key={model} className="hover:bg-muted/5">
                            <td className="px-6 py-4 font-medium">{model}</td>
                            <td className="px-6 py-4 text-right">{stats.calls}</td>
                            <td className="px-6 py-4 text-right">{stats.tokens.toLocaleString()}</td>
                            <td className="px-6 py-4 text-right">
                                {(stats.calls === 0 ? 0 : Math.round(stats.tokens / stats.calls)).toLocaleString()}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
