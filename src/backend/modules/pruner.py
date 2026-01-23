"""
剪枝模块
负责判断是否剪枝路径，生成路径摘要
"""
from typing import List, Dict, Any, Optional

from ..core.schema import Node, SessionData, QAInteraction
from ..llm.client_interface import BaseLLMClient
from ..llm.prompt_manager import get_prompt_manager
from ..llm.embedding import get_embedding_manager
from ..config_loader import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class Pruner:
    """
    剪枝器模块
    负责路径剪枝决策和生成摘要
    """

    def __init__(
        self,
        llm_client: BaseLLMClient,
        embedding_manager=None,
        prompt_manager=None
    ):
        """
        初始化剪枝器

        Args:
            llm_client: LLM 客户端
            embedding_manager: 嵌入管理器
            prompt_manager: Prompt 管理器
        """
        self.llm = llm_client
        self.embedding = embedding_manager or get_embedding_manager()
        self.prompts = prompt_manager or get_prompt_manager()
        self.settings = get_settings()

    async def should_prune(
        self,
        node: Node,
        session: SessionData
    ) -> tuple[bool, Optional[str]]:
        """
        判断节点是否应该被剪枝

        Args:
            node: 待判断的节点
            session: 会话数据

        Returns:
            tuple[bool, Optional[str]]: (是否剪枝, 剪枝原因)
        """
        # 1. 检查深度限制
        if node.depth >= self.settings.mcts.max_depth:
            return True, f"达到最大深度限制 ({self.settings.mcts.max_depth})"

        # 2. 检查是否为重复问题
        if node.interaction and node.interaction.question:
            # 获取历史问题
            history_questions = self._get_history_questions(session, node.id)
            is_duplicate = await self.embedding.check_duplicate(
                node.interaction.question,
                history_questions,
                threshold=self.settings.embedding.similarity_threshold
            )

            if is_duplicate:
                return True, "问题重复"

        # 3. 检查连续低价值
        if await self._is_low_value_path(node, session):
            return True, "连续低价值路径"

        # 4. 检查是否偏离目标
        if await self._is_off_topic(node, session):
            return True, "偏离主题"

        # 5. 检查是否已有足够信息
        if len(session.global_facts) >= 50:  # 可配置的阈值
            return True, "已有足够信息"

        return False, None

    async def summarize_path(
        self,
        leaf_node: Node,
        session: SessionData
    ) -> str:
        """
        生成路径摘要

        Args:
            leaf_node: 路径的叶子节点
            session: 会话数据

        Returns:
            str: 路径摘要
        """
        try:
            # 获取路径上的所有节点
            path_nodes = self._get_path_to_root(leaf_node, session)

            # 提取关键问答
            path_qas = []
            for node in path_nodes:
                if node.interaction:
                    qa = {
                        "question": node.interaction.question,
                        "answer": node.interaction.summary or node.interaction.answer[:100] + "..."
                    }
                    path_qas.append(qa)

            # 准备 QA 文本
            qa_text = "\n\n".join([
                f"Q: {qa['question']}\nA: {qa['answer']}"
                for qa in path_qas[-5:]  # 只考虑最近5个问答
            ])

            # 渲染摘要 Prompt
            context_note = ""
            if leaf_node.is_pruned:
                context_note = f"\n注意：该路径已被剪枝，原因是：{leaf_node.prune_reason}。请在摘要中简要说明为何该方向不再继续。"

            # 使用集中管理的 Prompt
            prompt = self.prompts.render(
                "summarize_pruned_path",
                qa_text=qa_text,
                context_note=context_note
            )
            # 调用 LLM 生成摘要
            messages = [{"role": "user", "content": prompt}]
            summary = await self.llm.chat_completion(
                messages=messages,
                temperature=0.3 # 降低温度以获得更稳定的概括
            )

            return summary.content.strip()

        except Exception as e:
            logger.error(f"生成路径摘要失败: {e}")
            # 降级处理：返回简单的总结
            return f"该路径包含 {len(path_nodes)} 个节点，探索了 {leaf_node.depth} 层深度"

    async def _is_low_value_path(
        self,
        node: Node,
        session: SessionData
    ) -> bool:
        """
        检查是否为低价值路径
        """
        # 获取路径上的节点
        path_nodes = self._get_path_to_root(node, session)

        # 检查最近 N 个节点的平均价值
        recent_nodes = path_nodes[-3:]  # 最近3个节点
        if len(recent_nodes) < 3:
            return False

        avg_value = sum(n.state.average_value for n in recent_nodes) / len(recent_nodes)

        # 如果平均价值低于阈值，认为是低价值路径
        return avg_value < 2.0  # 可配置的阈值

    async def _is_off_topic(
        self,
        node: Node,
        session: SessionData
    ) -> bool:
        """
        检查是否偏离主题
        """
        if not node.interaction or not session.global_goal:
            return False

        # 计算问题与目标的相似度
        similarity = self.embedding.cosine_similarity(
            await self.embedding.get_embedding(node.interaction.question),
            await self.embedding.get_embedding(session.global_goal)
        )

        # 如果相似度太低，认为偏离主题
        return similarity < 0.2  # 可配置的阈值

    def _get_history_questions(
        self,
        session: SessionData,
        exclude_node_id: str
    ) -> List[str]:
        """
        获取历史问题列表（排除指定节点）
        """
        questions = []
        for node_id, node in session.nodes.items():
            if node_id != exclude_node_id and node.interaction:
                questions.append(node.interaction.question)
        return questions

    def _get_path_to_root(
        self,
        node: Node,
        session: SessionData
    ) -> List[Node]:
        """
        获取从节点到根节点的路径
        """
        path = []
        current_node = node

        while current_node:
            path.append(current_node)
            if current_node.parent_id:
                current_node = session.nodes.get(current_node.parent_id)
                if not current_node:
                    break
            else:
                break

        return list(reversed(path))  # 从根节点到当前节点

    def prune_subtree(
        self,
        root_node_id: str,
        reason: str,
        session: SessionData
    ) -> int:
        """
        剪枝子树

        Args:
            root_node_id: 子树根节点 ID
            reason: 剪枝原因
            session: 会话数据

        Returns:
            int: 剪枝的节点数量
        """
        if root_node_id not in session.nodes:
            return 0

        pruned_count = 0
        nodes_to_prune = [root_node_id]

        # 收集所有需要剪枝的节点
        i = 0
        while i < len(nodes_to_prune):
            node_id = nodes_to_prune[i]
            node = session.nodes.get(node_id)

            if node:
                nodes_to_prune.extend(node.children_ids)
            i += 1

        # 执行剪枝
        for node_id in nodes_to_prune:
            node = session.nodes.get(node_id)
            if node and not node.is_pruned:
                node.mark_pruned(reason)
                pruned_count += 1

        logger.info(f"剪枝子树 {root_node_id}，共剪枝 {pruned_count} 个节点，原因：{reason}")

        return pruned_count

    def get_pruning_statistics(self, session: SessionData) -> Dict[str, Any]:
        """
        获取剪枝统计信息

        Args:
            session: 会话数据

        Returns:
            Dict: 剪枝统计信息
        """
        total_nodes = len(session.nodes)
        pruned_nodes = sum(1 for n in session.nodes.values() if n.is_pruned)

        # 统计剪枝原因
        prune_reasons = {}
        for node in session.nodes.values():
            if node.is_pruned and node.prune_reason:
                prune_reasons[node.prune_reason] = prune_reasons.get(node.prune_reason, 0) + 1

        stats = {
            "total_nodes": total_nodes,
            "pruned_nodes": pruned_nodes,
            "pruned_percentage": (pruned_nodes / total_nodes * 100) if total_nodes > 0 else 0,
            "active_nodes": total_nodes - pruned_nodes,
            "prune_reasons": prune_reasons
        }

        return stats