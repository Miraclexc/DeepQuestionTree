"""
核心数据结构定义
使用 Pydantic v2 定义所有数据模型，确保类型安全和序列化便利性
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum

from pydantic import BaseModel, Field


class Fact(BaseModel):
    """表示一个从回答中提取出的确切事实"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="事实的唯一标识符")
    content: str = Field(..., description="事实的具体文本内容")
    source_node_id: str = Field(..., description="该事实来源于哪个节点(回答)")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="置信度 0.0-1.0")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")


class QAInteraction(BaseModel):
    """表示一次问答交互"""
    question: str = Field(..., description="向LLM提出的问题")
    answer: str = Field(..., description="LLM的完整回答")
    summary: Optional[str] = Field(None, description="回答的摘要（用于压缩上下文）")
    tokens_used: int = Field(default=0, ge=0, description="本次交互消耗的Token数")
    model_used: Optional[str] = Field(None, description="使用的模型名称")
    created_at: datetime = Field(default_factory=datetime.now, description="交互时间")


class NodeState(BaseModel):
    """MCTS 节点的统计状态，用于计算 UCT"""
    visit_count: int = Field(default=0, ge=0, description="访问次数 (n_j)")
    value_sum: float = Field(default=0.0, description="累积价值总和 (用于计算平均值)")

    @property
    def average_value(self) -> float:
        """计算平均价值"""
        if self.visit_count == 0:
            return 0.0
        return self.value_sum / self.visit_count


class Node(BaseModel):
    """思维树的节点"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="节点的唯一标识符")
    parent_id: Optional[str] = Field(None, description="父节点ID，根节点为None")
    children_ids: List[str] = Field(default_factory=list, description="子节点ID列表")

    depth: int = Field(default=0, ge=0, description="当前深度")

    # 内容数据
    interaction: Optional[QAInteraction] = Field(None, description="该节点对应的问答，根节点可能为空")
    new_facts: List[Fact] = Field(default_factory=list, description="该节点产生的新事实列表")

    # MCTS 状态
    state: NodeState = Field(default_factory=NodeState, description="MCTS统计状态")
    is_terminal: bool = Field(default=False, description="是否为终止节点（不可再分）")
    is_pruned: bool = Field(default=False, description="是否已被剪枝")
    is_processing: bool = Field(default=False, description="是否正在被处理（并行计算中）")
    prune_reason: Optional[str] = Field(None, description="剪枝原因")

    created_at: datetime = Field(default_factory=datetime.now, description="节点创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="最后更新时间")

    def uct_value(self, parent_visit_count: int, c_param: float) -> float:
        """
        计算 UCT 值
        公式: Q(s,a) + C * sqrt(ln(N) / n)

        Args:
            parent_visit_count: 父节点的访问次数 (N)
            c_param: 探索常数 (C)

        Returns:
            UCT 值，未访问节点返回无穷大
        """
        if self.state.visit_count == 0:
            return float('inf')  # 保证未访问节点优先被访问

        exploitation = self.state.average_value
        exploration = c_param * math.sqrt(math.log(parent_visit_count) / self.state.visit_count)
        return exploitation + exploration

    def add_child(self, child_id: str) -> None:
        """添加子节点"""
        if child_id not in self.children_ids:
            self.children_ids.append(child_id)
            self.updated_at = datetime.now()

    def mark_pruned(self, reason: str) -> None:
        """标记节点为已剪枝"""
        self.is_pruned = True
        self.prune_reason = reason
        self.updated_at = datetime.now()


class SessionStatus(str, Enum):
    """会话状态枚举"""
    RUNNING = "running"      # 正在运行
    PAUSED = "paused"        # 暂停
    COMPLETED = "completed"  # 已完成
    ERROR = "error"          # 出错


class SessionData(BaseModel):
    """完整的会话数据，可直接序列化为 JSON 文件"""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="会话的唯一标识符")
    root_node_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="根节点ID")
    nodes: Dict[str, Node] = Field(default_factory=dict, description="ID到Node的扁平化映射，方便查找")
    global_facts: List[Fact] = Field(default_factory=list, description="全局已确认的事实列表")
    global_goal: str = Field(..., description="用户的初始核心问题")

    # 运行统计
    total_simulations: int = Field(default=0, ge=0, description="总模拟次数")
    total_tokens_used: int = Field(default=0, ge=0, description="总Token消耗")

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now, description="会话创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="最后更新时间")

    # 状态
    status: SessionStatus = Field(SessionStatus.RUNNING, description="会话状态")
    error_message: Optional[str] = Field(None, description="错误信息（如果有）")

    # 配置快照
    mcts_config: Optional[Dict] = Field(None, description="MCTS配置快照")

    # 报告数据
    report: Optional[Dict] = Field(None, description="生成的完整报告与统计")

    def get_node(self, node_id: str) -> Optional[Node]:
        """安全获取节点"""
        return self.nodes.get(node_id)

    def add_node(self, node: Node) -> None:
        """添加节点到会话"""
        self.nodes[node.id] = node
        self.updated_at = datetime.now()

    def add_global_fact(self, fact: Fact) -> None:
        """添加全局事实"""
        self.global_facts.append(fact)
        self.updated_at = datetime.now()

    def increment_simulations(self) -> None:
        """增加模拟次数"""
        self.total_simulations += 1
        self.updated_at = datetime.now()

    def get_tree_depth(self) -> int:
        """获取树的最大深度"""
        if not self.nodes:
            return 0
        return max(node.depth for node in self.nodes.values())

    def get_total_nodes(self) -> int:
        """获取节点总数"""
        return len(self.nodes)

    def get_active_nodes(self) -> List[Node]:
        """获取所有活跃节点（未被剪枝且非终止）"""
        return [
            node for node in self.nodes.values()
            if not node.is_pruned and not node.is_terminal
        ]

    def get_best_path(self) -> List[Node]:
        """获取访问次数最多的路径"""
        if self.root_node_id not in self.nodes:
            return []

        path = []
        current_id = self.root_node_id

        while current_id:
            current_node = self.nodes[current_id]
            path.append(current_node)

            # 选择访问次数最多的子节点
            if current_node.children_ids:
                best_child_id = max(
                    current_node.children_ids,
                    key=lambda cid: self.nodes[cid].state.visit_count
                )
                current_id = best_child_id
            else:
                break

        return path


# 用于前端响应的数据结构
class TreeNodeData(BaseModel):
    """前端树节点数据"""
    id: str
    label: str  # 显示的问题摘要
    visits: int
    value: float
    depth: int
    isPruned: bool
    isProcessing: bool
    factsCount: int
    question: Optional[str] = None  # 完整问题


class TreeEdge(BaseModel):
    """前端树边数据"""
    id: str
    source: str
    target: str


class TreeResponse(BaseModel):
    """前端树数据响应"""
    nodes: List[Dict]
    edges: List[Dict]