"use client";

import React, { useEffect, useState, useCallback } from 'react';
import { Sidebar } from './Sidebar';
import { TreeCanvas } from './TreeCanvas';
import { NodePanel } from './NodePanel';
import { ReportView } from './ReportView';
import { fetchSessions, fetchTree, fetchNode, startSession, stopSession, deleteSession, fetchReport, getSystemStatus } from '@/lib/api';
import { Node, SessionData } from '@/lib/types';
import { Loader2, Play, Square, AlertCircle, FileText } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function DeepQuestionTree() {
    const [sessions, setSessions] = useState<any[]>([]);
    const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
    const [treeData, setTreeData] = useState<{ nodes: any[], edges: any[] }>({ nodes: [], edges: [] });
    const [selectedNode, setSelectedNode] = useState<Node | null>(null);
    const [isNodePanelOpen, setIsNodePanelOpen] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Report State
    const [showReport, setShowReport] = useState(false);
    const [reportData, setReportData] = useState<any>(null);
    const [isGeneratingReport, setIsGeneratingReport] = useState(false);

    // 新会话对话框状态（简化）
    const [showNewSessionInput, setShowNewSessionInput] = useState(false);
    const [newGoal, setNewGoal] = useState("");
    const [isStarting, setIsStarting] = useState(false);

    const [systemStatus, setSystemStatus] = useState<'connected' | 'disconnected' | 'unknown'>('unknown');

    // System Status Polling
    useEffect(() => {
        const checkStatus = async () => {
            try {
                await getSystemStatus();
                setSystemStatus('connected');
            } catch (err) {
                setSystemStatus('disconnected');
            }
        };

        checkStatus();
        const interval = setInterval(checkStatus, 5000); // Check every 5s
        return () => clearInterval(interval);
    }, []);

    // 加载会话列表
    const loadSessions = useCallback(async () => {
        try {
            const data = await fetchSessions();
            setSessions(data);
        } catch (err) {
            console.error("Failed to load sessions", err);
        }
    }, []);

    useEffect(() => {
        loadSessions();
        const interval = setInterval(loadSessions, 10000); // 每 10 秒轮询一次
        return () => clearInterval(interval);
    }, [loadSessions]);

    // 会话更改时加载树
    useEffect(() => {
        if (!currentSessionId) {
            setTreeData({ nodes: [], edges: [] });
            return;
        }

        const loadTree = async () => {
            setIsLoading(true);
            try {
                const data = await fetchTree(currentSessionId);
                setTreeData(data);
                setError(null);
            } catch (err) {
                console.error(err);
                setError("Failed to load tree data");
            } finally {
                setIsLoading(false);
            }
        };

        loadTree();
        // Poll for tree updates if session is running (simulated by polling always for now)
        const interval = setInterval(loadTree, 2000);
        return () => clearInterval(interval);

    }, [currentSessionId]);

    const handleNodeClick = async (event: React.MouseEvent, node: any) => {
        if (!currentSessionId) return;
        try {
            const fullNode = await fetchNode(currentSessionId, node.id);
            setSelectedNode(fullNode);
            setIsNodePanelOpen(true);
        } catch (err) {
            console.error(err);
        }
    };

    const handleStartSession = async () => {
        if (!newGoal.trim()) return;
        setIsStarting(true);
        try {
            const res = await startSession(newGoal);
            await loadSessions();
            setCurrentSessionId(res.session_id);
            setShowNewSessionInput(false);
            setNewGoal("");
        } catch (err) {
            setError("Failed to start session");
        } finally {
            setIsStarting(false);
        }
    };

    // 删除会话
    const handleDeleteSession = async (sessionId: string) => {
        try {
            await deleteSession(sessionId);
            // 本地移除
            setSessions(prev => prev.filter(s => s.session_id !== sessionId));
            // 如果删除的是当前会话，清空状态
            if (currentSessionId === sessionId) {
                setCurrentSessionId(null);
                setTreeData({ nodes: [], edges: [] });
            }
        } catch (err) {
            console.error("Failed to delete session", err);
            setError("Failed to delete session");
        }
    };

    // 生成报告
    const handleGenerateReport = async () => {
        if (!currentSessionId) return;
        setShowReport(true);
        setReportData(null); // Clear previous report data
        setIsGeneratingReport(true);
        try {
            const data = await fetchReport(currentSessionId);
            setReportData(data);
        } catch (err) {
            console.error("Failed to generate report", err);
            setError("Failed to generate report");
            // setShowReport(false); // Optional: close on error or show error in modal
        } finally {
            setIsGeneratingReport(false);
        }
    };

    return (
        <div className="flex h-full w-full overflow-hidden">
            {/* Sidebar */}
            <Sidebar
                sessions={sessions}
                selectedSessionId={currentSessionId}
                onSelectSession={setCurrentSessionId}
                onDeleteSession={handleDeleteSession}
                onNewSession={() => setShowNewSessionInput(true)}
                systemStatus={systemStatus}
            />

            {/* Main Content */}
            <div className="flex-1 flex flex-col relative h-full">
                {/* Header / Toolbar */}
                <div className="h-14 border-b bg-background/50 backdrop-blur flex items-center justify-between px-4">
                    <div className="font-semibold text-lg flex items-center gap-2">
                        {currentSessionId ? (
                            sessions.find(s => s.session_id === currentSessionId)?.global_goal || "Unknown Session"
                        ) : "Deep Question Tree"}
                    </div>

                    {currentSessionId && (
                        <div className="flex items-center gap-3">
                            {(() => {
                                const session = sessions.find(s => s.session_id === currentSessionId);
                                if (!session) return null;
                                const isRunning = session.status === 'running';
                                return (
                                    <div className={cn(
                                        "px-2 py-0.5 rounded-full text-xs font-medium border flex items-center gap-1.5 transition-colors",
                                        "bg-muted/40 text-muted-foreground border-transparent"
                                    )}>
                                        <div className={cn("w-1.5 h-1.5 rounded-full", isRunning ? "bg-blue-400/70 animate-pulse" : "bg-gray-400/70")} />
                                        {isRunning ? "Running Explorations" : "Analysis Completed"}
                                    </div>
                                );
                            })()}
                        </div>
                    )}

                    {currentSessionId && (
                        <div className="flex items-center gap-2">
                            <button
                                onClick={async () => {
                                    if (confirm("Are you sure you want to stop the exploration and generate the report?")) {
                                        await stopSession();
                                        await handleGenerateReport();
                                    }
                                }}
                                disabled={sessions.find(s => s.session_id === currentSessionId)?.status !== 'running'}
                                className="px-3 py-1.5 text-xs font-medium bg-destructive/10 text-destructive hover:bg-destructive/20 disabled:opacity-50 disabled:cursor-not-allowed rounded-md flex items-center gap-1.5 transition-colors border border-destructive/20"
                            >
                                <Square className="h-3.5 w-3.5 fill-current" />
                                Stop & Report
                            </button>

                            <button
                                onClick={handleGenerateReport}
                                className="px-3 py-1.5 text-xs font-medium bg-primary/10 text-primary hover:bg-primary/20 rounded-md flex items-center gap-1.5 transition-colors"
                            >
                                <FileText className="h-3.5 w-3.5" />
                                Generated Report
                            </button>

                            <div className="bg-muted px-2 py-1 rounded text-[10px] text-muted-foreground font-mono">
                                ID: {currentSessionId.slice(0, 8)}
                            </div>
                        </div>
                    )}
                </div>

                {/* Canvas Area */}
                <div className="flex-1 relative bg-slate-50 dark:bg-slate-900">
                    {currentSessionId ? (
                        <TreeCanvas
                            nodes={treeData.nodes}
                            edges={treeData.edges}
                            onNodeClick={handleNodeClick}
                        />
                    ) : (
                        <div className="flex h-full items-center justify-center text-muted-foreground flex-col gap-4">
                            <BrainIcon className="w-16 h-16 opacity-20" />
                            <p>Select a session to view the reasoning tree</p>
                        </div>
                    )}

                    {/* Loading Indicator */}
                    {isLoading && (
                        <div className="absolute top-4 right-4 bg-background/80 backdrop-blur px-3 py-1 rounded-full text-xs font-medium border shadow-sm flex items-center gap-2">
                            <Loader2 className="h-3 w-3 animate-spin" />
                            Updating...
                        </div>
                    )}

                    {/* Error Banner */}
                    {error && (
                        <div className="absolute top-4 left-4 right-4 mx-auto max-w-md bg-destructive/10 text-destructive border border-destructive/20 px-4 py-2 rounded-lg text-sm flex items-center gap-2">
                            <AlertCircle className="h-4 w-4" />
                            {error}
                            <button onClick={() => setError(null)} className="ml-auto hover:underline">Dismiss</button>
                        </div>
                    )}
                </div>

                {/* New Session Modal Overlay */}
                {showNewSessionInput && (
                    <div className="absolute inset-0 bg-background/80 backdrop-blur z-50 flex items-center justify-center p-4">
                        <div className="bg-card border shadow-xl rounded-xl w-full max-w-lg p-6 space-y-4">
                            <h2 className="text-xl font-bold">Start New Exploration</h2>
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Research Goal / Question</label>
                                <textarea
                                    value={newGoal}
                                    onChange={(e) => setNewGoal(e.target.value)}
                                    className="w-full h-32 p-3 rounded-md border resize-none focus:ring-2 focus:ring-primary focus:border-transparent outline-none"
                                    placeholder="e.g. Analyze the impact of quantum computing on cryptography..."
                                />
                            </div>
                            <div className="flex justify-end gap-3">
                                <button
                                    onClick={() => setShowNewSessionInput(false)}
                                    className="px-4 py-2 text-sm font-medium hover:bg-muted rounded-md"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={handleStartSession}
                                    disabled={isStarting || !newGoal.trim()}
                                    className="px-4 py-2 text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 rounded-md flex items-center gap-2"
                                >
                                    {isStarting && <Loader2 className="h-4 w-4 animate-spin" />}
                                    Start Analysis
                                </button>
                            </div>
                        </div>
                    </div>
                )}

                {/* Report View Modal */}
                {showReport && (
                    <ReportView
                        report={reportData}
                        isLoading={isGeneratingReport}
                        onClose={() => setShowReport(false)}
                    />
                )}
            </div>

            {/* Right Details Panel */}
            {isNodePanelOpen && (
                <div className="h-full border-l bg-background shadow-xl absolute right-0 top-0 z-40 animate-in slide-in-from-right duration-200">
                    <NodePanel
                        node={selectedNode}
                        onClose={() => setIsNodePanelOpen(false)}
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
