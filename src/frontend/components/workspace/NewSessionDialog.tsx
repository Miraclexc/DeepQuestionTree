import { Loader2 } from "lucide-react";

interface NewSessionDialogProps {
    open: boolean;
    draftGoal: string;
    isStarting: boolean;
    onClose: () => void;
    onStart: () => Promise<void>;
    onChangeGoal: (goal: string) => void;
}

export function NewSessionDialog({
    open,
    draftGoal,
    isStarting,
    onClose,
    onStart,
    onChangeGoal,
}: NewSessionDialogProps) {
    if (!open) {
        return null;
    }

    return (
        <div className="absolute inset-0 bg-background/80 backdrop-blur z-50 flex items-center justify-center p-4">
            <div className="bg-card border shadow-xl rounded-xl w-full max-w-lg p-6 space-y-4">
                <h2 className="text-xl font-bold">Start New Exploration</h2>
                <div className="space-y-2">
                    <label className="text-sm font-medium">Research Goal / Question</label>
                    <textarea
                        value={draftGoal}
                        onChange={(event) => onChangeGoal(event.target.value)}
                        className="w-full h-32 p-3 rounded-md border resize-none focus:ring-2 focus:ring-primary focus:border-transparent outline-none"
                        placeholder="e.g. Analyze the impact of quantum computing on cryptography..."
                    />
                </div>
                <div className="flex justify-end gap-3">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-sm font-medium hover:bg-muted rounded-md"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={onStart}
                        disabled={isStarting || !draftGoal.trim()}
                        className="px-4 py-2 text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 rounded-md flex items-center gap-2"
                    >
                        {isStarting && <Loader2 className="h-4 w-4 animate-spin" />}
                        Start Analysis
                    </button>
                </div>
            </div>
        </div>
    );
}
