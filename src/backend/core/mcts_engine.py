"""
MCTS 核心引擎
实现蒙特卡洛树搜索的选择、扩展、模拟、回传播
"""
import math
import random
from typing import Dict, List, Optional

from .schema import Node, SessionData, Fact
from ..config_loader import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class MCTSEngine:
    """
    MCTS 引擎核心类
    负责执行 MCTS 的四个步骤：Selection, Expansion, Simulation, Backpropagation
    """

    def __init__(
        self, 
        session: SessionData, 
        questioner=None, 
        pruner=None,
        compressor=None,
        prompt_manager=None,
        settings=None
    ):
        """
        初始化 MCTS 引擎

        Args:
            session: 会话数据
            questioner: 提问模块实例
            pruner: 剪枝模块实例
        """
        self.session = session
        self.questioner = questioner
        self.pruner = pruner
        self.compressor = compressor
        self.settings = settings or get_settings()
        self.c_param = self.settings.mcts.exploration_constant
        
        # 初始化 Prompt 管理器
        from ..llm.prompt_manager import get_prompt_manager
        self.prompts = prompt_manager or get_prompt_manager()

    async def run_step(self) -> Optional[str]:
        """
        执行一次完整的 MCTS 迭代：Select -> Expand -> Simulate -> Backpropagate

        Returns:
            Optional[str]: 扩展的新节点 ID，如果没有扩展则返回 None
        """
        try:
            # 1. Selection: 使用 UCT 策略选择叶子节点
            leaf_node_id = self._select(self.session.root_node_id)
            if not leaf_node_id:
                return None
                
            leaf_node = self.session.nodes[leaf_node_id]

            # 如果节点正在处理中（并行冲突），跳过
            if leaf_node.is_processing:
                return None

            # 标记为处理中
            leaf_node.is_processing = True
            
            try:
                # --- 新增步骤：确保选中的节点有回答 ---
                # 如果没有回答，先生成回答，以便后续扩展有上下文
                await self._process_node(leaf_node)
    
                # --- 新增步骤：剪枝检查 ---
                if self.pruner:
                    should_prune, reason = await self.pruner.should_prune(leaf_node, self.session)
                    if should_prune:
                        logger.info(f"Pruning node {leaf_node.id}: {reason}")
                        
                        # 标记为已剪枝
                        leaf_node.mark_pruned(reason)
                        
                        # 生成被剪枝路径的摘要
                        summary = await self.pruner.summarize_path(leaf_node, self.session)
                        if leaf_node.interaction:
                            leaf_node.interaction.summary = summary
                        
                        # 回传播负值（惩罚）
                        self._backpropagate(leaf_node_id, value=0.0)
                        return None
    
                # 如果节点已被剪枝或终结，回传播负值
                if leaf_node.is_pruned or leaf_node.is_terminal:
                    self._backpropagate(leaf_node_id, value=0.0)
                    return None
    
                # 2. Expansion: 扩展新节点
                new_node_ids = await self._expand(leaf_node)
                logger.info(f"Expanded node {leaf_node.id}, got {len(new_node_ids)} children")

                # 如果返回空列表，可能是以下情况：
                # 1. 达到分支限制（Internal Node，但子节点都在忙）-> 跳过，不标记为 Terminal
                # 2. 生成失败 -> 标记为 Terminal
                if not new_node_ids:
                    # 检查是否因为已有子节点（分支限制）
                    if len(leaf_node.children_ids) >= self.settings.mcts.branch_factor:
                        # 这是一个内部节点，可能因为子节点都 busy 或 pruned 而被选中
                        
                        # Check if any children are just busy processing
                        children = [self.session.nodes[cid] for cid in leaf_node.children_ids if cid in self.session.nodes]
                        processing_children = [c.id for c in children if c.is_processing]
                        if processing_children:
                            logger.info(f"Node {leaf_node.id} has processing children: {processing_children}. Skipping.")
                            # Just skip this turn if children are busy
                            return None

                        # 如果所有子节点都被剪枝（且没有 processing），那么这个节点也应该被视为死胡同
                        # 标记为 terminal，防止后续再次被 select 选中
                        logger.info(f"Node {leaf_node.id} fully expanded and all children pruned/exhausted. Marking as terminal.")
                        leaf_node.is_terminal = True
                        self._backpropagate(leaf_node_id, value=0.0)
                        return None
                    
                    # 真正无法生成（失败），标记为终结
                    logger.error(f"Failed to generate children for {leaf_node.id} (limit not reached). Marking as terminal.")
                    leaf_node.is_terminal = True
                    self._backpropagate(leaf_node_id, value=0.0)
                    return None
    
                # 3. Simulation: 对第一个新节点进行启发式评估
                simulation_node_id = new_node_ids[0]
                value = await self._simulate_value(simulation_node_id)
    
                # 4. Backpropagation: 回传播价值
                self._backpropagate(simulation_node_id, value)
    
                # 增加总模拟次数
                self.session.increment_simulations()
    
                return simulation_node_id

            finally:
                # 无论成功失败，释放处理状态
                leaf_node.is_processing = False
    
        except Exception as e:
            logger.error(f"MCTS 步骤执行失败: {e}")
            if 'leaf_node' in locals():
                leaf_node.is_processing = False
            return None

    def _select(self, current_node_id: str) -> Optional[str]:
        """选择叶子节点"""
        current_node = self.session.nodes[current_node_id]
        
        while current_node.children_ids:
            # 过滤掉已剪枝 AND 正在处理的子节点
            valid_children = [
                self.session.nodes[cid] for cid in current_node.children_ids
                if cid in self.session.nodes 
                and not self.session.nodes[cid].is_pruned
                and not self.session.nodes[cid].is_processing
            ]
            
            if not valid_children:
                # 如果所有子节点都不可用（剪枝或忙），返回当前节点
                # 外层逻辑需判断是 Expand 还是 Skip
                return current_node_id
            
            parent_visits = max(1, current_node.state.visit_count)
            best_child = max(
                valid_children,
                key=lambda n: n.uct_value(parent_visits, self.c_param)
            )
            current_node_id = best_child.id
            current_node = best_child
            
        return current_node_id

    async def _expand(self, parent_node: Node) -> List[str]:
        """
        扩展父节点，生成新的子节点
        """
        if not self.questioner:
            logger.warning("Questioner 模块未初始化")
            return []

        # 获取上下文（取父节点的回答）
        current_answer = ""
        parent_question = "初始探索目标"
        if parent_node.interaction:
            current_answer = parent_node.interaction.answer
            parent_question = parent_node.interaction.question

        # 检查是否已达到分支因子限制
        # 如果节点已扩展过（已有子节点），不再扩展，直接视为终结或死路（如果所有子节点都被剪枝）
        if len(parent_node.children_ids) >= self.settings.mcts.branch_factor:
            logger.info(f"Node {parent_node.id} already has {len(parent_node.children_ids)} children (limit {self.settings.mcts.branch_factor}). Skipping expansion.")
            return []

        # 生成 k 个候选问题
        # 使用当前路径上的事实作为上下文，而不是全局事实
        # 这样能保证问题是基于当前推理链条产生的
        path_facts = self._get_path_facts(parent_node)
        
        questions = await self.questioner.generate_candidates(
            context_facts=path_facts,
            current_answer=current_answer,
            goal=self.session.global_goal,
            parent_question=parent_question,
            k=self.settings.mcts.branch_factor
        )
        
        new_ids = []
        for q_text in questions:
            # 创建新节点
            from .schema import QAInteraction
            new_node = Node(
                parent_id=parent_node.id,
                depth=parent_node.depth + 1,
                interaction=QAInteraction(
                    question=q_text, 
                    answer="", # 暂无回答，等待 Process 阶段生成
                    summary=""
                )
            )
            # 添加到会话
            self.session.add_node(new_node)
            parent_node.add_child(new_node.id)
            new_ids.append(new_node.id)
            
        return new_ids

    async def _simulate_value(self, node_id: str) -> float:
        """启发式评估"""
        node = self.session.nodes[node_id]
        question = node.interaction.question if node.interaction else ""
        
        if not self.questioner:
            return 5.0
            
        # 获取父节点问题作为上下文
        parent_question = "初始探索"
        if node.parent_id and node.parent_id in self.session.nodes:
            parent_node = self.session.nodes[node.parent_id]
            if parent_node.interaction:
                parent_question = parent_node.interaction.question

        score = await self.questioner.evaluate_question_value(
            question=question,
            known_facts=self.session.global_facts,
            goal=self.session.global_goal,
            parent_question=parent_question
        )
        return score

    def _backpropagate(self, node_id: str, value: float) -> None:
        """回传播价值"""
        current_id = node_id
        while current_id:
            node = self.session.nodes[current_id]
            node.state.visit_count += 1
            node.state.value_sum += value
            current_id = node.parent_id

    def get_best_child(self, node_id: Optional[str] = None) -> Optional[Node]:
        """获取访问次数最多的子节点"""
        if node_id is None:
            node_id = self.session.root_node_id
        if node_id not in self.session.nodes:
            return None
        parent_node = self.session.nodes[node_id]
        if not parent_node.children_ids:
            return None
        best_child_id = max(
            parent_node.children_ids,
            key=lambda cid: self.session.nodes[cid].state.visit_count
        )
        return self.session.nodes[best_child_id]

    def should_stop(self) -> bool:
        """判断是否应该停止 MCTS"""
        if self.session.total_simulations >= self.settings.mcts.max_simulations:
            logger.info("达到最大模拟次数，停止 MCTS")
            return True

        if self.session.get_tree_depth() >= self.settings.mcts.max_depth:
            logger.info("达到最大深度，停止 MCTS")
            return True

        active_nodes = self.session.get_active_nodes()
        if not active_nodes:
            logger.info("没有活跃节点，停止 MCTS")
            return True

        return False

    async def _process_node(self, node: Node) -> None:
        """
        处理节点：如果节点没有回答，生成回答并提取事实
        """
        # 如果已有回答且不是初始占位符，跳过
        if node.interaction and node.interaction.answer and node.interaction.answer != "探索起点":
            return

        # 根节点通常已有回答，但也可能没有（取决于初始化方式）
        # 这里主要针对新扩展的节点

        if not self.questioner or not self.compressor:
            logger.warning("Questioner or Compressor not initialized")
            return

        try:
            # 1. Generate Answer (Using Questioner)
            question = node.interaction.question
            
            # 使用 Questioner 回答问题并获取统计信息
            answer, tokens, model = await self.questioner.answer_question(
                question=question,
                context_facts=self.session.global_facts,
                goal=self.session.global_goal
            )
            
            node.interaction.answer = answer
            node.interaction.tokens_used = tokens
            node.interaction.model_used = model
            
            # 2. Extract Facts
            new_facts, extract_tokens, _ = await self.compressor.extract_facts(answer, node.id)
            node.new_facts = new_facts
            
            # 累加 Token 消耗
            node.interaction.tokens_used += extract_tokens
            
            # 3. Update Global Facts
            self.session.global_facts = await self.compressor.merge_facts(
                self.session.global_facts,
                new_facts
            )
            
            logger.info(f"Processed node {node.id}: Generated answer and {len(new_facts)} facts (Total Tokens: {node.interaction.tokens_used})")
            
        except Exception as e:
            logger.error(f"Failed to process node {node.id}: {e}")
            node.interaction.answer = "Error generating answer."

    def get_tree_statistics(self) -> Dict:
        """
        获取树的统计信息

        Returns:
            Dict: 统计信息字典
        """
        stats = {
            "total_nodes": self.session.get_total_nodes(),
            "total_simulations": self.session.total_simulations,
            "tree_depth": self.session.get_tree_depth(),
            "active_nodes": len(self.session.get_active_nodes()),
            "pruned_nodes": sum(1 for n in self.session.nodes.values() if n.is_pruned),
            "terminal_nodes": sum(1 for n in self.session.nodes.values() if n.is_terminal),
            "total_facts": len(self.session.global_facts)
        }

        # 计算平均访问次数
        if stats["total_nodes"] > 0:
            total_visits = sum(n.state.visit_count for n in self.session.nodes.values())
            stats["average_visits"] = total_visits / stats["total_nodes"]
        else:
            stats["average_visits"] = 0

        return stats

    def _get_path_facts(self, node: Node) -> List[Fact]:
        """
        获取从根节点到当前节点路径上的所有事实
        """
        facts = []
        current = node
        while current:
            # 将当前节点的事实添加到列表开头（保持时间顺序，如果需要的话可以反转）
            # 这里我们直接extend，因为我们要收集的是集合
            facts.extend(current.new_facts)
            
            if current.parent_id and current.parent_id in self.session.nodes:
                current = self.session.nodes[current.parent_id]
            else:
                current = None
        
        # 可选：去重
        # 由于 Fact 有唯一 ID，可以去重
        unique_facts = {f.id: f for f in facts}
        return list(unique_facts.values())