"""
嵌入向量管理模块
支持本地模型和 API 两种模式
"""
import numpy as np
from typing import List, Optional

from ..config_loader import get_settings
from .client_interface import BaseLLMClient


class EmbeddingManager:
    """嵌入向量管理器，支持本地和 API 两种模式"""

    _instance = None
    _model = None
    _client = None

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super(EmbeddingManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化嵌入管理器"""
        self.settings = get_settings()
        self._initialize()

    def _initialize(self) -> None:
        """初始化本地模型或客户端"""
        if self.settings.embedding.use_local:
            self._initialize_local_model()
        else:
            # API 模式需要外部传入 LLM 客户端
            pass

    def _initialize_local_model(self) -> None:
        """初始化本地 sentence-transformers 模型"""
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.settings.embedding.model_path)
            print(f"已加载本地嵌入模型: {self.settings.embedding.model_path}")
        except ImportError:
            raise ImportError(
                "使用本地嵌入模型需要安装 sentence-transformers: "
                "pip install sentence-transformers"
            )
        except Exception as e:
            raise Exception(f"加载本地嵌入模型失败: {e}")

    def set_client(self, client: BaseLLMClient) -> None:
        """
        设置用于 API 模式的 LLM 客户端

        Args:
            client: LLM 客户端实例
        """
        self._client = client

    async def get_embedding(self, text: str) -> List[float]:
        """
        获取文本的嵌入向量

        Args:
            text: 需要向量化的文本

        Returns:
            List[float]: 文本的嵌入向量
        """
        if not text or not text.strip():
            # 对空文本返回零向量
            return [0.0] * 768

        # 预处理文本
        text = text.strip()
        if len(text) > 8000:  # 避免文本过长
            text = text[:8000] + "..."

        if self.settings.embedding.use_local and self._model:
            # 使用本地模型
            return self._model.encode(text).tolist()
        elif self._client:
            # 使用 API
            return await self._client.get_embedding(text)
        else:
            raise Exception(
                "没有可用的嵌入模型。请检查配置或设置 LLM 客户端。"
            )

    async def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        批量获取嵌入向量

        Args:
            texts: 文本列表

        Returns:
            List[List[float]]: 嵌入向量列表
        """
        if not texts:
            return []

        if self.settings.embedding.use_local and self._model:
            # 本地模型支持批量处理
            embeddings = self._model.encode(texts)
            return [emb.tolist() for emb in embeddings]
        else:
            # API 模式需要逐个调用
            embeddings = []
            for text in texts:
                emb = await self.get_embedding(text)
                embeddings.append(emb)
            return embeddings

    def cosine_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        计算两个嵌入向量的余弦相似度

        Args:
            embedding1: 第一个向量
            embedding2: 第二个向量

        Returns:
            float: 余弦相似度 (-1 到 1)
        """
        # 转换为 numpy 数组
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        # 计算余弦相似度
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    async def find_most_similar(
        self,
        query: str,
        candidates: List[str],
        top_k: int = 1
    ) -> List[tuple]:
        """
        在候选文本中找到与查询最相似的文本

        Args:
            query: 查询文本
            candidates: 候选文本列表
            top_k: 返回最相似的 k 个结果

        Returns:
            List[tuple]: [(index, similarity_score, text), ...] 按相似度降序排列
        """
        if not candidates:
            return []

        # 获取查询向量
        query_emb = await self.get_embedding(query)

        # 批量获取候选向量
        candidate_embs = await self.get_embeddings_batch(candidates)

        # 计算相似度
        similarities = []
        for i, cand_emb in enumerate(candidate_embs):
            sim = self.cosine_similarity(query_emb, cand_emb)
            similarities.append((i, sim, candidates[i]))

        # 按相似度降序排序
        similarities.sort(key=lambda x: x[1], reverse=True)

        # 返回 top_k 个结果
        return similarities[:top_k]

    async def check_duplicate(
        self,
        text: str,
        existing_texts: List[str],
        threshold: Optional[float] = None
    ) -> bool:
        """
        检查文本是否与已有文本重复

        Args:
            text: 待检查的文本
            existing_texts: 已有文本列表
            threshold: 相似度阈值，默认使用配置中的值

        Returns:
            bool: 是否重复
        """
        if not existing_texts:
            return False

        if threshold is None:
            threshold = self.settings.embedding.similarity_threshold

        # 找到最相似的文本
        most_similar = await self.find_most_similar(text, existing_texts, top_k=1)

        if most_similar:
            _, similarity, _ = most_similar[0]
            # 转换 NumPy bool 为 Python bool
            return bool(similarity >= threshold)

        return False

    def get_dimension(self) -> int:
        """
        获取嵌入向量的维度

        Returns:
            int: 向量维度
        """
        if self._model:
            return self._model.get_sentence_embedding_dimension()
        else:
            # API 模式的常见维度
            return 768  # OpenAI 的 text-embedding-ada-002 维度


# 全局实例
_embedding_manager: Optional[EmbeddingManager] = None


def get_embedding_manager() -> EmbeddingManager:
    """
    获取全局嵌入管理器实例

    Returns:
        EmbeddingManager: 嵌入管理器实例
    """
    global _embedding_manager
    if _embedding_manager is None:
        _embedding_manager = EmbeddingManager()
    return _embedding_manager