from src.backend.core.schema import Fact, Node, SessionData
from src.backend.core.tree_utils import (
    get_path_facts,
    get_path_node_ids,
    normalize_question_text,
)


def test_get_path_node_ids_walks_from_leaf_to_root():
    session = SessionData(global_goal="goal")
    root = Node(id=session.root_node_id, depth=0)
    child = Node(id="child", parent_id=root.id, depth=1)
    leaf = Node(id="leaf", parent_id=child.id, depth=2)
    session.nodes = {root.id: root, child.id: child, leaf.id: leaf}

    assert get_path_node_ids(session, leaf.id) == ["leaf", "child", root.id]


def test_get_path_facts_deduplicates_by_fact_id():
    session = SessionData(global_goal="goal")
    root = Node(id=session.root_node_id, depth=0)
    child = Node(id="child", parent_id=root.id, depth=1)
    duplicate_fact = Fact(id="fact-1", content="fact", source_node_id=root.id)
    root.new_facts = [duplicate_fact]
    child.new_facts = [
        Fact(id="fact-1", content="newer fact", source_node_id=child.id),
        Fact(id="fact-2", content="second fact", source_node_id=child.id),
    ]
    session.nodes = {root.id: root, child.id: child}

    assert [fact.id for fact in get_path_facts(session, child)] == [
        "fact-1",
        "fact-2",
    ]


def test_normalize_question_text_uses_optional_normalizer():
    class Normalizer:
        def normalize_text(self, value: str) -> str:
            return f"normalized:{value}"

    assert normalize_question_text("  Mixed   CASE  ") == "mixed case"
    assert normalize_question_text("  Mixed   CASE  ", Normalizer()) == (
        "normalized:Mixed   CASE"
    )
