import { Route } from "lucide-react";

import { NodePathEntry } from "@/lib/types";

interface NodePathSectionProps {
    path: NodePathEntry[];
}

export function NodePathSection({ path }: NodePathSectionProps) {
    if (path.length === 0) {
        return null;
    }

    return (
        <div className="space-y-2">
            <h4 className="flex items-center gap-2 text-sm font-medium text-primary">
                <Route className="h-4 w-4" />
                Path Context
            </h4>
            <ol className="space-y-2">
                {path.map((entry) => (
                    <li
                        key={entry.id}
                        className="rounded-md border bg-card p-3 text-xs shadow-sm"
                    >
                        <div className="flex items-center justify-between gap-2">
                            <span className="font-medium">Depth {entry.depth}</span>
                            <span className="font-mono text-muted-foreground">
                                v={entry.value.toFixed(2)} / n={entry.visits}
                            </span>
                        </div>
                        <div className="mt-1 text-muted-foreground">
                            {entry.question || "Root node"}
                        </div>
                    </li>
                ))}
            </ol>
        </div>
    );
}

