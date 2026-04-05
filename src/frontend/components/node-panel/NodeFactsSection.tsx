import { Lightbulb } from "lucide-react";

import { FactReadModel } from "@/lib/types";

import { MarkdownRenderer } from "../MarkdownRenderer";

interface NodeFactsSectionProps {
    facts: FactReadModel[];
}

export function NodeFactsSection({ facts }: NodeFactsSectionProps) {
    if (facts.length === 0) {
        return null;
    }

    return (
        <div className="space-y-2">
            <h4 className="flex items-center gap-2 text-sm font-medium text-primary">
                <Lightbulb className="h-4 w-4" />
                Facts Extracted ({facts.length})
            </h4>
            <ul className="space-y-2">
                {facts.map((fact) => (
                    <li
                        key={fact.id}
                        className="text-xs bg-yellow-50 dark:bg-yellow-900/20 text-yellow-800 dark:text-yellow-200 p-2 rounded border border-yellow-200 dark:border-yellow-800/50"
                    >
                        <MarkdownRenderer content={fact.content} />
                    </li>
                ))}
            </ul>
        </div>
    );
}

