import textwrap
from pathlib import Path

import src.backend.modules.persistence as persistence_module
from src.backend.config_loader import load_settings, reload_settings


def test_load_settings_does_not_read_frontend_env_local(monkeypatch, tmp_path):
    project_root = tmp_path
    config_dir = project_root / "config"
    frontend_dir = project_root / "src" / "frontend"

    config_dir.mkdir(parents=True)
    frontend_dir.mkdir(parents=True)

    (config_dir / "settings.yaml").write_text(
        textwrap.dedent(
            """
            app:
              api_port: 9100
              frontend_port: 3100
            """
        ).strip(),
        encoding="utf-8",
    )
    (frontend_dir / ".env.local").write_text(
        textwrap.dedent(
            """
            NEXT_PUBLIC_API_PORT=9999
            NEXT_PUBLIC_FRONTEND_PORT=3999
            """
        ).strip(),
        encoding="utf-8",
    )

    monkeypatch.chdir(project_root)

    settings = load_settings("config/settings.yaml")

    assert settings.app.api_port == 9100
    assert settings.app.frontend_port == 3100


def test_load_settings_applies_security_token_env_override(monkeypatch, tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)

    (config_dir / "settings.yaml").write_text(
        textwrap.dedent(
            """
            security:
              api_token: yaml-token
            """
        ).strip(),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SECURITY__API_TOKEN", "env-token")

    settings = load_settings("config/settings.yaml")

    assert settings.security.api_token == "env-token"


def test_load_settings_dotenv_overrides_yaml(monkeypatch, tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)

    (config_dir / "settings.yaml").write_text(
        textwrap.dedent(
            """
            app:
              debug: true
              api_port: 9100
            llm:
              base_url: https://yaml.example/v1
            """
        ).strip(),
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text(
        textwrap.dedent(
            """
            APP__DEBUG=false
            APP__API_PORT=9200
            LLM__BASE_URL=https://dotenv.example/v1
            """
        ).strip(),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("APP__DEBUG", raising=False)
    monkeypatch.delenv("APP__API_PORT", raising=False)
    monkeypatch.delenv("LLM__BASE_URL", raising=False)

    settings = load_settings("config/settings.yaml")

    assert settings.app.debug is False
    assert settings.app.api_port == 9200
    assert settings.llm.base_url == "https://dotenv.example/v1"


def test_load_settings_environment_overrides_dotenv_and_yaml(monkeypatch, tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)

    (config_dir / "settings.yaml").write_text(
        textwrap.dedent(
            """
            app:
              debug: true
              mock_llm: false
              api_port: 9100
            llm:
              base_url: https://yaml.example/v1
              generation_model: yaml-model
            checker:
              question_history_window: 20
              literal_normalization: false
              fail_open: false
            storage:
              data_dir: yaml-data
              sessions_dir: yaml-data/sessions
              session_db_path: yaml-data/sessions/yaml.sqlite3
              logs_dir: yaml-data/logs
            """
        ).strip(),
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text(
        textwrap.dedent(
            """
            APP__DEBUG=true
            APP__API_PORT=9200
            LLM__BASE_URL=https://dotenv.example/v1
            STORAGE__DATA_DIR=dotenv-data
            """
        ).strip(),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP__DEBUG", "false")
    monkeypatch.setenv("APP__MOCK_LLM", "true")
    monkeypatch.setenv("APP__API_PORT", "9300")
    monkeypatch.setenv("LLM__BASE_URL", "https://env.example/v1")
    monkeypatch.setenv("LLM__GENERATION_MODEL", "env-model")
    monkeypatch.setenv("CHECKER__QUESTION_HISTORY_WINDOW", "50")
    monkeypatch.setenv("CHECKER__LITERAL_NORMALIZATION", "true")
    monkeypatch.setenv("CHECKER__FAIL_OPEN", "true")
    monkeypatch.setenv("STORAGE__DATA_DIR", str(tmp_path / "runtime-data"))
    monkeypatch.setenv(
        "STORAGE__SESSIONS_DIR",
        str(tmp_path / "runtime-data" / "sessions"),
    )
    monkeypatch.setenv(
        "STORAGE__LOGS_DIR",
        str(tmp_path / "runtime-data" / "logs"),
    )
    monkeypatch.setenv(
        "STORAGE__SESSION_DB_PATH",
        str(tmp_path / "runtime-data" / "sessions" / "runtime.sqlite3"),
    )

    settings = load_settings("config/settings.yaml")

    assert settings.app.debug is False
    assert settings.app.mock_llm is True
    assert settings.app.api_port == 9300
    assert settings.llm.base_url == "https://env.example/v1"
    assert settings.llm.generation_model == "env-model"
    assert settings.checker.question_history_window == 50
    assert settings.checker.literal_normalization is True
    assert settings.checker.fail_open is True
    assert settings.storage.data_dir == str(tmp_path / "runtime-data")
    assert settings.storage.sessions_dir == str(tmp_path / "runtime-data" / "sessions")
    assert settings.storage.session_db_path == str(
        tmp_path / "runtime-data" / "sessions" / "runtime.sqlite3"
    )
    assert settings.storage.logs_dir == str(tmp_path / "runtime-data" / "logs")


def test_load_settings_uses_defaults_when_config_file_is_missing(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("STORAGE__DATA_DIR", raising=False)
    monkeypatch.delenv("STORAGE__SESSIONS_DIR", raising=False)
    monkeypatch.delenv("STORAGE__SESSION_DB_PATH", raising=False)
    monkeypatch.delenv("STORAGE__LOGS_DIR", raising=False)

    settings = load_settings("config/settings.yaml")

    assert settings.app.api_port == 8001
    assert settings.checker.question_history_window == 50
    assert settings.storage.sessions_dir == "data/sessions"
    assert settings.storage.session_db_path == "data/sessions/deepquestiontree.sqlite3"


def test_session_manager_uses_environment_overridden_storage_paths(
    monkeypatch, tmp_path
):
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "settings.yaml").write_text(
        textwrap.dedent(
            """
            storage:
              data_dir: data
              sessions_dir: data/sessions
              session_db_path: data/sessions/deepquestiontree.sqlite3
              logs_dir: data/logs
            """
        ).strip(),
        encoding="utf-8",
    )

    expected_sessions_dir = tmp_path / "isolated-data" / "sessions"
    expected_db_path = expected_sessions_dir / "isolated.sqlite3"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("STORAGE__DATA_DIR", str(tmp_path / "isolated-data"))
    monkeypatch.setenv("STORAGE__SESSIONS_DIR", str(expected_sessions_dir))
    monkeypatch.setenv("STORAGE__SESSION_DB_PATH", str(expected_db_path))
    monkeypatch.setenv(
        "STORAGE__LOGS_DIR",
        str(tmp_path / "isolated-data" / "logs"),
    )

    persistence_module._session_manager = None
    reload_settings("config/settings.yaml")
    manager = persistence_module.get_session_manager()

    try:
        assert Path(manager.db_path) == expected_db_path
    finally:
        persistence_module._session_manager = None
