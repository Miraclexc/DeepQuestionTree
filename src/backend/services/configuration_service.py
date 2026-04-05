from __future__ import annotations

from ..api.dto import MessageResponse
from ..config_loader import reload_settings
from ..utils.logger import setup_logging
from .coordinator import RuntimeCoordinator
from .module_factory import RuntimeModuleFactory


class ConfigurationService:
    """负责配置重载与模块重建。"""

    def __init__(
        self,
        coordinator: RuntimeCoordinator,
        module_factory: RuntimeModuleFactory,
    ) -> None:
        self._coordinator = coordinator
        self._module_factory = module_factory

    def reload_configuration(self) -> MessageResponse:
        reload_settings()
        setup_logging()
        modules = self._module_factory.build(use_mock=self._coordinator.use_mock)
        self._coordinator.reconfigure(modules)
        return MessageResponse(message="配置已重新加载")
