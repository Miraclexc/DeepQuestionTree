from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from src.backend.core.mcts_engine import MCTSEngine
from src.backend.core.schema import Fact, Node, QAInteraction, SessionData


def build_settings(*, max_simulations: int = 4, branch_factor: int = 1):
    return SimpleNamespace(
        mcts=SimpleNamespace(
            exploration_constant=1.4,
            branch_factor=branch_factor,
            max_depth=5,
            max_simulations=max_simulations,
            save_interval_steps=1,
            parallel_workers=3,
        )
    )


def build_session_with_two_leaves() -> tuple[SessionData, str, str]:
    session = SessionData(global_goal="验证并发 MCTS")
    root = Node(
        id=session.root_node_id,
        depth=0,
        interaction=QAInteraction(
            question="验证并发 MCTS",
            answer="根节点已有答案",
            summary="root",
        ),
    )
    left = Node(
        parent_id=root.id,
        depth=1,
        interaction=QAInteraction(question="left?", answer="", summary=""),
    )
    right = Node(
        parent_id=root.id,
        depth=1,
        interaction=QAInteraction(question="right?", answer="", summary=""),
    )
    session.add_node(root)
    session.add_node(left)
    session.add_node(right)
    root.children_ids = [left.id, right.id]
    return session, left.id, right.id


@dataclass
class BarrierQuestioner:
    participants: int = 2

    def __post_init__(self) -> None:
        self._ready = asyncio.Event()
        self._arrivals = 0

    async def generate_candidates(
        self,
        *,
        context_facts,
        current_answer: str,
        goal: str,
        parent_question: str,
        k: int,
    ) -> list[str]:
        return [f"{parent_question} -> next"]

    async def evaluate_question_value(
        self,
        *,
        question: str,
        known_facts,
        goal: str,
        parent_question: str,
    ) -> float:
        return 1.0

    async def answer_question(
        self,
        *,
        question: str,
        context_facts,
        goal: str,
    ) -> tuple[str, int, str]:
        self._arrivals += 1
        if self._arrivals >= self.participants:
            self._ready.set()
        await self._ready.wait()
        return f"answer:{question}", 1, "fake-model"


class DeterministicCompressor:
    async def extract_facts(
        self,
        text: str,
        source_node_id: str,
    ) -> tuple[list[Fact], int, str]:
        return (
            [
                Fact(
                    content=f"fact:{source_node_id}",
                    source_node_id=source_node_id,
                    confidence=1.0,
                )
            ],
            1,
            "fake-model",
        )

    async def merge_facts(
        self,
        existing_facts: list[Fact],
        new_facts: list[Fact],
        similarity_threshold: float = 0.85,
    ) -> list[Fact]:
        del similarity_threshold
        merged = list(existing_facts)
        seen = {fact.content for fact in merged}
        for fact in new_facts:
            if fact.content not in seen:
                merged.append(fact)
                seen.add(fact.content)
        return merged


class NeverPrune:
    async def should_prune(
        self, node: Node, session: SessionData
    ) -> tuple[bool, str | None]:
        del node, session
        return False, None

    async def summarize_path(self, leaf_node: Node, session: SessionData) -> str:
        del leaf_node, session
        return "summary"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_commit_step_rejects_stale_proposal_and_clears_reservation():
    session, _, _ = build_session_with_two_leaves()
    engine = MCTSEngine(
        session=session,
        questioner=BarrierQuestioner(participants=2),
        compressor=DeterministicCompressor(),
        pruner=NeverPrune(),
        settings=build_settings(max_simulations=4),
    )

    snapshot_one = await engine.reserve_step()
    snapshot_two = await engine.reserve_step()

    assert snapshot_one is not None
    assert snapshot_two is not None

    proposal_one, proposal_two = await asyncio.gather(
        engine.prepare_step(snapshot_one),
        engine.prepare_step(snapshot_two),
    )

    result_one = await engine.commit_step(proposal_one)
    result_two = await engine.commit_step(proposal_two)

    assert result_one.committed is True
    assert result_two.committed is False
    assert result_two.reason == "stale_revision"

    stale_leaf = session.nodes[snapshot_two.leaf_node_id]
    assert stale_leaf.is_processing is False
    assert stale_leaf.processing_token is None
