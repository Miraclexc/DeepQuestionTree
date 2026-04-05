import pytest

from src.backend.core.schema import Node, QAInteraction
from src.backend.llm.mock_client import MockClient
from src.backend.modules.integrator import Integrator


@pytest.mark.unit
class TestIntegrator:
    def test_analyze_path_uses_goal_for_root_milestone(self):
        integrator = Integrator(MockClient())
        path = [
            Node(
                depth=0,
                interaction=QAInteraction(question="根问题", answer="探索起点"),
            ),
            Node(
                depth=1,
                interaction=QAInteraction(question="后续问题", answer="后续回答"),
                is_terminal=True,
            ),
        ]

        analysis = integrator._analyze_path(path, goal="测试总目标")

        assert analysis["milestones"][0]["question"] == "测试总目标"
