from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator

from ..core.schema import SessionLlmUsage


class LlmUsageRecorder:
    """请求作用域内的 LLM 使用统计收集器。"""

    def __init__(self) -> None:
        self._usage = SessionLlmUsage()

    def record(self, model: str, tokens: int, *, calls: int = 1) -> None:
        self._usage.record(model, tokens, calls=calls)

    def snapshot(self) -> SessionLlmUsage:
        return self._usage.model_copy(deep=True)


_active_usage_recorder: ContextVar[LlmUsageRecorder | None] = ContextVar(
    "active_llm_usage_recorder",
    default=None,
)


@contextmanager
def bind_usage_recorder(recorder: LlmUsageRecorder) -> Iterator[LlmUsageRecorder]:
    """将 recorder 绑定到当前异步上下文。"""
    token: Token[LlmUsageRecorder | None] = _active_usage_recorder.set(recorder)
    try:
        yield recorder
    finally:
        _active_usage_recorder.reset(token)


def get_active_usage_recorder() -> LlmUsageRecorder | None:
    return _active_usage_recorder.get()


def record_usage_for_current_request(model: str, tokens: int, *, calls: int = 1) -> None:
    """向当前请求上下文中的 recorder 追加使用统计。"""
    recorder = get_active_usage_recorder()
    if recorder is None:
        return
    recorder.record(model, tokens, calls=calls)
