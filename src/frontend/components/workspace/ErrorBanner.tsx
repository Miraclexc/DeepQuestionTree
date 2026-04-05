import { AlertCircle } from "lucide-react";

interface ErrorBannerProps {
    message: string | null;
    onDismiss: () => void;
}

export function ErrorBanner({ message, onDismiss }: ErrorBannerProps) {
    if (!message) {
        return null;
    }

    return (
        <div className="absolute top-4 left-4 right-4 mx-auto max-w-md bg-destructive/10 text-destructive border border-destructive/20 px-4 py-2 rounded-lg text-sm flex items-center gap-2">
            <AlertCircle className="h-4 w-4" />
            {message}
            <button onClick={onDismiss} className="ml-auto hover:underline">
                Dismiss
            </button>
        </div>
    );
}

