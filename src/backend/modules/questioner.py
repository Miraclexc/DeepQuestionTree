"""
提问模块
负责生成候选问题、评估问题价值、检测重复问题
"""
import json
from typing import List, Dict, Any

from ..core.schema import Fact, SessionData
from ..llm.client_interface import BaseLLMClient
from ..llm.prompt_manager import get_prompt_manager
from ..llm.embedding import get_embedding_manager
from ..utils.logger import get_logger

logger = get_logger(__name__)


class Questioner:
    """
    提问者模块
    负责问题生成、价值评估和重复检测
    """

    def __init__(
        self,
        llm_client: BaseLLMClient,
        embedding_manager=None,
        prompt_manager=None
    ):
        """
        初始化提问者

        Args:
            llm_client: LLM 客户端
            embedding_manager: 嵌入管理器
            prompt_manager: Prompt 管理器
        """
        self.llm = llm_client
        self.embedding = embedding_manager or get_embedding_manager()
        self.prompts = prompt_manager or get_prompt_manager()
        self.settings = None

        # 维护历史问题库（用于去重）
        self.history_questions: List[str] = []
        self.history_embeddings: List[List[float]] = []

    async def generate_candidates(
        self,
        context_facts: List[Fact],
        current_answer: str,
        goal: str,
        parent_question: str = "初始问题",
        k: int = 3
    ) -> List[str]:
        """
        生成候选问题列表

        Args:
            context_facts: 当前上下文中的事实列表
            current_answer: 当前的回答
            goal: 全局目标问题
            parent_question: 上一轮提出的问题
            k: 生成问题数量

        Returns:
            List[str]: 候选问题列表
        """
        try:
            # 准备上下文文本
            if context_facts:
                facts_text = "\n".join([f"- {f.content}" for f in context_facts[-10:]])  # 限制事实数量
            else:
                facts_text = "暂无已知事实"

            # 渲染 Prompt
            prompt = self.prompts.render(
                "generate_questions",
                context_facts=facts_text,
                current_answer=current_answer,
                goal=goal,
                parent_question=parent_question,
                k=k
            )

            # 调用 LLM 生成问题
            messages = [{"role": "user", "content": prompt}]
            response = await self.llm.chat_completion(
                messages=messages,
                temperature=0.8,  # 较高的创造性
                json_mode=True
            )

            # 解析响应 (使用 response.content)
            try:
                questions = json.loads(response.content)
                if isinstance(questions, list):
                    # 过滤和验证问题
                    valid_questions = []
                    for q in questions[:k]:
                        if isinstance(q, str) and len(q.strip()) > 5:
                            valid_questions.append(q.strip())
                    return valid_questions
            except json.JSONDecodeError:
                logger.warning(f"无法解析问题生成响应: {response.content[:100]}...")

            # 如果 JSON 解析失败，尝试手动提取
            return self._extract_questions_from_text(response.content)

        except Exception as e:
            logger.error(f"生成候选问题失败: {e}")
            # 返回默认问题
            return self._get_default_questions(k)

    async def evaluate_question_value(
        self,
        question: str,
        known_facts: List[Fact],
        goal: str,
        parent_question: str = "初始问题"
    ) -> float:
        """
        评估问题的信息增益价值

        Args:
            question: 待评估的问题
            known_facts: 已知事实列表
            goal: 全局目标
            parent_question: 上一轮问题

        Returns:
            float: 评估分数 (0.0 - 10.0)
        """
        try:
            # 准备已知事实文本
            if known_facts:
                facts_text = "\n".join([f"- {f.content}" for f in known_facts[-20:]])  # 限制数量
            else:
                facts_text = "暂无已知事实"

            # 渲染评估 Prompt
            prompt = self.prompts.render(
                "evaluate_question",
                question=question,
                known_facts=facts_text,
                goal=goal,
                parent_question=parent_question
            )

            # 调用 LLM 评估
            messages = [{"role": "user", "content": prompt}]
            response = await self.llm.chat_completion(
                messages=messages,
                temperature=0.3,  # 较低的随机性
                json_mode=True
            )

            # 解析分数 (使用 response.content)
            score = self._extract_score(response.content)
            return max(0.0, min(10.0, float(score)))

        except Exception as e:
            logger.error(f"评估问题价值失败: {e}")
            # 返回中等分数
            return 5.0

    async def answer_question(
        self,
        question: str,
        context_facts: List[Fact],
        goal: str
    ) -> tuple[str, int, str]:
        """
        回答问题

        Args:
            question: 问题内容
            context_facts: 上下文事实
            goal: 全局目标

        Returns:
            tuple[str, int, str]: (回答内容, 消耗token数, 使用的模型)
        """
        try:
             # Context from global facts (take last 10)
            facts_text = "\n".join([f"- {f.content}" for f in context_facts[-10:]])
            
            # 使用 Prompt Manager 渲染
            prompt = self.prompts.render(
                "process_node_answer",
                goal=goal,
                facts_text=facts_text,
                question=question
            )
            
            messages = [{"role": "user", "content": prompt}]
            
            # 使用 LLM 客户端
            response = await self.llm.chat_completion(
                messages=messages,
                temperature=0.7,
                json_mode=False
            )
            
            return response.content, response.tokens, response.model

        except Exception as e:
            logger.error(f"回答问题失败: {e}")
            return "Error generating answer.", 0, "unknown"

    async def check_duplicate(
        self,
        question: str,
        threshold: float = None
    ) -> bool:
        """
        检查问题是否重复

        Args:
            question: 待检查的问题
            threshold: 相似度阈值

        Returns:
            bool: 是否重复
        """
        if threshold is None:
            from ..config_loader import get_settings
            self.settings = get_settings()
            threshold = self.settings.embedding.similarity_threshold

        if not self.history_questions:
            # 第一个问题，记录并返回不重复
            await self._add_to_history(question)
            return False

        # 检查与历史问题的相似度
        is_duplicate = await self.embedding.check_duplicate(
            question,
            self.history_questions,
            threshold
        )

        if not is_duplicate:
            # 不重复，加入历史
            await self._add_to_history(question)

        return is_duplicate

    async def _add_to_history(self, question: str) -> None:
        """添加问题到历史记录"""
        self.history_questions.append(question)
        emb = await self.embedding.get_embedding(question)
        self.history_embeddings.append(emb)

        # 限制历史记录数量
        max_history = 1000
        if len(self.history_questions) > max_history:
            self.history_questions = self.history_questions[-max_history:]
            self.history_embeddings = self.history_embeddings[-max_history:]

    def _extract_questions_from_text(self, text: str) -> List[str]:
        """从文本中提取问题列表"""
        import re

        # 尝试匹配引号或编号列表中的问题
        questions = []

        # 匹配引号中的问题
        quoted = re.findall(r'["\"]([^"\"]{10,})["\"]', text)
        questions.extend(quoted)

        # 匹配编号列表
        numbered = re.findall(r'^\d+\.\s*(.+)$', text, re.MULTILINE)
        questions.extend([q.strip() for q in numbered if len(q.strip()) > 10])

        # 匹配问号结尾的句子（改进版，支持中文和英文问号）
        sentences = re.findall(r'([^\n.!。！]*[?？]+)', text)
        questions.extend([s.strip() for s in sentences if len(s.strip()) > 5])

        # 去重并返回
        unique_questions = list(dict.fromkeys(questions))  # 保持顺序的去重
        return unique_questions[:3]  # 最多返回3个

    def _extract_score(self, response: str) -> float:
        """从响应中提取分数"""
        import re

        # 尝试匹配数字
        numbers = re.findall(r'\d+(?:\.\d+)?', response)
        if numbers:
            return float(numbers[0])

        # 尝试解析 JSON
        try:
            data = json.loads(response)
            if isinstance(data, dict) and 'score' in data:
                return float(data['score'])
        except:
            pass

        # 默认分数
        return 5.0

    def _get_default_questions(self, k: int) -> List[str]:
        """获取默认问题列表"""
        default_questions = [
            "这个技术的核心原理是什么？",
            "它有哪些潜在的应用场景？",
            "实施过程中可能遇到哪些挑战？",
            "与现有方案相比有何优势？",
            "未来的发展趋势如何？"
        ]
        return default_questions[:k]