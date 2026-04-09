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


class RecordingPromptManager:
    def __init__(self):
        self.calls: list[tuple[str, dict[str, object]]] = []

    def render(self, key: str, **kwargs):
        self.calls.append((key, kwargs))
        if key == "generate_report":
            return (
                f"goal={kwargs['goal']}\n"
                f"facts={kwargs['facts']}\n"
                f"main_paths={kwargs['main_paths']}\n"
                f"key_insights={kwargs['key_insights']}"
            )
        if key == "generate_executive_summary":
            return f"summary::{kwargs['report_content']}"
        if key == "extract_key_insights":
            return f"insights::{kwargs['facts_text']}"
        if key == "suggest_next_steps":
            return f"suggest::{kwargs['goal']}::{kwargs['facts_summary']}"
        raise AssertionError(f"unexpected prompt key: {key}")


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

    @pytest.mark.asyncio
    async def test_generate_final_report_keeps_pruned_insights_out_of_report_prompt(
        self,
    ):
        llm_client = ContractAwareIntegratorLLM(
            [
                {
                    "content": '["关键见解"]',
                    "structured_content": ["关键见解"],
                },
                {
                    "content": "正式报告正文",
                },
                {
                    "content": "执行摘要",
                },
                {
                    "content": '["下一步建议"]',
                    "structured_content": ["下一步建议"],
                },
            ]
        )
        prompts = RecordingPromptManager()
        integrator = Integrator(llm_client, prompt_manager=prompts)
        session = SessionData(global_goal="测试目标")
        pruned_node = Node(
            parent_id=session.root_node_id,
            depth=1,
            interaction=QAInteraction(
                question="低价值路径",
                answer="无效回答",
                summary="这条剪枝摘要不应进入正文",
            ),
            is_pruned=True,
            prune_reason="连续低价值路径",
        )
        session.add_node(
            Node(
                id=session.root_node_id,
                depth=0,
                interaction=QAInteraction(question="测试目标", answer="探索起点"),
            )
        )
        session.add_node(pruned_node)
        session.global_facts = [
            Fact(
                content="已验证事实",
                source_node_id=session.root_node_id,
                confidence=0.9,
            )
        ]

        report = await integrator.generate_final_report(session)

        generate_report_call = next(
            kwargs for key, kwargs in prompts.calls if key == "generate_report"
        )
        executive_summary_call = next(
            kwargs
            for key, kwargs in prompts.calls
            if key == "generate_executive_summary"
        )

        assert "pruned" not in generate_report_call
        assert "这条剪枝摘要不应进入正文" not in report["full_report"]
        assert (
            "这条剪枝摘要不应进入正文" not in executive_summary_call["report_content"]
        )
        assert report["pruned_insights"] == [
            "路径片段 (因连续低价值路径中止): 这条剪枝摘要不应进入正文"
        ]
