from __future__ import annotations

from typing import Any

from .schema import Fact, Node, SessionData


def get_path_facts(session: SessionData, node: Node) -> list[Fact]:
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


def get_path_node_ids(session: SessionData, node_id: str) -> list[str]:
    path: list[str] = []
    current_id: str | None = node_id
    while current_id:
        path.append(current_id)
        current_node = session.nodes.get(current_id)
        if current_node is None:
            break
        current_id = current_node.parent_id
    return path


def normalize_question_text(question: str, normalizer: Any = None) -> str:
    normalized = question.strip()
    if normalizer is not None and hasattr(normalizer, "normalize_text"):
        return normalizer.normalize_text(normalized)
    return " ".join(normalized.lower().split())
