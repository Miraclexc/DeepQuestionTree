"""
OpenAI 兼容 LLM 客户端实现
支持 OpenAI、DeepSeek、Moonshot 等所有兼容 OpenAI API 的服务
"""

from typing import Any, Dict, List, Optional

import openai
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..config_loader import get_settings
from ..utils.logger import get_logger
from .client_interface import (
    BaseLLMClient,
    CompletionResponse,
    Purpose,
    ResponseContract,
    StructuredOutputContractError,
    parse_structured_content,
)

logger = get_logger(__name__)


class OpenAICompatibleClient(BaseLLMClient):
    """OpenAI 兼容的 LLM 客户端"""

    def __init__(self):
        """初始化客户端"""
        settings = get_settings()

        # 初始化 OpenAI 客户端
        self.client = openai.AsyncOpenAI(
            api_key=settings.llm.api_key,
            base_url=settings.llm.base_url,
            timeout=settings.llm.timeout,
            max_retries=settings.llm.max_retries,
        )

        self.generation_model = settings.llm.generation_model
        self.decision_model = settings.llm.decision_model

        # 使用统计
        self.total_tokens_used = 0
        self.total_cost = 0.0
        self.request_count = 0

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((openai.RateLimitError, openai.APITimeoutError)),
    )
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_contract: ResponseContract = "text",
        purpose: Purpose = "generation",
    ) -> CompletionResponse:
        """
        执行对话请求，包含自动重试逻辑
        """
        try:
            model = (
                self.decision_model if purpose == "decision" else self.generation_model
            )

            # 设置响应格式
            response_format = (
                {"type": "json_object"} if response_contract == "json_object" else None
            )

            # 发送请求
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )

            # 提取内容
            content = response.choices[0].message.content or ""
            structured_content = None
            if response_contract != "text":
                try:
                    structured_content = parse_structured_content(
                        content,
                        response_contract,
                    )
                except StructuredOutputContractError as exc:
                    logger.warning(
                        "Structured response contract mismatch for %s: %s",
                        response_contract,
                        exc,
                    )
                    raise

            # 更新使用统计
            tokens = 0
            cost = 0.0
            if response.usage:
                tokens = response.usage.total_tokens
                cost = self._estimate_cost(model, tokens)

                self.total_tokens_used += tokens
                self.total_cost += cost
            self.request_count += 1

            return CompletionResponse(
                content=content,
                model=model,
                tokens=tokens,
                cost=cost,
                structured_content=structured_content,
            )

        except StructuredOutputContractError:
            raise

        except openai.AuthenticationError as e:
            raise Exception(f"API 认证失败: {e}")
        except openai.RateLimitError as e:
            raise Exception(f"API 请求频率限制: {e}")
        except openai.APITimeoutError as e:
            raise Exception(f"API 请求超时: {e}")
        except Exception as e:
            raise Exception(f"LLM API 调用失败: {e}")

    async def get_usage_stats(self) -> Dict[str, Any]:
        """获取使用统计"""
        return {
            "total_tokens_used": self.total_tokens_used,
            "total_cost_usd": self.total_cost,
            "total_requests": self.request_count,
            "average_tokens_per_request": self.total_tokens_used
            / max(self.request_count, 1),
        }

    async def reset_usage_stats(self) -> None:
        """重置使用统计"""
        self.total_tokens_used = 0
        self.total_cost = 0.0
        self.request_count = 0

    def _estimate_cost(self, model: str, tokens: int) -> float:
        """
        估算费用（简化版，实际应该根据具体定价）
        """
        # 这里是简化的定价模型，实际需要根据具体服务的定价表
        pricing_per_1k = {
            "gpt-4": 0.03,
            "gpt-4o": 0.005,
            "gpt-3.5-turbo": 0.002,
            "deepseek-chat": 0.0014,
            "moonshot-v1-8k": 0.012,
        }

        price_per_1k = pricing_per_1k.get(model, 0.01)
        return (tokens / 1000) * price_per_1k
