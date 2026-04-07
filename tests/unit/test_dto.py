from __future__ import annotations

from src.backend.api.dto import build_session_read_model
from src.backend.core.schema import Node, QAInteraction, SessionData


def _build_session() -> SessionData:
    session = SessionData(global_goal="DTO 报告可用性")
    session.add_node(
        Node(
            id=session.root_node_id,
            depth=0,
            interaction=QAInteraction(question="DTO 报告可用性", answer="探索起点"),
        )
    )
    session.session_version = 3
    return session


def test_build_session_read_model_uses_explicit_report_availability_flag():
    session = _build_session()

    model = build_session_read_model(
        session,
        is_active=True,
        report_available=False,
    )

    assert model.session_id == session.session_id
    assert model.is_active is True
    assert model.report_available is False
