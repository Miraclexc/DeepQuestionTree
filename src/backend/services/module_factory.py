from __future__ import annotations

from dataclasses import dataclass

from ..config_loader import get_settings
from ..llm.client_interface import BaseLLMClient
from ..llm.embedding import get_embedding_manager
from ..llm.llm_client import OpenAICompatibleClient
from ..llm.mock_client import MockClient
from ..modules.compressor import Compressor
from ..modules.integrator import Integrator
from ..modules.pruner import Pruner
from ..modules.questioner import Questioner
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class RuntimeModules:
    llm_client: BaseLLMClient
    questioner: Questioner
    compressor: Compressor
    pruner: Pruner
    integrator: Integrator


class RuntimeModuleFactory:
    """集中装配运行时依赖模块。"""

    def build(self, *, use_mock: bool) -> RuntimeModules:
        settings = get_settings()
        effective_use_mock = use_mock or settings.app.mock_llm

        llm_client: BaseLLMClient
        if effective_use_mock:
            logger.info("使用 Mock LLM 客户端")
            llm_client = MockClient()
        else:
            logger.info("使用 OpenAI 兼容 LLM 客户端")
            llm_client = OpenAICompatibleClient()

        embedding_manager = get_embedding_manager()
        embedding_manager.refresh_settings()
        embedding_manager.set_client(
            llm_client,
            prefer_client=effective_use_mock or not settings.embedding.use_local,
        )

        return RuntimeModules(
            llm_client=llm_client,
            questioner=Questioner(llm_client, embedding_manager),
            compressor=Compressor(llm_client),
            pruner=Pruner(llm_client, embedding_manager),
            integrator=Integrator(llm_client),
        )
