"use client";

import { useEffect, useRef, useState } from "react";

import { fetchNode } from "@/lib/api";
import { NodeDetail } from "@/lib/types";

export function useNodeDetails(currentSessionId: string | null) {
    const [selectedNode, setSelectedNode] = useState<NodeDetail | null>(null);
    const [isNodePanelOpen, setIsNodePanelOpen] = useState(false);
    const previousSessionIdRef = useRef<string | null>(currentSessionId);

    useEffect(() => {
        const previousSessionId = previousSessionIdRef.current;

        if (previousSessionId !== currentSessionId) {
            setSelectedNode(null);
            setIsNodePanelOpen(false);
        }

        previousSessionIdRef.current = currentSessionId;
    }, [currentSessionId]);

    const openNode = async (nodeId: string) => {
        if (!currentSessionId) {
            return;
        }

        const node = await fetchNode(currentSessionId, nodeId);
        setSelectedNode(node);
        setIsNodePanelOpen(true);
    };

    return {
        selectedNode,
        isNodePanelOpen,
        openNode,
        closeNode: () => setIsNodePanelOpen(false),
        clearNode: () => setSelectedNode(null),
    };
}
