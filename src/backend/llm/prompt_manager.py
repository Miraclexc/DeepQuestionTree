"""
Prompt 管理模块
负责加载、缓存和渲染 Prompt 模板
"""
import os
from pathlib import Path
from typing import Any, Dict

from jinja2 import Template, TemplateError
from yaml import safe_load

from ..config_loader import get_settings


class PromptManager:
    """Prompt 模板管理器"""

    def __init__(self, prompt_file: str = "config/prompts.yaml"):
        """
        初始化 Prompt 管理器

        Args:
            prompt_file: Prompt 配置文件路径
        """
        self.prompt_file = Path(prompt_file)
        self.prompts: Dict[str, str] = {}
        self.settings = get_settings()

        # 加载所有 Prompt
        self._load_prompts()

    def _load_prompts(self) -> None:
        """
        从 YAML 文件加载所有 Prompt 模板
        """
        if not self.prompt_file.exists():
            raise FileNotFoundError(f"Prompt 文件不存在: {self.prompt_file}")

        try:
            with open(self.prompt_file, 'r', encoding='utf-8') as f:
                self.prompts = safe_load(f) or {}
        except Exception as e:
            raise ValueError(f"加载 Prompt 文件失败: {e}") from e

        if not self.prompts:
            raise ValueError("Prompt 文件为空")

    def render(self, prompt_key: str, **kwargs: Any) -> str:
        """
        渲染 Prompt 模板

        Args:
            prompt_key: YAML 中的键名
            **kwargs: 传递给模板的变量

        Returns:
            str: 渲染后的完整 Prompt 字符串

        Raises:
            KeyError: Prompt key 不存在
            TemplateError: 模板渲染错误
        """
        template_str = self.prompts.get(prompt_key)
        if not template_str:
            available_keys = list(self.prompts.keys())
            raise KeyError(
                f"Prompt key '{prompt_key}' 不存在。可用的 keys: {available_keys}"
            )

        try:
            template = Template(template_str)
            rendered = template.render(**kwargs)
            return rendered.strip()
        except TemplateError as e:
            raise TemplateError(f"渲染 Prompt '{prompt_key}' 失败: {e}") from e

    def get_prompt(self, prompt_key: str) -> str:
        """
        获取原始 Prompt 字符串（不渲染）

        Args:
            prompt_key: Prompt 键名

        Returns:
            str: 原始 Prompt 字符串
        """
        if prompt_key not in self.prompts:
            raise KeyError(f"Prompt key '{prompt_key}' 不存在")
        return self.prompts[prompt_key]

    def reload(self) -> None:
        """重新加载 Prompt 文件"""
        self._load_prompts()

    def list_prompts(self) -> Dict[str, str]:
        """
        列出所有可用的 Prompt

        Returns:
            Dict: {prompt_key: prompt_content}
        """
        return self.prompts.copy()

    def validate_prompt(self, prompt_key: str, required_vars: list) -> bool:
        """
        验证 Prompt 是否包含所需的变量

        Args:
            prompt_key: Prompt 键名
            required_vars: 必需的变量名列表

        Returns:
            bool: 是否包含所有必需变量
        """
        if prompt_key not in self.prompts:
            return False

        template_str = self.prompts[prompt_key]
        template = Template(template_str)
        environment = template.environment

        # 检查未定义的变量
        undefined_vars = set(template.parse().find_undeclared_variables(environment))
        required_set = set(required_vars)

        # 检查是否所有必需变量都存在
        return required_set.issubset(undefined_vars)


# 全局 Prompt 管理器实例
_prompt_manager: PromptManager = None


def get_prompt_manager() -> PromptManager:
    """
    获取全局 Prompt 管理器实例

    Returns:
        PromptManager: Prompt 管理器实例
    """
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager