from types import SimpleNamespace

import pytest

from src.backend.core.schema import Fact, Node, QAInteraction, SessionData
from src.backend.llm.mock_client import MockClient
from src.backend.modules.integrator import Integrator


class ContractAwareIntegratorLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.response_contracts: list[str] = []

    async def chat_completion(
        self,
        messages,
        temperature=0.7,
        max_tokens=None,
        response_contract="text",
        purpose="generation",
    ):
        self.response_contracts.append(response_contract)
        response = self.responses.pop(0)
        return SimpleNamespace(
            content=response["content"],
            structured_content=response.get("structured_content"),
            tokens=response.get("tokens", 0),
            model=response.get("model", "contract-aware"),
        )

    async def get_usage_stats(self):
        return {}

    async def reset_usage_stats(self):
        return None


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

    @pytest.mark.asyncio
    async def test_extract_key_insights_uses_json_array_contract(self):
        llm_client = ContractAwareIntegratorLLM(
            [
                {
                    "content": '["见解1", "见解2"]',
                    "structured_content": ["见解1", "见解2"],
                }
            ]
        )
        integrator = Integrator(llm_client)
        session = SessionData(global_goal="测试目标")
        session.global_facts = [
            Fact(content="高置信度事实", source_node_id="node_1", confidence=0.95)
        ]

        insights = await integrator._extract_key_insights(session, best_path=[])

        assert llm_client.response_contracts == ["json_array"]
        assert insights == ["见解1", "见解2"]

    @pytest.mark.asyncio
    async def test_suggest_next_steps_uses_json_array_contract(self):
        llm_client = ContractAwareIntegratorLLM(
            [
                {
                    "content": '["建议1", "建议2"]',
                    "structured_content": ["建议1", "建议2"],
                }
            ]
        )
        integrator = Integrator(llm_client)
        session = SessionData(global_goal="测试目标")
        session.global_facts = [
            Fact(content="已发现事实", source_node_id="node_1", confidence=0.8)
        ]

        suggestions = await integrator._suggest_next_steps(session)

        assert llm_client.response_contracts == ["json_array"]
        assert suggestions == ["建议1", "建议2"]
