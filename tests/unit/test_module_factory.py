from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.backend.services.errors as error_module
import src.backend.services.module_factory as module_factory
from src.backend.services.module_factory import RuntimeModuleFactory


def test_runtime_module_factory_rejects_invalid_real_provider_configuration(
    monkeypatch,
):
    monkeypatch.setattr(
        "src.backend.services.module_factory.get_settings",
        lambda: SimpleNamespace(
            app=SimpleNamespace(mock_llm=False),
            llm=SimpleNamespace(
                api_key="",
                base_url="",
                generation_model="",
                decision_model="",
                timeout=60,
                max_retries=3,
            ),
            logging=SimpleNamespace(level="INFO"),
        ),
    )

    with pytest.raises(error_module.ApplicationError) as exc_info:
        RuntimeModuleFactory().build(use_mock=False)

    assert exc_info.value.code == "configuration_error"
    assert "mock" in exc_info.value.detail.lower()


def test_runtime_module_factory_accepts_deepseek_defaults(monkeypatch):
    sentinel_client = object()

    monkeypatch.setattr(
        "src.backend.services.module_factory.get_settings",
        lambda: SimpleNamespace(
            app=SimpleNamespace(mock_llm=False),
            llm=SimpleNamespace(
                api_key="deepseek-key",
                base_url="https://api.deepseek.com/v1",
                generation_model="deepseek-chat",
                decision_model="deepseek-reasoner",
                timeout=60,
                max_retries=3,
            ),
            logging=SimpleNamespace(level="INFO"),
        ),
    )
    monkeypatch.setattr(
        module_factory,
        "OpenAICompatibleClient",
        lambda: sentinel_client,
    )
    monkeypatch.setattr(module_factory, "Checker", lambda client: ("checker", client))
    monkeypatch.setattr(
        module_factory,
        "Questioner",
        lambda client, checker: ("questioner", client, checker),
    )
    monkeypatch.setattr(
        module_factory,
        "Compressor",
        lambda client, checker: ("compressor", client, checker),
    )
    monkeypatch.setattr(
        module_factory,
        "Pruner",
        lambda client, checker: ("pruner", client, checker),
    )
    monkeypatch.setattr(
        module_factory,
        "Integrator",
        lambda client: ("integrator", client),
    )

    modules = RuntimeModuleFactory().build(use_mock=False)

    assert modules.llm_client is sentinel_client
    assert modules.integrator == ("integrator", sentinel_client)
