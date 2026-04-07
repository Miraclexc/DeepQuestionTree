from __future__ import annotations

import asyncio

import pytest

from src.backend.core.mcts_engine import MCTSEngine
from src.backend.core.schema import Fact, Node, QAInteraction, SessionData
from tests.unit.test_mcts_concurrency import (
    BarrierQuestioner,
    DeterministicCompressor,
    NeverPrune,
    build_session_with_two_leaves,
    build_settings,
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_run_steps_preserve_fact_union_after_retry():
    session, left_id, right_id = build_session_with_two_leaves()
    engine = MCTSEngine(
        session=session,
        questioner=BarrierQuestioner(participants=2),
        compressor=DeterministicCompressor(),
        pruner=NeverPrune(),
        settings=build_settings(max_simulations=2),
    )

    await asyncio.gather(engine.run_step(), engine.run_step())
    assert session.total_simulations == 1

    await engine.run_step()

    assert session.total_simulations == 2
    assert {fact.content for fact in session.global_facts} == {
        f"fact:{left_id}",
        f"fact:{right_id}",
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_parallel_reservations_do_not_exceed_simulation_budget():
    session, _, _ = build_session_with_two_leaves()
    engine = MCTSEngine(
        session=session,
        questioner=BarrierQuestioner(participants=1),
        compressor=DeterministicCompressor(),
        pruner=NeverPrune(),
        settings=build_settings(max_simulations=1),
    )

    await asyncio.gather(engine.run_step(), engine.run_step(), engine.run_step())

    assert session.total_simulations == 1
    assert all(node.processing_token is None for node in session.nodes.values())
    assert all(node.is_processing is False for node in session.nodes.values())
