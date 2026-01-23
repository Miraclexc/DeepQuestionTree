"""
配置加载器
负责加载和合并配置文件与环境变量
"""
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseModel, Field, ConfigDict, field_validator
from pydantic_settings import BaseSettings



def load_frontend_env() -> Dict[str, str]:
    """
    读取前端 .env.local 文件并加载端口配置
    """
    env_path = Path("src/frontend/.env.local")
    env_vars = {}
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, val = line.strip().split('=', 1)
                    env_vars[key.strip()] = val.strip()
    return env_vars


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

    @field_validator('api_key', mode='before')
    @classmethod
    def resolve_api_key(cls, v: Any) -> str:
        """解析 API key，支持环境变量"""
        if isinstance(v, str) and v.startswith('${') and v.endswith('}'):
            env_var = v[2:-1]
            return os.getenv(env_var, "")
        return str(v)


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


class StorageConfig(BaseModel):
    """存储配置"""
    data_dir: str = "data"
    sessions_dir: str = "data/sessions"
    logs_dir: str = "data/logs"


class LoggingConfig(BaseModel):
    """日志配置"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_rotation: str = "daily"
    json_format: bool = False


class Settings(BaseSettings):
    """主配置类"""
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore"
    )

    app: AppConfig = Field(default_factory=AppConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    mcts: MCTSConfig = Field(default_factory=MCTSConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def load_settings(config_path: Optional[str] = None) -> Settings:
    """
    加载配置文件并覆盖环境变量
    """
    if config_path is None:
        config_path = "config/settings.yaml"

    config_file = Path(config_path)

    # 尝试加载 YAML 配置文件
    config_dict: Dict[str, Any] = {}

    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_dict = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"配置文件格式错误: {e}") from e
    else:
        # 如果配置文件不存在，使用默认配置
        print(f"警告: 配置文件 {config_path} 不存在，使用默认配置")

    # 加载前端环境配置以覆盖端口
    frontend_env = load_frontend_env()
    
    # 手动注入到 config_dict 中
    if 'app' not in config_dict:
        config_dict['app'] = {}
    
    # 将前端 env 映射到 app config
    if 'NEXT_PUBLIC_API_PORT' in frontend_env:
        try:
            config_dict['app']['api_port'] = int(frontend_env['NEXT_PUBLIC_API_PORT'])
        except ValueError:
            pass
            
    if 'NEXT_PUBLIC_FRONTEND_PORT' in frontend_env:
        try:
            config_dict['app']['frontend_port'] = int(frontend_env['NEXT_PUBLIC_FRONTEND_PORT'])
        except ValueError:
            pass

    if 'NEXT_PUBLIC_API_HOST' in frontend_env:
        config_dict['app']['api_host'] = frontend_env['NEXT_PUBLIC_API_HOST']
        
    if 'NEXT_PUBLIC_FRONTEND_HOST' in frontend_env:
        config_dict['app']['frontend_host'] = frontend_env['NEXT_PUBLIC_FRONTEND_HOST']

    # Pydantic 的 BaseSettings 会自动处理环境变量覆盖
    settings = Settings(**config_dict)

    # 创建必要的目录
    Path(settings.storage.data_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.storage.sessions_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.storage.logs_dir).mkdir(parents=True, exist_ok=True)

    return settings


# 全局配置实例（单例模式）
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """获取全局配置实例"""
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


def reload_settings(config_path: Optional[str] = None) -> Settings:
    """重新加载配置"""
    global _settings
    _settings = load_settings(config_path)
    return _settings
