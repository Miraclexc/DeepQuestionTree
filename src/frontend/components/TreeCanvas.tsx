"use client";

import { useEffect, useMemo, useRef } from 'react';
import ReactFlow, {
    Edge,
    Controls,
    Background,
    useNodesState,
    useEdgesState,
    MarkerType,
    Node as FlowNode,
    NodeTypes,
    ReactFlowProvider,
    useReactFlow
} from 'reactflow';
import 'reactflow/dist/style.css';
import Dagre from '@dagrejs/dagre';
import { TreeFlowEdge, TreeFlowNode, TreeNodeData } from '@/lib/types';
import { TreeNodeCard } from './tree/TreeNodeCard';

const nodeTypes: NodeTypes = {
    custom: TreeNodeCard,
};

interface TreeCanvasProps {
    nodes: TreeFlowNode[];
    edges: TreeFlowEdge[];
    onNodeClick: (nodeId: string) => void;
}

type CanvasNode = FlowNode<TreeNodeData>;
type CanvasEdge = Edge;

type LayoutCache = {
    positions: Map<string, { x: number; y: number }>;
    signature: string;
};

const getLayoutedElements = (nodes: CanvasNode[], edges: CanvasEdge[]) => {
    const dagreGraph = new Dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));

    dagreGraph.setGraph({ rankdir: 'TB' });

    nodes.forEach((node) => {
        dagreGraph.setNode(node.id, { width: 220, height: 150 });
    });

    edges.forEach((edge) => {
        dagreGraph.setEdge(edge.source, edge.target);
    });

    Dagre.layout(dagreGraph);

    const layoutedNodes = nodes.map((node) => {
        const nodeWithPosition = dagreGraph.node(node.id);

        return {
            ...node,
            position: {
                x: nodeWithPosition.x - 110,
                y: nodeWithPosition.y - 75,
            },
        };
    });

    return { nodes: layoutedNodes, edges };
};

const getTopologySignature = (nodes: CanvasNode[], edges: CanvasEdge[]) => {
    const nodeIds = nodes.map((node) => node.id).sort().join('|');
    const edgeIds = edges
        .map((edge) => `${edge.source}->${edge.target}`)
        .sort()
        .join('|');
    return `${nodeIds}::${edgeIds}`;
};

function TreeCanvasInner({ nodes: initialNodes, edges: initialEdges, onNodeClick }: TreeCanvasProps) {
    const { fitView } = useReactFlow();
    const [nodes, setNodes, onNodesChange] = useNodesState<TreeNodeData>([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState<CanvasEdge>([]);
    const layoutCacheRef = useRef<LayoutCache | null>(null);
    const topologySignature = useMemo(
        () => getTopologySignature(initialNodes as CanvasNode[], initialEdges as CanvasEdge[]),
        [initialEdges, initialNodes],
    );

    useEffect(() => {
        if (initialNodes.length > 0) {
            const cachedLayout = layoutCacheRef.current;
            if (cachedLayout && cachedLayout.signature === topologySignature) {
                setNodes(
                    initialNodes.map((node) => ({
                        ...node,
                        position: cachedLayout.positions.get(node.id) ?? node.position,
                    })) as CanvasNode[],
                );
                setEdges(initialEdges as CanvasEdge[]);
                return;
            }

            const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
                initialNodes as CanvasNode[],
                initialEdges as CanvasEdge[],
            );
            setNodes(layoutedNodes);
            setEdges(layoutedEdges);
            layoutCacheRef.current = {
                signature: topologySignature,
                positions: new Map(
                    layoutedNodes.map((node) => [node.id, node.position]),
                ),
            };

            window.requestAnimationFrame(() => {
                fitView({ padding: 0.2 });
            });
        } else {
            setNodes([]);
            setEdges([]);
            layoutCacheRef.current = null;
        }
    }, [fitView, initialEdges, initialNodes, setEdges, setNodes, topologySignature]);

    return (
        <div className="h-full w-full bg-slate-50 dark:bg-slate-950">
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={(_event, node) => onNodeClick(node.id)}
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
