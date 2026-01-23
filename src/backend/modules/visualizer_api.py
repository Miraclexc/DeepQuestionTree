"""
可视化模块 API
为前端提供树结构数据的接口
"""
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, Depends, status

from ..core.schema import SessionData, Node, TreeResponse, TreeNodeData, TreeEdge
from .persistence import get_session_manager, SessionManager

router = APIRouter(
    prefix="/api/visualizer",
    tags=["visualizer"],
    responses={404: {"description": "Not found"}},
)

@router.get("/sessions", response_model=List[Dict])
async def list_sessions(
    manager: SessionManager = Depends(get_session_manager)
):
    """
    获取所有可用会话列表
    """
    return manager.list_sessions()


@router.get("/sessions/{session_id}", response_model=SessionData)
async def get_session(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager)
):
    """
    获取会话完整数据
    """
    """
    获取会话完整数据
    """
    # 优先从内存获取活跃会话
    active_session = manager.get_active_session()
    if active_session and active_session.session_id == session_id:
        session = active_session
    else:
        session = await manager.load_session(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )
    return session


@router.get("/sessions/{session_id}/tree", response_model=TreeResponse)
async def get_tree_structure(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager)
):
    """
    获取用于可视化的树结构 (React Flow 格式)
    """
    # 优先从内存获取活跃会话，以支持实时状态（如 is_processing）
    active_session = manager.get_active_session()
    if active_session and active_session.session_id == session_id:
        session = active_session
    else:
        session = await manager.load_session(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )
    
    nodes_list: List[Dict] = []
    edges_list: List[Dict] = []
    
    # 遍历所有节点构建 React Flow 数据
    # 前端负责使用 Dagre 等库进行自动布局，或者我们这里给一个大致的层级布局
    
    # 计算每层的节点数，用于简单的 X 轴分布 (可选)
    # depth_counts = {} 
    
    for node_id, node in session.nodes.items():
        # 构建节点数据
        label = "Start"
        if node.interaction:
             # 截取前30个字作为标签
            label = node.interaction.question[:30] + ("..." if len(node.interaction.question) > 30 else "")
            
        tree_node = {
            "id": node.id,
            "type": "custom", # 前端将注册 'custom' 类型的节点组件
            "position": {"x": 0, "y": 0}, # 前端布局引擎会覆盖此值
            "data": {
                "label": label,
                "full_question": node.interaction.question if node.interaction else "Root",
                "visits": node.state.visit_count,
                "value": node.state.average_value,
                "depth": node.depth,
                "isPruned": node.is_pruned,
                "isTerminal": node.is_terminal,
                "isProcessing": node.is_processing,
                "factsCount": len(node.new_facts),
                "answer": _parse_answer(node.interaction.answer if node.interaction else "")
            }
        }
        nodes_list.append(tree_node)
        
        # 构建边数据
        for child_id in node.children_ids:
            edge = {
                "id": f"{node.id}-{child_id}",
                "source": node.id,
                "target": child_id,
                "type": "smoothstep", # 使用平滑阶梯线
                "animated": False 
            }
            edges_list.append(edge)
            
    return TreeResponse(nodes=nodes_list, edges=edges_list)


@router.get("/sessions/{session_id}/nodes/{node_id}", response_model=Node)
async def get_node_detail(
    session_id: str,
    node_id: str,
    manager: SessionManager = Depends(get_session_manager)
):
    """
    获取单个节点的详细信息
    """
    # 优先从内存获取活跃会话
    active_session = manager.get_active_session()
    if active_session and active_session.session_id == session_id:
        session = active_session
    else:
        session = await manager.load_session(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )
        
    node = session.get_node(node_id)
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node {node_id} not found in session {session_id}"
        )
        
    # 尝试清理回答数据
    if node.interaction and node.interaction.answer:
        node.interaction.answer = _parse_answer(node.interaction.answer)
        
    return node


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager)
):
    """
    删除会话
    """
    success = await manager.delete_session(session_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )
    return None


def _parse_answer(answer: str) -> str:
    """
    尝试解析可能是 JSON 格式的回答
    """
    import json
    try:
        if answer.strip().startswith("[") or answer.strip().startswith("{"):
            data = json.loads(answer)
            if isinstance(data, list):
                # 假设是 [{"content": "...", ...}] 格式
                contents = [item.get("content", "") for item in data if isinstance(item, dict)]
                return "\n".join(contents)
            elif isinstance(data, dict):
                return data.get("content", answer)
    except:
        pass
    return answer
