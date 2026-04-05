import { cn } from "@/lib/utils";

interface ConnectionIndicatorProps {
    systemStatus: "connected" | "disconnected" | "unknown";
}

export function ConnectionIndicator({ systemStatus }: ConnectionIndicatorProps) {
    return (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <div
                className={cn(
                    "w-2 h-2 rounded-full animate-pulse",
                    systemStatus === "connected"
                        ? "bg-green-500"
                        : systemStatus === "disconnected"
                          ? "bg-red-500"
                          : "bg-gray-400",
                )}
            />
            {systemStatus === "connected"
                ? "System Ready"
                : systemStatus === "disconnected"
                  ? "Disconnected"
                  : "Checking..."}
        </div>
    );
}

