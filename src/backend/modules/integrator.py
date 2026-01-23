"""
整合模块
负责生成最终报告，整合所有探索结果
"""
from typing import List, Dict, Any, Optional

from ..core.schema import Node, SessionData, Fact
from ..llm.client_interface import BaseLLMClient
from ..llm.prompt_manager import get_prompt_manager
from ..utils.logger import get_logger

logger = get_logger(__name__)


class Integrator:
    """
    整合器模块
    负责生成最终的综合性报告
    """

    def __init__(
        self,
        llm_client: BaseLLMClient,
        prompt_manager=None
    ):
        """
        初始化整合器

        Args:
            llm_client: LLM 客户端
            prompt_manager: Prompt 管理器
        """
        self.llm = llm_client
        self.prompts = prompt_manager or get_prompt_manager()

    async def generate_final_report(
        self,
        session: SessionData,
        max_facts: int = 50
    ) -> Dict[str, Any]:
        """
        生成最终的综合性报告

        Args:
            session: 会话数据
            max_facts: 最大事实数量

        Returns:
            Dict: 包含报告和分析的字典
        """
        try:
            # 1. 整理和分析事实
            facts_analysis = self._analyze_facts(session.global_facts, max_facts)

            # 2. 提取最佳探索路径
            best_path = session.get_best_path()
            path_analysis = self._analyze_path(best_path)
            
            # --- 新增步骤：分析被剪枝的路径 ---
            pruned_insights = await self._analyze_pruned_paths(session)

            # 3. 生成主要观点
            key_insights = await self._extract_key_insights(session, best_path)

            # 4. 生成完整报告
            # 4. 生成完整报告
            report = await self._generate_report_content(
                session.global_goal,
                facts_analysis,
                path_analysis,
                key_insights,
                pruned_insights
            )

            # 5. 生成执行摘要
            executive_summary = await self._generate_executive_summary(
                session.global_goal,
                report
            )

            # 6. 建议后续探索方向
            suggestions = await self._suggest_next_steps(session)

            # 7. 分析 LLM 使用情况
            llm_stats = self._analyze_llm_usage(session)

            # 整合所有结果
            final_report = {
                "session_id": session.session_id,
                "goal": session.global_goal,
                "executive_summary": executive_summary,
                "full_report": report,
                "key_insights": key_insights,
                "pruned_insights": pruned_insights,
                "statistics": self._get_session_statistics(session),
                "llm_stats": llm_stats, # 新增字段
                "facts_analysis": facts_analysis,
                "path_analysis": path_analysis,
                "suggestions": suggestions,
                "generated_at": session.updated_at.isoformat()
            }

            return final_report

        except Exception as e:
            logger.error(f"生成最终报告失败: {e}")
            return self._get_error_report(session, str(e))

    def _analyze_facts(
        self,
        facts: List[Fact],
        max_facts: int
    ) -> Dict[str, Any]:
        """
        分析收集到的事实
        """
        # 按置信度排序
        sorted_facts = sorted(facts, key=lambda f: f.confidence, reverse=True)

        # 分类事实（简单的关键词分类）
        categories = {
            "技术原理": [],
            "应用场景": [],
            "优势特点": [],
            "风险挑战": [],
            "成本效益": [],
            "其他": []
        }

        for fact in sorted_facts[:max_facts]:
            categorized = False
            for category in categories:
                if self._belongs_to_category(fact.content, category):
                    categories[category].append(fact)
                    categorized = True
                    break
            if not categorized:
                categories["其他"].append(fact)

        # 统计信息
        stats = {
            "total_facts": len(facts),
            "analyzed_facts": min(len(facts), max_facts),
            "average_confidence": sum(f.confidence for f in facts) / len(facts) if facts else 0,
            "high_confidence_facts": sum(1 for f in facts if f.confidence >= 0.9),
            "categories": {
                k: {"count": len(v), "facts": [f.content for f in v[:5]]}
                for k, v in categories.items() if v
            }
        }

        return stats

    def _analyze_path(self, path: List[Node]) -> Dict[str, Any]:
        """
        分析最佳探索路径
        """
        if not path:
            return {"error": "没有探索路径"}

        # 路径统计
        stats = {
            "depth": len(path) - 1,
            "total_visits": sum(n.state.visit_count for n in path),
            "average_value": sum(n.state.average_value for n in path) / len(path),
            "key_questions": [],
            "milestones": []
        }

        # 提取关键问题（高价值节点）
        for node in path:
            if node.interaction and node.state.average_value >= 7.0:
                stats["key_questions"].append({
                    "question": node.interaction.question,
                    "value": node.state.average_value,
                    "depth": node.depth
                })

        # 识别里程碑节点
        for i, node in enumerate(path):
            if i == 0:
                stats["milestones"].append({
                    "type": "起点",
                    "question": session.global_goal if 'session' in locals() else "初始问题",
                    "depth": 0
                })
            elif node.is_pruned:
                stats["milestones"].append({
                    "type": "剪枝点",
                    "question": node.interaction.question if node.interaction else "N/A",
                    "reason": node.prune_reason
                })
            elif node.is_terminal:
                stats["milestones"].append({
                    "type": "终点",
                    "question": node.interaction.question if node.interaction else "N/A",
                    "depth": node.depth
                })

        return stats

    async def _extract_key_insights(
        self,
        session: SessionData,
        best_path: List[Node]
    ) -> List[str]:
        """
        提取关键见解（使用 JSON 格式）
        """
        try:
            # 收集高置信度事实
            high_conf_facts = [
                f for f in session.global_facts
                if f.confidence >= 0.8
            ]

            if not high_conf_facts:
                return []

            # 准备上下文
            facts_text = "\n".join([f"- {f.content}" for f in high_conf_facts[:30]])

            # 渲染提取见解的 Prompt
            prompt = self.prompts.render(
                "extract_key_insights",
                facts_text=facts_text
            )

            # 调用 LLM
            messages = [{"role": "user", "content": prompt}]
            response = await self.llm.chat_completion(
                messages=messages,
                temperature=0.7 # 提高创造性
            )

            # 解析见解 (JSON)
            return self._parse_json_list(response.content)

        except Exception as e:
            logger.error(f"提取关键见解失败: {e}")
            return []

    async def _suggest_next_steps(
        self,
        session: SessionData
    ) -> List[str]:
        """
        建议后续探索方向 (使用 LLM 生成)
        """
        try:
            # 准备事实概览
            facts_summary = "\n".join([f"- {f.content}" for f in session.global_facts[:15]])
            
            prompt = self.prompts.render(
                "suggest_next_steps",
                goal=session.global_goal,
                facts_summary=facts_summary
            )
            
            messages = [{"role": "user", "content": prompt}]
            response = await self.llm.chat_completion(
                messages=messages,
                temperature=0.7
            )
            
            return self._parse_json_list(response.content)

        except Exception as e:
            logger.error(f"生成后续建议失败: {e}")
            return ["继续深入当前的探索路径", "验证已获得的关键假设"]

    def _parse_json_list(self, response: str) -> List[str]:
        """解析 JSON 列表响应"""
        import json
        import re
        
        try:
            # 尝试直接解析
            return json.loads(response)
        except json.JSONDecodeError:
            try:
                # 尝试提取代码块中的内容
                match = re.search(r'\[.*\]', response, re.DOTALL)
                if match:
                    return json.loads(match.group(0))
            except Exception:
                pass
        
        # 降级：简单的行处理
        lines = [line.strip().strip('"').strip("'").strip(',').strip('- ') for line in response.split('\n') if line.strip()]
        return [l for l in lines if len(l) > 5]

    def _get_session_statistics(self, session: SessionData) -> Dict:
        """获取会话统计信息"""
        return {
            "total_nodes": session.get_total_nodes(),
            "total_simulations": session.total_simulations,
            "tree_depth": session.get_tree_depth(),
            "total_facts": len(session.global_facts),
            "active_nodes": len(session.get_active_nodes()),
            "pruned_nodes": sum(1 for n in session.nodes.values() if n.is_pruned)
        }

    async def _analyze_pruned_paths(self, session: SessionData) -> List[str]:
        """
        分析被剪枝的路径
        """
        pruned_summaries = []
        for node in session.nodes.values():
            if node.is_pruned and node.interaction and node.interaction.summary:
                reason = node.prune_reason or "未知原因"
                summary = node.interaction.summary
                pruned_summaries.append(f"路径片段 (因{reason}中止): {summary}")
        return pruned_summaries[:5] # 只取前5个作为代表

    async def _generate_report_content(
        self,
        goal: str,
        facts_analysis: Dict,
        path_analysis: Dict,
        key_insights: List[str],
        pruned_insights: List[str]
    ) -> str:
        """
        生成完整报告内容
        """
        try:
            # 准备事实文本
            facts_text = self._format_facts_for_report(facts_analysis)

            # 准备路径信息
            path_text = self._format_path_for_report(path_analysis)

            # 准备关键见解
            insights_text = "\n".join([f"- {insight}" for insight in key_insights])

            # 准备剪枝见解
            pruned_text = "\n".join([f"- {insight}" for insight in pruned_insights]) if pruned_insights else "无显著剪枝记录"

            # 渲染报告 Prompt
            prompt = self.prompts.render(
                "generate_report",
                goal=goal,
                facts=facts_text,
                main_paths=path_text,
                key_insights=insights_text
            )
            
            # 生成报告
            messages = [{"role": "user", "content": prompt}]
            report = await self.llm.chat_completion(
                messages=messages,
                temperature=0.3
            )

            return report.content

        except Exception as e:
            logger.error(f"生成报告内容失败: {e}")
            return f"报告生成失败: {str(e)}"

    async def _generate_executive_summary(
        self,
        goal: str,
        full_report: str
    ) -> str:
        """
        生成执行摘要
        """
        try:
            prompt = self.prompts.render(
                "generate_executive_summary",
                goal=goal,
                report_content=full_report[:1000]
            )

            messages = [{"role": "user", "content": prompt}]
            summary = await self.llm.chat_completion(
                messages=messages,
                temperature=0.3
            )

            return summary.content.strip()

        except Exception as e:
            logger.error(f"生成执行摘要失败: {e}")
            return full_report[:200] + "..."

    def _belongs_to_category(self, content: str, category: str) -> bool:
        """
        判断事实属于哪个类别
        """
        category_keywords = {
            "技术原理": ["原理", "机制", "算法", "架构", "实现"],
            "应用场景": ["应用", "场景", "案例", "用途", "行业"],
            "优势特点": ["优势", "特点", "好处", "优点", "强项"],
            "风险挑战": ["风险", "挑战", "问题", "困难", "缺陷"],
            "成本效益": ["成本", "效益", "投资", "收益", "预算"]
        }

        keywords = category_keywords.get(category, [])
        return any(kw in content for kw in keywords)

    def _format_facts_for_report(self, facts_analysis: Dict) -> str:
        """格式化事实用于报告"""
        facts_text = []
        for category, info in facts_analysis["categories"].items():
            if info["facts"]:
                facts_text.append(f"\n### {category} ({info['count']}项)")
                for fact in info["facts"]:
                    facts_text.append(f"- {fact}")
        return "\n".join(facts_text)

    def _format_path_for_report(self, path_analysis: Dict) -> str:
        """格式化路径用于报告"""
        if "error" in path_analysis:
            return path_analysis["error"]

        path_text = []
        path_text.append(f"\n探索深度：{path_analysis['depth']}层")
        path_text.append(f"平均价值评分：{path_analysis['average_value']:.2f}/10")

        if path_analysis["key_questions"]:
            path_text.append("\n### 关键问题")
            for q in path_analysis["key_questions"][:5]:
                path_text.append(f"- {q['question']} (评分: {q['value']:.2f})")

        return "\n".join(path_text)

    def _analyze_llm_usage(self, session: SessionData) -> Dict[str, Any]:
        """
        分析 LLM 使用情况
        """
        usage_by_model = {}
        total_tokens = 0
        total_calls = 0

        for node in session.nodes.values():
            if node.interaction:
                model = node.interaction.model_used or "unknown"
                tokens = node.interaction.tokens_used
                
                if model not in usage_by_model:
                    usage_by_model[model] = {"calls": 0, "tokens": 0}
                
                usage_by_model[model]["calls"] += 1
                usage_by_model[model]["tokens"] += tokens
                
                total_calls += 1
                total_tokens += tokens

        return {
            "total_calls": total_calls,
            "total_tokens": total_tokens,
            "usage_by_model": usage_by_model
        }

    def _get_error_report(self, session: SessionData, error: str) -> Dict:
        """获取错误报告"""
        return {
            "session_id": session.session_id,
            "goal": session.global_goal,
            "error": error,
            "partial_data": {
                "facts_count": len(session.global_facts),
                "nodes_count": len(session.nodes),
                "simulations": session.total_simulations
            },
            "generated_at": session.updated_at.isoformat()
        }