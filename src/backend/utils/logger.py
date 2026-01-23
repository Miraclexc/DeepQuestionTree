"""
日志封装模块
提供统一的日志记录接口，支持控制台和文件输出，支持 JSON 格式和上下文追踪
"""
import logging
import logging.handlers
import sys
import json
import uuid
from pathlib import Path
from typing import Optional, Dict, Any
from contextvars import ContextVar

from ..config_loader import get_settings

# 上下文变量，用于追踪请求 ID
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")
session_id_ctx: ContextVar[str] = ContextVar("session_id", default="")


class JSONFormatter(logging.Formatter):
    """JSON 日志格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }

        # 添加上下文信息
        req_id = request_id_ctx.get()
        if req_id:
            log_data["request_id"] = req_id
            
        sess_id = session_id_ctx.get()
        if sess_id:
            log_data["session_id"] = sess_id

        # 处理异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # 添加额外字段
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)

        return json.dumps(log_data, ensure_ascii=False)


class ContextFilter(logging.Filter):
    """上下文过滤器，注入 request_id 等信息"""

    def filter(self, record):
        record.request_id = request_id_ctx.get()
        record.session_id = session_id_ctx.get()
        return True


class LLMTraceLogger:
    """专门的 LLM 调用日志记录器"""

    def __init__(self):
        """初始化 LLM Trace 日志记录器"""
        self.logger = logging.getLogger("llm_trace")
        self._setup()

    def _setup(self) -> None:
        """设置日志记录器"""
        self.logger.setLevel(logging.DEBUG)

        # 避免重复添加处理器
        if self.logger.handlers:
            return

        settings = get_settings()
        log_dir = Path(settings.storage.logs_dir)
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
            
        # 生成带时间戳的文件名：llm_trace_YYYY-MM-DD_HH-MM-SS.log
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_file = log_dir / f"llm_trace_{timestamp}.log"

        # 使用 FileHandler 记录本次运行的日志
        file_handler = logging.FileHandler(
            filename=log_file,
            encoding="utf-8"
        )
        
        # LLM Trace logs are usually large text blobs, keep them readable (not JSON) by default
        file_formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.DEBUG)
        self.logger.addHandler(file_handler)

    def log_request(
        self,
        messages: list,
        temperature: float,
        model: str,
        json_mode: bool = False
    ) -> str:
        """记录 LLM 请求"""
        req_id = str(uuid.uuid4())[:8]

        log_msg = f"[{req_id}] REQUEST\n"
        log_msg += f"Model: {model}\n"
        log_msg += f"Temperature: {temperature}\n"
        log_msg += f"JSON Mode: {json_mode}\n"
        log_msg += f"Messages:\n"

        for i, msg in enumerate(messages):
            log_msg += f"  {i+1}. Role: {msg['role']}\n"
            log_msg += f"     Content: {msg['content'][:500]}...\n" # Truncate for log safety

        self.logger.info(log_msg)
        return req_id

    def log_response(
        self,
        request_id: str,
        response: str,
        tokens_used: Optional[int] = None,
        error: Optional[str] = None
    ) -> None:
        """记录 LLM 响应"""
        log_msg = f"[{request_id}] RESPONSE\n"

        if error:
            log_msg += f"ERROR: {error}\n"
        else:
            log_msg += f"Response: {response[:500]}...\n"
            if tokens_used:
                log_msg += f"Tokens Used: {tokens_used}\n"

        self.logger.info(log_msg)


# 全局日志记录器实例
_llm_logger: Optional[LLMTraceLogger] = None


def get_llm_logger() -> LLMTraceLogger:
    """获取 LLM Trace 日志记录器"""
    global _llm_logger
    if _llm_logger is None:
        _llm_logger = LLMTraceLogger()
    return _llm_logger


def setup_logging():
    """设置主日志记录器"""
    try:
        settings = get_settings()
        level_str = settings.logging.level.upper()
        log_dir = Path(settings.storage.logs_dir)
        use_json = getattr(settings.logging, "json_format", False)
    except Exception:
        # Fallback defaults
        level_str = "INFO"
        log_dir = Path("data/logs")
        use_json = False

    level = getattr(logging, level_str, logging.INFO)
    
    # 根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 清除现有处理器（防止重载时重复）
    if root_logger.handlers:
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

    # 1. 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    if use_json:
        console_formatter = JSONFormatter()
    else:
        # 增强的可读格式，包含 Request ID
        console_formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - [%(name)s] - %(message)s"
        )
    
    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(ContextFilter())
    root_logger.addHandler(console_handler)

    # 2. 文件处理器
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成带时间戳的文件名：backend_log_YYYY-MM-DD_HH-MM-SS.log
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_file = log_dir / f"backend_log_{timestamp}.log"

        # 使用 FileHandler 记录本次运行的日志
        file_handler = logging.FileHandler(
            filename=log_file,
            encoding="utf-8"
        )
        file_handler.setLevel(level)
        
        if use_json:
            file_formatter = JSONFormatter()
        else:
            file_formatter = logging.Formatter(
                "%(asctime)s - %(levelname)s - [%(name)s] - %(message)s"
            )
            
        file_handler.setFormatter(file_formatter)
        file_handler.addFilter(ContextFilter())
        root_logger.addHandler(file_handler)
        
    except Exception as e:
        print(f"Failed to setup file logging: {e}")

    # 设置第三方库日志级别
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    logging.info("Logging system initialized")


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的日志记录器"""
    return logging.getLogger(name)