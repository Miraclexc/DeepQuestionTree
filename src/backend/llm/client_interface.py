"""
LLM 客户端抽象基类
定义所有 LLM 客户端必须实现的接口
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel

ResponseContract = Literal["text", "json_object", "json_array"]
StructuredContent = Dict[str, Any] | List[Any] | None


class StructuredOutputContractError(ValueError):
    """结构化输出不符合调用方声明的契约。"""


def parse_structured_content(
    content: str,
    response_contract: ResponseContract,
) -> StructuredContent:
    """按声明的响应契约解析并验证 LLM 输出。"""
    if response_contract == "text":
        return None

    import json

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise StructuredOutputContractError(
            f"Expected {response_contract} response, but content was not valid JSON."
        ) from exc

    if response_contract == "json_object" and not isinstance(parsed, dict):
        raise StructuredOutputContractError(
            "Expected top-level JSON object, but received a different JSON shape."
        )

    if response_contract == "json_array" and not isinstance(parsed, list):
        raise StructuredOutputContractError(
            "Expected top-level JSON array, but received a different JSON shape."
        )

    return parsed


class CompletionResponse(BaseModel):
    """LLM 响应数据封装"""

    content: str
    model: str
    tokens: int = 0
    cost: float = 0.0
    structured_content: StructuredContent = None


class BaseLLMClient(ABC):
    """LLM 客户端抽象基类"""

    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_contract: ResponseContract = "text",
    ) -> CompletionResponse:
        """
        发送对话请求并获取回复

        Args:
            messages: OpenAI 格式的消息列表 [{"role": "user", "content": "..."}]
            temperature: 采样温度，0.0-2.0
            max_tokens: 最大 token 数
            response_contract: 响应契约，区分文本 / JSON 对象 / JSON 数组

        Returns:
            CompletionResponse: 包含文本内容和使用统计的对象

        Raises:
            StructuredOutputContractError: 结构化输出形状不符合契约时抛出
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
