"""
LLM 客户端抽象基类
定义所有 LLM 客户端必须实现的接口
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class CompletionResponse(BaseModel):
    """LLM 响应数据封装"""
    content: str
    model: str
    tokens: int = 0
    cost: float = 0.0

class BaseLLMClient(ABC):
    """LLM 客户端抽象基类"""

    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        json_mode: bool = False
    ) -> CompletionResponse:
        """
        发送对话请求并获取回复

        Args:
            messages: OpenAI 格式的消息列表 [{"role": "user", "content": "..."}]
            temperature: 采样温度，0.0-2.0
            max_tokens: 最大 token 数
            json_mode: 是否强制返回 JSON 格式

        Returns:
            CompletionResponse: 包含文本内容和使用统计的对象

        Raises:
            Exception: API 调用失败时抛出异常
        """
        pass

    @abstractmethod
    async def get_embedding(self, text: str) -> List[float]:
        """
        获取文本的向量表示

        Args:
            text: 需要向量化的文本

        Returns:
            List[float]: 文本的嵌入向量

        Raises:
            Exception: API 调用失败时抛出异常
        """
        pass

    @abstractmethod
    async def get_usage_stats(self) -> Dict[str, Any]:
        """
        获取当前会话的使用统计

        Returns:
            Dict: 包含 token 消耗、费用等信息的字典
        """
        pass

    @abstractmethod
    async def reset_usage_stats(self) -> None:
        """重置使用统计"""
        pass