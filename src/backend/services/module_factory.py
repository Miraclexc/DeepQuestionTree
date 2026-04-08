from __future__ import annotations

from dataclasses import dataclass

from ..config_loader import get_settings
from ..llm.client_interface import BaseLLMClient
from ..llm.llm_client import OpenAICompatibleClient
from ..llm.mock_client import MockClient
from ..modules.checker import Checker
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
        checker = Checker(llm_client)

        return RuntimeModules(
            llm_client=llm_client,
            questioner=Questioner(llm_client, checker=checker),
            compressor=Compressor(llm_client, checker=checker),
            pruner=Pruner(llm_client, checker=checker),
            integrator=Integrator(llm_client),
        )
