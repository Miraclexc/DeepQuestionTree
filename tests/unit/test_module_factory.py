from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.backend.services.errors as error_module
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
