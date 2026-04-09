"""
MCTS 核心引擎
实现蒙特卡洛树搜索的选择、扩展、模拟、回传播
"""

from __future__ import annotations

import asyncio
import inspect
import math
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from ..config_loader import get_settings
from ..llm.usage_tracking import LlmUsageRecorder, bind_usage_recorder
from ..utils.logger import get_logger
from .schema import Fact, Node, QAInteraction, SessionData, SessionLlmUsage

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SessionSnapshot:
    session_revision: int
    leaf_node_id: str
    reservation_token: str
    session: SessionData


@dataclass(slots=True)
class StepProposal:
    session_revision: int
    leaf_node_id: str
    reservation_token: str
    updated_nodes: dict[str, Node]
    created_nodes: list[Node]
    global_facts: list[Fact]
    llm_usage_delta: SessionLlmUsage
    new_node_id: str | None
    simulation_applied: bool


@dataclass(frozen=True, slots=True)
class CommitResult:
    committed: bool
    reason: str | None = None
    new_node_id: str | None = None


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
        settings=None,
        commit_lock: asyncio.Lock | None = None,
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
        self._commit_lock = commit_lock or asyncio.Lock()

        from ..llm.prompt_manager import get_prompt_manager

        self.prompts = prompt_manager or get_prompt_manager()

    async def run_step(self) -> Optional[str]:
        """
        执行一次完整的 MCTS 迭代：Reserve -> Prepare -> Commit

        Returns:
            Optional[str]: 扩展的新节点 ID，如果没有扩展则返回 None
        """
        snapshot: SessionSnapshot | None = None
        try:
            snapshot = await self.reserve_step()
            if snapshot is None:
                return None

            proposal = await self.prepare_step(snapshot)
            if proposal is None:
                await self.abort_step(snapshot)
                return None

            result = await self.commit_step(proposal)
            if not result.committed:
                return None

            return result.new_node_id
        except asyncio.CancelledError:
            if snapshot is not None:
                await self.abort_step(snapshot)
            raise
        except Exception as exc:
            logger.exception("MCTS 步骤执行失败: %s", exc)
            if snapshot is not None:
                await self.abort_step(snapshot)
            raise

    async def reserve_step(self) -> SessionSnapshot | None:
        """在串行提交通道内预占一个叶子节点，并构造只读快照。"""
        async with self._commit_lock:
            if (
                self.session.total_simulations + self.session.get_pending_reservations()
                >= self.settings.mcts.max_simulations
            ):
                return None

            leaf_node_id = self._select(self.session.root_node_id, session=self.session)
            if not leaf_node_id:
                return None

            leaf_node = self.session.nodes[leaf_node_id]
            if (
                leaf_node.is_processing
                or leaf_node.processing_token is not None
                or leaf_node.is_pruned
                or leaf_node.is_terminal
            ):
                return None

            reservation_token = str(uuid.uuid4())
            leaf_node.reserve_processing(reservation_token)
            snapshot_session = self.session.model_copy(deep=True)

            return SessionSnapshot(
                session_revision=self.session.session_revision,
                leaf_node_id=leaf_node_id,
                reservation_token=reservation_token,
                session=snapshot_session,
            )

    async def prepare_step(self, snapshot: SessionSnapshot) -> StepProposal | None:
        """基于快照执行所有慢操作，只产出待提交提案。"""
        session = snapshot.session
        leaf_node = session.nodes.get(snapshot.leaf_node_id)
        if leaf_node is None:
            return None
        recorder = LlmUsageRecorder()
        with bind_usage_recorder(recorder):
            if self.pruner:
                should_prune, reason = await self._should_prune(
                    leaf_node,
                    session,
                    phase="pre",
                )
                if should_prune:
                    prune_reason = reason or "未命名剪枝原因"
                    logger.info("Pruning node %s: %s", leaf_node.id, prune_reason)
                    await self._mark_pruned_node(session, leaf_node, prune_reason)
                    return self._build_proposal(
                        snapshot=snapshot,
                        session=session,
                        created_node_ids=[],
                        backprop_start_id=leaf_node.id,
                        value=0.0,
                        simulation_applied=False,
                        new_node_id=None,
                        llm_usage_delta=recorder.snapshot(),
                    )

            await self._process_node(session, leaf_node)

            if self.pruner:
                should_prune, reason = await self._should_prune(
                    leaf_node,
                    session,
                    phase="post",
                )
                if should_prune:
                    prune_reason = reason or "未命名剪枝原因"
                    logger.info("Pruning node %s: %s", leaf_node.id, prune_reason)
                    await self._mark_pruned_node(session, leaf_node, prune_reason)
                    return self._build_proposal(
                        snapshot=snapshot,
                        session=session,
                        created_node_ids=[],
                        backprop_start_id=leaf_node.id,
                        value=0.0,
                        simulation_applied=False,
                        new_node_id=None,
                        llm_usage_delta=recorder.snapshot(),
                    )

            if leaf_node.is_pruned or leaf_node.is_terminal:
                return self._build_proposal(
                    snapshot=snapshot,
                    session=session,
                    created_node_ids=[],
                    backprop_start_id=leaf_node.id,
                    value=0.0,
                    simulation_applied=False,
                    new_node_id=None,
                    llm_usage_delta=recorder.snapshot(),
                )

            new_node_ids = await self._expand(session, leaf_node)
            logger.info(
                "Expanded node %s, got %s children",
                leaf_node.id,
                len(new_node_ids),
            )

            if not new_node_ids:
                if len(leaf_node.children_ids) >= self.settings.mcts.branch_factor:
                    children = [
                        session.nodes[cid]
                        for cid in leaf_node.children_ids
                        if cid in session.nodes
                    ]
                    processing_children = [
                        child.id
                        for child in children
                        if child.is_processing and child.processing_token is not None
                    ]
                    if processing_children:
                        logger.info(
                            "Node %s has processing children: %s. Skipping.",
                            leaf_node.id,
                            processing_children,
                        )
                        return None

                    logger.info(
                        "Node %s fully expanded and all children pruned/exhausted. "
                        "Marking as terminal.",
                        leaf_node.id,
                    )
                    leaf_node.mark_terminal()
                    return self._build_proposal(
                        snapshot=snapshot,
                        session=session,
                        created_node_ids=[],
                        backprop_start_id=leaf_node.id,
                        value=0.0,
                        simulation_applied=False,
                        new_node_id=None,
                        llm_usage_delta=recorder.snapshot(),
                    )

                logger.error(
                    "Failed to generate children for %s (limit not reached). "
                    "Marking as terminal.",
                    leaf_node.id,
                )
                leaf_node.mark_terminal()
                return self._build_proposal(
                    snapshot=snapshot,
                    session=session,
                    created_node_ids=[],
                    backprop_start_id=leaf_node.id,
                    value=0.0,
                    simulation_applied=False,
                    new_node_id=None,
                    llm_usage_delta=recorder.snapshot(),
                )

            simulation_node_id = new_node_ids[0]
            value = await self._simulate_value(session, simulation_node_id)
            return self._build_proposal(
                snapshot=snapshot,
                session=session,
                created_node_ids=new_node_ids,
                backprop_start_id=simulation_node_id,
                value=value,
                simulation_applied=True,
                new_node_id=simulation_node_id,
                llm_usage_delta=recorder.snapshot(),
            )

    async def commit_step(self, proposal: StepProposal) -> CommitResult:
        """在串行提交通道内应用提案，不在锁内执行 await。"""
        async with self._commit_lock:
            live_leaf = self.session.nodes.get(proposal.leaf_node_id)
            if live_leaf is None:
                self.session.merge_llm_usage(proposal.llm_usage_delta, touch=False)
                return CommitResult(committed=False, reason="missing_leaf")

            if live_leaf.processing_token != proposal.reservation_token:
                self.session.merge_llm_usage(proposal.llm_usage_delta, touch=False)
                return CommitResult(committed=False, reason="reservation_lost")

            if self.session.session_revision != proposal.session_revision:
                live_leaf.release_processing(proposal.reservation_token)
                self.session.merge_llm_usage(proposal.llm_usage_delta, touch=False)
                return CommitResult(committed=False, reason="stale_revision")

            if (
                proposal.simulation_applied
                and self.session.total_simulations >= self.settings.mcts.max_simulations
            ):
                live_leaf.release_processing(proposal.reservation_token)
                self.session.merge_llm_usage(proposal.llm_usage_delta, touch=False)
                return CommitResult(
                    committed=False,
                    reason="simulation_budget_reached",
                )

            for node_id, prepared_node in proposal.updated_nodes.items():
                live_node = self.session.nodes.get(node_id)
                if live_node is None:
                    live_leaf.release_processing(proposal.reservation_token)
                    self.session.merge_llm_usage(proposal.llm_usage_delta, touch=False)
                    return CommitResult(committed=False, reason="missing_updated_node")
                self._apply_existing_node_update(
                    live_node=live_node,
                    prepared_node=prepared_node,
                )

            for created_node in proposal.created_nodes:
                self.session.nodes[created_node.id] = created_node.model_copy(deep=True)

            self.session.global_facts = [
                fact.model_copy(deep=True) for fact in proposal.global_facts
            ]
            self.session.merge_llm_usage(proposal.llm_usage_delta, touch=False)

            if proposal.simulation_applied:
                self.session.increment_simulations()

            self.session.bump_session_version()
            self.session.increment_revision()

            committed_leaf = self.session.nodes.get(proposal.leaf_node_id)
            if committed_leaf is not None:
                committed_leaf.release_processing(proposal.reservation_token)

            self.session.updated_at = datetime.now()
            return CommitResult(
                committed=True,
                new_node_id=proposal.new_node_id,
            )

    async def abort_step(self, snapshot: SessionSnapshot) -> None:
        """释放尚未提交的预占节点。"""
        async with self._commit_lock:
            live_leaf = self.session.nodes.get(snapshot.leaf_node_id)
            if live_leaf is not None:
                live_leaf.release_processing(snapshot.reservation_token)

    def _select(
        self,
        current_node_id: str,
        *,
        session: SessionData | None = None,
    ) -> Optional[str]:
        """选择叶子节点"""
        if session is None:
            session = self.session
        current_node = session.nodes[current_node_id]

        while current_node.children_ids:
            valid_children = [
                session.nodes[cid]
                for cid in current_node.children_ids
                if cid in session.nodes
                and not session.nodes[cid].is_pruned
                and not session.nodes[cid].is_processing
            ]

            if not valid_children:
                return current_node_id

            parent_visits = max(1, current_node.state.visit_count)
            best_child = max(
                valid_children,
                key=lambda node: node.uct_value(parent_visits, self.c_param),
            )
            current_node_id = best_child.id
            current_node = best_child

        return current_node_id

    async def _expand(self, session: SessionData, parent_node: Node) -> List[str]:
        """
        扩展父节点，生成新的子节点
        """
        if not self.questioner:
            logger.warning("Questioner 模块未初始化")
            return []

        current_answer = ""
        parent_question = "初始探索目标"
        if parent_node.interaction:
            current_answer = parent_node.interaction.answer
            parent_question = parent_node.interaction.question

        if len(parent_node.children_ids) >= self.settings.mcts.branch_factor:
            logger.info(
                "Node %s already has %s children (limit %s). Skipping expansion.",
                parent_node.id,
                len(parent_node.children_ids),
                self.settings.mcts.branch_factor,
            )
            return []

        path_facts = self._get_path_facts(session, parent_node)
        questions = await self.questioner.generate_candidates(
            context_facts=path_facts,
            current_answer=current_answer,
            goal=session.global_goal,
            parent_question=parent_question,
            k=self.settings.mcts.branch_factor,
        )

        normalized_history = {
            self._normalize_question_text(node.interaction.question)
            for node in session.nodes.values()
            if node.interaction and node.interaction.question
        }
        seen_candidates: set[str] = set()
        new_ids: list[str] = []
        for question_text in questions:
            normalized_question = self._normalize_question_text(question_text)
            if not normalized_question:
                continue
            if (
                normalized_question in normalized_history
                or normalized_question in seen_candidates
            ):
                logger.info(
                    "Skipping duplicate candidate before node creation: %s",
                    question_text,
                )
                continue

            candidate_node = Node(
                parent_id=parent_node.id,
                depth=parent_node.depth + 1,
                prune_reason=None,
                interaction=QAInteraction(
                    question=question_text.strip(),
                    answer="",
                    summary="",
                    model_used=None,
                ),
            )
            if self.pruner:
                should_prune, reason = await self._should_prune(
                    candidate_node,
                    session,
                    phase="pre",
                )
                if should_prune:
                    logger.info(
                        "Rejected candidate before node creation: %s (%s)",
                        question_text,
                        reason or "未命名原因",
                    )
                    continue

            seen_candidates.add(normalized_question)
            new_node = Node(
                id=candidate_node.id,
                parent_id=candidate_node.parent_id,
                depth=candidate_node.depth,
                prune_reason=None,
                interaction=(
                    candidate_node.interaction.model_copy(deep=True)
                    if candidate_node.interaction is not None
                    else None
                ),
            )
            session.add_node(new_node)
            parent_node.add_child(new_node.id)
            new_ids.append(new_node.id)

        return new_ids

    async def _simulate_value(self, session: SessionData, node_id: str) -> float:
        """启发式评估"""
        node = session.nodes[node_id]
        question = node.interaction.question if node.interaction else ""

        if not self.questioner:
            return 5.0

        parent_question = "初始探索"
        if node.parent_id and node.parent_id in session.nodes:
            parent_node = session.nodes[node.parent_id]
            if parent_node.interaction:
                parent_question = parent_node.interaction.question

        score = await self.questioner.evaluate_question_value(
            question=question,
            known_facts=session.global_facts,
            goal=session.global_goal,
            parent_question=parent_question,
        )
        return score

    def _backpropagate(
        self,
        node_id: str,
        value: float,
        *,
        session: SessionData | None = None,
    ) -> None:
        """回传播价值"""
        if session is None:
            session = self.session
        current_id: str | None = node_id
        while current_id:
            node = session.nodes[current_id]
            node.state.visit_count += 1
            node.state.value_sum += value
            node.updated_at = datetime.now()
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
            key=lambda child_id: self.session.nodes[child_id].state.visit_count,
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

    async def _process_node(self, session: SessionData, node: Node) -> None:
        """
        处理节点：如果节点没有回答，生成回答并提取事实
        """
        if (
            node.interaction
            and node.interaction.answer
            and node.interaction.answer != "探索起点"
        ):
            return

        if not self.questioner or not self.compressor:
            logger.warning("Questioner or Compressor not initialized")
            return

        interaction = node.interaction
        if interaction is None:
            logger.warning(
                "Node %s has no interaction payload; skipping processing.",
                node.id,
            )
            return

        question = interaction.question
        answer, tokens, model = await self.questioner.answer_question(
            question=question,
            context_facts=session.global_facts,
            goal=session.global_goal,
        )

        interaction.answer = answer
        interaction.tokens_used = tokens
        interaction.model_used = model

        new_facts, extract_tokens, _ = await self.compressor.extract_facts(
            answer, node.id
        )
        node.new_facts = new_facts
        interaction.tokens_used += extract_tokens
        session.global_facts = await self.compressor.merge_facts(
            session.global_facts,
            new_facts,
        )
        node.touch(bump_revision=True)

        logger.info(
            "Processed node %s: Generated answer and %s facts (Total Tokens: %s)",
            node.id,
            len(new_facts),
            interaction.tokens_used,
        )

    def get_tree_statistics(self) -> Dict[str, float | int]:
        """
        获取树的统计信息

        Returns:
            Dict: 统计信息字典
        """
        stats: dict[str, float | int] = {
            "total_nodes": self.session.get_total_nodes(),
            "total_simulations": self.session.total_simulations,
            "tree_depth": self.session.get_tree_depth(),
            "active_nodes": len(self.session.get_active_nodes()),
            "pruned_nodes": sum(
                1 for node in self.session.nodes.values() if node.is_pruned
            ),
            "terminal_nodes": sum(
                1 for node in self.session.nodes.values() if node.is_terminal
            ),
            "total_facts": len(self.session.global_facts),
        }

        if stats["total_nodes"] > 0:
            total_visits = sum(
                node.state.visit_count for node in self.session.nodes.values()
            )
            stats["average_visits"] = total_visits / stats["total_nodes"]
        else:
            stats["average_visits"] = 0

        return stats

    def _get_path_facts(self, session: SessionData, node: Node) -> List[Fact]:
        """
        获取从根节点到当前节点路径上的所有事实
        """
        facts: list[Fact] = []
        current: Node | None = node
        while current:
            facts.extend(current.new_facts)

            if current.parent_id and current.parent_id in session.nodes:
                current = session.nodes[current.parent_id]
            else:
                current = None

        unique_facts = {fact.id: fact for fact in facts}
        return list(unique_facts.values())

    def _build_proposal(
        self,
        *,
        snapshot: SessionSnapshot,
        session: SessionData,
        created_node_ids: list[str],
        backprop_start_id: str,
        value: float,
        simulation_applied: bool,
        new_node_id: str | None,
        llm_usage_delta: SessionLlmUsage,
    ) -> StepProposal:
        self._backpropagate(
            backprop_start_id,
            value,
            session=session,
        )

        created_ids = set(created_node_ids)
        updated_node_ids = [
            node_id
            for node_id in self._get_path_node_ids(session, backprop_start_id)
            if node_id not in created_ids
        ]

        updated_nodes = {
            node_id: session.nodes[node_id].model_copy(deep=True)
            for node_id in updated_node_ids
        }
        created_nodes = [
            session.nodes[node_id].model_copy(deep=True) for node_id in created_node_ids
        ]

        return StepProposal(
            session_revision=snapshot.session_revision,
            leaf_node_id=snapshot.leaf_node_id,
            reservation_token=snapshot.reservation_token,
            updated_nodes=updated_nodes,
            created_nodes=created_nodes,
            global_facts=[fact.model_copy(deep=True) for fact in session.global_facts],
            llm_usage_delta=llm_usage_delta.model_copy(deep=True),
            new_node_id=new_node_id,
            simulation_applied=simulation_applied,
        )

    def _get_path_node_ids(self, session: SessionData, node_id: str) -> list[str]:
        """获取从当前节点到根节点的所有节点 ID。"""
        path: list[str] = []
        current_id: str | None = node_id
        while current_id:
            path.append(current_id)
            current_node = session.nodes.get(current_id)
            if current_node is None:
                break
            current_id = current_node.parent_id
        return path

    def _apply_existing_node_update(
        self,
        *,
        live_node: Node,
        prepared_node: Node,
    ) -> None:
        """将快照里的已存在节点状态复制到活动会话，保留实时 reservation 元数据。"""
        live_node.children_ids = list(prepared_node.children_ids)
        live_node.depth = prepared_node.depth
        live_node.parent_id = prepared_node.parent_id
        live_node.interaction = (
            prepared_node.interaction.model_copy(deep=True)
            if prepared_node.interaction is not None
            else None
        )
        live_node.new_facts = [
            fact.model_copy(deep=True) for fact in prepared_node.new_facts
        ]
        live_node.state.visit_count = prepared_node.state.visit_count
        live_node.state.value_sum = prepared_node.state.value_sum
        live_node.is_terminal = prepared_node.is_terminal
        live_node.is_pruned = prepared_node.is_pruned
        live_node.prune_reason = prepared_node.prune_reason
        live_node.node_revision = prepared_node.node_revision
        live_node.created_at = prepared_node.created_at
        live_node.updated_at = prepared_node.updated_at

    async def _should_prune(
        self,
        node: Node,
        session: SessionData,
        *,
        phase: str,
    ) -> tuple[bool, str | None]:
        if self.pruner is None:
            return False, None

        should_prune = self.pruner.should_prune
        has_phase = False
        try:
            has_phase = "phase" in inspect.signature(should_prune).parameters
        except (TypeError, ValueError):
            has_phase = False

        if has_phase:
            return await should_prune(node, session, phase=phase)
        return await should_prune(node, session)

    def _normalize_question_text(self, question: str) -> str:
        normalized = question.strip()
        checker = getattr(self.pruner, "checker", None)
        if checker is None:
            checker = getattr(self.questioner, "checker", None)
        if checker is not None and hasattr(checker, "normalize_text"):
            return checker.normalize_text(normalized)
        return " ".join(normalized.lower().split())

    async def _mark_pruned_node(
        self,
        session: SessionData,
        node: Node,
        reason: str,
    ) -> None:
        node.mark_pruned(reason)
        if (
            node.interaction is None
            or self.pruner is None
            or not hasattr(self.pruner, "summarize_path")
            or node.interaction.summary
            or not node.interaction.answer
            or node.interaction.answer == "探索起点"
        ):
            return

        try:
            node.interaction.summary = await self.pruner.summarize_path(node, session)
        except Exception as exc:  # pragma: no cover - 降级摘要路径
            logger.warning("Failed to summarize pruned node %s: %s", node.id, exc)
            node.interaction.summary = (
                node.interaction.answer[:120] if node.interaction.answer else reason
            )
        node.touch(bump_revision=True)
