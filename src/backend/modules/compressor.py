"""
压缩模块
负责上下文压缩和事实提取
"""
import json
from typing import List, Dict, Any

from ..core.schema import Fact, QAInteraction, SessionData
from ..llm.client_interface import BaseLLMClient
from ..llm.prompt_manager import get_prompt_manager
from ..llm.embedding import get_embedding_manager
from ..utils.logger import get_logger

logger = get_logger(__name__)


class Compressor:
    """
    压缩器模块
    负责从回答中提取事实和压缩上下文
    """

    def __init__(
        self,
        llm_client: BaseLLMClient,
        prompt_manager=None
    ):
        """
        初始化压缩器

        Args:
            llm_client: LLM 客户端
            prompt_manager: Prompt 管理器
        """
        self.llm = llm_client
        self.prompts = prompt_manager or get_prompt_manager()
        self.embedding_manager = get_embedding_manager()

    async def extract_facts(self, text: str, source_node_id: str) -> tuple[List[Fact], int, str]:
        """
        从文本中提取事实

        Args:
            text: 输入文本
            source_node_id: 来源节点 ID

        Returns:
            tuple[List[Fact], int, str]: (事实列表, 消耗token数, 使用的模型)
        """
        try:
            # 渲染事实提取 Prompt
            prompt = self.prompts.render(
                "extract_facts",
                text=text
            )

            # 调用 LLM 提取事实
            messages = [{"role": "user", "content": prompt}]
            response = await self.llm.chat_completion(
                messages=messages,
                temperature=0.2,  # 低温度保证准确性
                json_mode=True
            )

            # 解析响应
            facts = []
            try:
                facts_data = json.loads(response.content)
                if isinstance(facts_data, list):
                    for fact_data in facts_data:
                        if isinstance(fact_data, dict) and 'content' in fact_data:
                            fact = Fact(
                                content=fact_data['content'],
                                source_node_id=source_node_id,
                                confidence=fact_data.get('confidence', 1.0)
                            )
                            facts.append(fact)
            except json.JSONDecodeError:
                logger.warning(f"无法解析事实提取响应: {response.content[:100]}...")

            # 如果 JSON 解析失败或为空，尝试手动提取
            if not facts:
                facts = self._extract_facts_manually(text, source_node_id)
            
            return facts, response.tokens, response.model

        except Exception as e:
            logger.error(f"提取事实失败: {e}")
            return [], 0, "unknown"

    async def compress_context(
        self,
        context: str,
        token_limit: int = 2000
    ) -> str:
        """
        压缩上下文，保留最重要的信息

        Args:
            context: 原始上下文
            token_limit: Token 限制

        Returns:
            str: 压缩后的上下文
        """
        # 粗略估算 Token 数（中文字符）
        estimated_tokens = len(context)

        if estimated_tokens <= token_limit:
            return context  # 不需要压缩

        try:
            # 渲染压缩 Prompt
            prompt = self.prompts.render(
                "compress_context",
                context=context,
                token_limit=token_limit
            )

            # 调用 LLM 压缩
            messages = [{"role": "user", "content": prompt}]
            compressed_response = await self.llm.chat_completion(
                messages=messages,
                temperature=0.3
            )

            return compressed_response.content.strip()

        except Exception as e:
            logger.error(f"压缩上下文失败: {e}")
            # 降级处理：简单截断
            return context[:token_limit * 2] + "..."

    async def merge_facts(
        self,
        existing_facts: List[Fact],
        new_facts: List[Fact],
        similarity_threshold: float = 0.85
    ) -> List[Fact]:
        """
        合并事实列表，去除重复

        Args:
            existing_facts: 已有事实列表
            new_facts: 新事实列表
            similarity_threshold: 相似度阈值（默认0.85）

        Returns:
            List[Fact]: 合并后的去重事实列表
        """
        merged_facts = existing_facts.copy()

        for new_fact in new_facts:
            # 检查是否与已有事实重复
            is_duplicate = False
            max_similarity = 0.0
            most_similar_fact = None

            # 获取新事实的嵌入向量
            new_fact_emb = await self.embedding_manager.get_embedding(new_fact.content)

            # 计算与所有已有事实的相似度
            for existing_fact in merged_facts:
                existing_fact_emb = await self.embedding_manager.get_embedding(existing_fact.content)
                similarity = self.embedding_manager.cosine_similarity(new_fact_emb, existing_fact_emb)

                if similarity > max_similarity:
                    max_similarity = similarity
                    most_similar_fact = existing_fact

            # 判断是否重复
            if max_similarity >= similarity_threshold:
                is_duplicate = True
                # 保留置信度更高的
                if new_fact.confidence > most_similar_fact.confidence:
                    merged_facts.remove(most_similar_fact)
                    merged_facts.append(new_fact)
                    logger.debug(f"替换事实（置信度更高）: {new_fact.content[:50]}...")
                else:
                    logger.debug(f"跳过重复事实（相似度: {max_similarity:.2f}）: {new_fact.content[:50]}...")

            if not is_duplicate:
                merged_facts.append(new_fact)
                logger.debug(f"添加新事实: {new_fact.content[:50]}...")

        return merged_facts

    def _extract_facts_manually(self, text: str, source_node_id: str) -> List[Fact]:
        """
        手动提取事实（降级方案）
        """
        facts = []

        # 简单的规则：寻找句号结尾的陈述句
        sentences = text.split('。')
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 10 and not sentence.endswith(('？', '！')):
                # 过滤掉明显的主观表述
                subjective_words = ['我认为', '可能', '大概', '也许', '似乎']
                if not any(word in sentence for word in subjective_words):
                    fact = Fact(
                        content=sentence + '。',
                        source_node_id=source_node_id,
                        confidence=0.6  # 手动提取的置信度较低
                    )
                    facts.append(fact)

        # 最多返回 5 个事实
        return facts[:5]

    def summarize_interactions(
        self,
        interactions: List[QAInteraction],
        max_facts: int = 20
    ) -> Dict[str, Any]:
        """
        总结多个交互，提取关键信息

        Args:
            interactions: 交互列表
            max_facts: 最大事实数量

        Returns:
            Dict: 总结信息
        """
        # 收集所有事实
        all_facts = []
        for interaction in interactions:
            # 模拟提取事实（实际应该调用 extract_facts）
            facts = self._extract_facts_manually(
                interaction.answer,
                "summary"
            )
            all_facts.extend(facts)

        # 按置信度排序
        all_facts.sort(key=lambda f: f.confidence, reverse=True)

        # 统计信息
        summary = {
            "total_interactions": len(interactions),
            "total_facts": len(all_facts),
            "key_facts": all_facts[:max_facts],
            "average_confidence": sum(f.confidence for f in all_facts) / len(all_facts) if all_facts else 0
        }

        return summary