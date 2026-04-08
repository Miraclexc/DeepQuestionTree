from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

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
from .errors import ConfigurationError

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
            self._validate_real_provider_settings(settings)
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

    def _validate_real_provider_settings(self, settings) -> None:
        llm = settings.llm
        missing_fields: list[str] = []
        if not str(llm.api_key or "").strip():
            missing_fields.append("llm.api_key")
        if not str(llm.generation_model or "").strip():
            missing_fields.append("llm.generation_model")
        if not str(llm.decision_model or "").strip():
            missing_fields.append("llm.decision_model")

        base_url = str(llm.base_url or "").strip()
        parsed_url = urlparse(base_url) if base_url else None
        base_url_valid = bool(
            parsed_url and parsed_url.scheme in {"http", "https"} and parsed_url.netloc
        )
        if not base_url_valid:
            missing_fields.append("llm.base_url")

        if not missing_fields:
            return

        detail = (
            "Real provider configuration is invalid: "
            f"{', '.join(missing_fields)}. "
            "Fix the provider settings or enable mock mode via "
            "APP__MOCK_LLM=true / use_mock=true."
        )
        raise ConfigurationError(detail)
