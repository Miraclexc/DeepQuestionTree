"use client";

import React, { useCallback, useEffect } from 'react';
import ReactFlow, {
    Node,
    Edge,
    Controls,
    Background,
    useNodesState,
    useEdgesState,
    MarkerType,
    Handle,
    Position,
    NodeProps,
    ReactFlowProvider,
    useReactFlow
} from 'reactflow';
import 'reactflow/dist/style.css';
import { cn } from '@/lib/utils';
import { Brain, Ban, Flag, Loader2 } from 'lucide-react';
import Dagre from '@dagrejs/dagre';

// ... (code omitted)

const CustomNode = ({ data, selected }: NodeProps) => {
    // data matches TreeNodeData from backend
    const isPruned = data.isPruned;
    const isTerminal = data.isTerminal;
    const isProcessing = data.isProcessing;
    const isUnvisited = data.visits === 0;

    return (
        <div className={cn(
            "min-w-[180px] max-w-[250px] rounded-lg border bg-card px-4 py-3 shadow-md transition-all",
            selected ? "ring-2 ring-primary border-primary" : "hover:border-primary/50",
            isPruned && "opacity-60 bg-muted/50 border-destructive/50",
            isTerminal && "border-green-500/50 bg-green-50/50 dark:bg-green-900/10",
            isProcessing && "ring-2 ring-blue-500/50 border-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.5)] animate-pulse"
        )}>
            <Handle type="target" position={Position.Top} className="!bg-muted-foreground" />

            <div className="mb-2 flex items-center justify-between">
                <div className={cn(
                    "flex items-center gap-1.5 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
                    isPruned ? "bg-destructive/10 text-destructive" :
                        isTerminal ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300" :
                            isProcessing ? "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300" :
                                "bg-primary/10 text-primary"
                )}>
                    {isPruned ? <Ban className="h-3 w-3" /> :
                        isTerminal ? <Flag className="h-3 w-3" /> :
                            isProcessing ? <Loader2 className="h-3 w-3 animate-spin" /> :
                                <Brain className="h-3 w-3" />}
                    {isPruned ? "Pruned" :
                        isTerminal ? "End" :
                            isProcessing ? "Thinking..." : "Thought"}
                </div>
                <div className="text-[10px] text-muted-foreground font-mono">
                    d:{data.depth}
                </div>
            </div>

            <div className="text-xs font-medium leading-snug line-clamp-3 mb-2">
                {data.label}
            </div>

            <div className="flex items-center justify-between border-t pt-2 mt-2">
                <div className="flex flex-col">
                    <span className="text-[10px] text-muted-foreground uppercase">Value</span>
                    <span className="text-xs font-bold font-mono">{data.value?.toFixed(2) ?? "0.00"}</span>
                </div>
                <div className="flex flex-col items-end">
                    <span className="text-[10px] text-muted-foreground uppercase">Visits</span>
                    <span className="text-xs font-bold font-mono">{data.visits ?? 0}</span>
                </div>
            </div>

            <Handle type="source" position={Position.Bottom} className="!bg-muted-foreground" />
        </div>
    );
};

const nodeTypes = {
    custom: CustomNode,
};

// --- Main Canvas Component ---

interface TreeCanvasProps {
    nodes: any[];
    edges: any[];
    onNodeClick: (event: React.MouseEvent, node: Node) => void;
}

const getLayoutedElements = (nodes: Node[], edges: Edge[]) => {
    const dagreGraph = new Dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));

    // Direction: Top to Bottom (TB)
    dagreGraph.setGraph({ rankdir: 'TB' });

    nodes.forEach((node) => {
        // Approximate width/height for layouting
        dagreGraph.setNode(node.id, { width: 220, height: 150 });
    });

    edges.forEach((edge) => {
        dagreGraph.setEdge(edge.source, edge.target);
    });

    Dagre.layout(dagreGraph);

    const layoutedNodes = nodes.map((node) => {
        const nodeWithPosition = dagreGraph.node(node.id);

        // Dagre gives center point, ReactFlow expects top-left
        return {
            ...node,
            position: {
                x: nodeWithPosition.x - 110, // width/2
                y: nodeWithPosition.y - 75,  // height/2
            },
        };
    });

    return { nodes: layoutedNodes, edges };
};

function TreeCanvasInner({ nodes: initialNodes, edges: initialEdges, onNodeClick }: TreeCanvasProps) {
    const { fitView } = useReactFlow();
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);

    useEffect(() => {
        if (initialNodes.length > 0) {
            const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
                initialNodes,
                initialEdges
            );
            setNodes(layoutedNodes);
            setEdges(layoutedEdges);

            // Wait for render then fit view
            window.requestAnimationFrame(() => {
                fitView({ padding: 0.2 });
            });
        } else {
            setNodes([]);
            setEdges([]);
        }
    }, [initialNodes, initialEdges, setNodes, setEdges, fitView]);

    return (
        <div className="h-full w-full bg-slate-50 dark:bg-slate-950">
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={onNodeClick}
                nodeTypes={nodeTypes}
                proOptions={{ hideAttribution: true }}
                defaultEdgeOptions={{
                    type: 'smoothstep',
                    markerEnd: { type: MarkerType.ArrowClosed },
                    animated: false,
                    style: { strokeWidth: 2, stroke: '#64748b' }
                }}
            >
                <Background gap={20} size={1} color="var(--border)" className="opacity-40" />
                <Controls className="bg-white dark:bg-gray-900 border shadow-sm" />
            </ReactFlow>
        </div>
    );
}

export function TreeCanvas(props: TreeCanvasProps) {
    return (
        <ReactFlowProvider>
            <TreeCanvasInner {...props} />
        </ReactFlowProvider>
    );
}
