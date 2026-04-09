"use client";

import { Loader2 } from "lucide-react";

import { useDeepQuestionTree } from "@/hooks/useDeepQuestionTree";

import { NodePanel } from "./NodePanel";
import { ReportView } from "./ReportView";
import { Sidebar } from "./Sidebar";
import { TreeCanvas } from "./TreeCanvas";
import { ErrorBanner } from "./workspace/ErrorBanner";
import { NewSessionDialog } from "./workspace/NewSessionDialog";
import { WorkspaceHeader } from "./workspace/WorkspaceHeader";

export default function DeepQuestionTree() {
    const {
        currentSession,
        currentSessionId,
        canGenerateReport,
        draftGoal,
        error,
        generateReportDisabledReason,
        isGeneratingReport,
        isNewSessionDialogOpen,
        isLoadingTree,
        isNodePanelOpen,
        isStarting,
        reportData,
        selectedNode,
        sessions,
        showReport,
        systemStatus,
        treeData,
        onChangeNewSessionGoal,
        onClearError,
        onCloseNodePanel,
        onCloseNewSessionDialog,
        onCloseReport,
        onDeleteSession,
        onGenerateReport,
        onOpenNewSessionDialog,
        onNodeClick,
        onSelectSession,
        onResumeSession,
        onStartSession,
        onStopAndReport,
    } = useDeepQuestionTree();

    return (
        <div className="flex h-full w-full overflow-hidden">
            <Sidebar
                sessions={sessions}
                selectedSessionId={currentSessionId}
                onSelectSession={onSelectSession}
                onResumeSession={onResumeSession}
                onDeleteSession={onDeleteSession}
                onNewSession={onOpenNewSessionDialog}
                systemStatus={systemStatus}
            />

            <div className="flex-1 flex flex-col relative h-full">
                <WorkspaceHeader
                    currentSession={currentSession}
                    currentSessionId={currentSessionId}
                    canGenerateReport={canGenerateReport}
                    generateReportDisabledReason={generateReportDisabledReason}
                    onGenerateReport={onGenerateReport}
                    onStopAndReport={onStopAndReport}
                />

                <div className="flex-1 relative bg-slate-50 dark:bg-slate-900">
                    {currentSessionId ? (
                        <TreeCanvas
                            nodes={treeData.nodes}
                            edges={treeData.edges}
                            onNodeClick={onNodeClick}
                        />
                    ) : (
                        <div className="flex h-full items-center justify-center text-muted-foreground flex-col gap-4">
                            <BrainIcon className="w-16 h-16 opacity-20" />
                            <p>Select a session to view the reasoning tree</p>
                        </div>
                    )}

                    {isLoadingTree && (
                        <div className="absolute top-4 right-4 bg-background/80 backdrop-blur px-3 py-1 rounded-full text-xs font-medium border shadow-sm flex items-center gap-2">
                            <Loader2 className="h-3 w-3 animate-spin" />
                            Updating...
                        </div>
                    )}

                    <ErrorBanner message={error} onDismiss={onClearError} />
                </div>

                <NewSessionDialog
                    open={isNewSessionDialogOpen}
                    draftGoal={draftGoal}
                    isStarting={isStarting}
                    onClose={onCloseNewSessionDialog}
                    onStart={onStartSession}
                    onChangeGoal={onChangeNewSessionGoal}
                />

                {showReport && (
                    <ReportView
                        report={reportData}
                        isLoading={isGeneratingReport}
                        onClose={onCloseReport}
                    />
                )}
            </div>

            {isNodePanelOpen && (
                <div className="h-full border-l bg-background shadow-xl absolute right-0 top-0 z-40 animate-in slide-in-from-right duration-200">
                    <NodePanel
                        node={selectedNode}
                        onClose={onCloseNodePanel}
                    />
                </div>
            )}
        </div>
    );
}

function BrainIcon(props: any) {
    return (
        <svg
            {...props}
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
        >
            <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z" />
            <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z" />
        </svg>
    )
}
