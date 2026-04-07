"""
配置加载器。

配置优先级：
默认值 < config/settings.yaml < 根目录 .env < 进程环境变量
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, field_validator

CONFIG_SECTIONS = {
    "app",
    "llm",
    "mcts",
    "embedding",
    "storage",
    "logging",
    "security",
}


class AppConfig(BaseModel):
    """应用配置"""

    debug: bool = True
    mock_llm: bool = False
    env: str = "development"
    api_port: int = 8001
    frontend_port: int = 3000
    api_host: str = "http://localhost"
    frontend_host: str = "http://localhost"


class LLMConfig(BaseModel):
    """LLM 配置"""

    generation_model: str = "gpt-4o"
    decision_model: str = "gpt-4"
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    timeout: int = 60
    max_retries: int = 3

    @field_validator("api_key", mode="before")
    @classmethod
    def resolve_api_key(cls, value: Any) -> str:
        """解析 API key，兼容未预处理的 ${ENV_VAR} 形式。"""
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            return os.getenv(env_var, "")
        return str(value)


class MCTSConfig(BaseModel):
    """MCTS 配置"""

    max_depth: int = 5
    branch_factor: int = 3
    max_simulations: int = 20
    exploration_constant: float = 1.414
    save_interval_steps: int = 5
    parallel_workers: int = 1


class EmbeddingConfig(BaseModel):
    """嵌入模型配置"""

    use_local: bool = True
    model_path: str = "DMetaSoul/sbert-chinese-general-v2-distill"
    api_model: str = "text-embedding-ada-002"
    similarity_threshold: float = 0.85
    local_files_only: bool = True
    fallback_mode: Literal["hash", "none"] = "hash"


class StorageConfig(BaseModel):
    """存储配置"""

    data_dir: str = "data"
    sessions_dir: str = "data/sessions"
    session_db_path: str = "data/sessions/deepquestiontree.sqlite3"
    logs_dir: str = "data/logs"


class LoggingConfig(BaseModel):
    """日志配置"""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_rotation: str = "daily"
    json_format: bool = False


class SecurityConfig(BaseModel):
    """安全配置"""

    api_token: str = "dev-token"


class Settings(BaseModel):
    """主配置类。"""

    model_config = ConfigDict(extra="ignore")

    app: AppConfig = Field(default_factory=AppConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    mcts: MCTSConfig = Field(default_factory=MCTSConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)


def load_settings(config_path: str | None = None) -> Settings:
    """加载配置文件并应用 .env 与环境变量覆盖。"""
    config_file = Path(config_path or "config/settings.yaml")

    yaml_config = _load_yaml_config(config_file)
    dotenv_path = config_file.parent.parent / ".env"
    dotenv_mapping = _load_dotenv_mapping(dotenv_path)
    dotenv_config = _extract_nested_config(dotenv_mapping)
    env_config = _extract_nested_config(os.environ)

    merged = _deep_merge({}, yaml_config)
    merged = _deep_merge(merged, dotenv_config)
    merged = _deep_merge(merged, env_config)

    placeholder_values = {
        key: value for key, value in dotenv_mapping.items() if value is not None
    }
    placeholder_values.update(os.environ)
    resolved = _resolve_placeholders(merged, placeholder_values)

    settings = Settings.model_validate(resolved)
    _ensure_storage_directories(settings)
    return settings


def _load_yaml_config(config_file: Path) -> dict[str, Any]:
    if not config_file.exists():
        return {}

    try:
        with config_file.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"配置文件格式错误: {exc}") from exc

    if not isinstance(loaded, dict):
        raise ValueError("配置文件顶层必须是对象")

    return loaded


def _load_dotenv_mapping(dotenv_path: Path) -> dict[str, str | None]:
    if not dotenv_path.exists():
        return {}
    return dict(dotenv_values(dotenv_path))


def _extract_nested_config(source: Mapping[str, Any]) -> dict[str, Any]:
    nested_config: dict[str, Any] = {}

    for raw_key, raw_value in source.items():
        if raw_value is None or "__" not in raw_key:
            continue

        path = [part.strip().lower() for part in raw_key.split("__") if part.strip()]
        if len(path) < 2 or path[0] not in CONFIG_SECTIONS:
            continue

        _assign_nested_value(nested_config, path, raw_value)

    return nested_config


def _assign_nested_value(target: dict[str, Any], path: list[str], value: Any) -> None:
    cursor = target
    for key in path[:-1]:
        next_value = cursor.get(key)
        if not isinstance(next_value, dict):
            next_value = {}
            cursor[key] = next_value
        cursor = next_value
    cursor[path[-1]] = value


def _deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, Mapping):
            merged[key] = _deep_merge(existing, value)
        else:
            merged[key] = value
    return merged


def _resolve_placeholders(value: Any, variables: Mapping[str, str]) -> Any:
    if isinstance(value, dict):
        return {
            key: _resolve_placeholders(child, variables) for key, child in value.items()
        }
    if isinstance(value, list):
        return [_resolve_placeholders(child, variables) for child in value]
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_var = value[2:-1]
        return variables.get(env_var, "")
    return value


def _ensure_storage_directories(settings: Settings) -> None:
    Path(settings.storage.data_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.storage.sessions_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.storage.session_db_path).parent.mkdir(parents=True, exist_ok=True)
    Path(settings.storage.logs_dir).mkdir(parents=True, exist_ok=True)


_settings: Settings | None = None


def get_settings() -> Settings:
    """获取全局配置实例。"""
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


def reload_settings(config_path: str | None = None) -> Settings:
    """重新加载配置。"""
    global _settings
    _settings = load_settings(config_path)
    return _settings
