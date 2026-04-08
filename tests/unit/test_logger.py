from __future__ import annotations

import logging
import logging.handlers
from types import SimpleNamespace

from src.backend.utils.logger import setup_logging


def test_setup_logging_uses_timed_rotation_handler_for_daily(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "src.backend.utils.logger.get_settings",
        lambda: SimpleNamespace(
            logging=SimpleNamespace(
                level="INFO",
                json_format=False,
                file_rotation="daily",
            ),
            storage=SimpleNamespace(logs_dir=str(tmp_path)),
        ),
    )

    setup_logging()

    try:
        rotating_handlers = [
            handler
            for handler in logging.getLogger().handlers
            if isinstance(handler, logging.handlers.TimedRotatingFileHandler)
        ]
        assert rotating_handlers
    finally:
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            handler.close()
