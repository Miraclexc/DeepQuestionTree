from __future__ import annotations

from dataclasses import dataclass

from .schema import Fact, Node, SessionData, SessionLlmUsage


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
