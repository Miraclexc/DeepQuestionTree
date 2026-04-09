from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from jinja2 import TemplateError

from src.backend.llm.prompt_manager import PromptManager

ACTIVE_PROMPT_FIXTURES: dict[str, dict[str, object]] = {
    "generate_questions": {
        "goal": "评估储能政策影响",
        "parent_question": "现有政策有哪些约束？",
        "current_answer": "当前已有部分政策分析。",
        "context_facts": "- 政策 A\n- 政策 B",
        "k": 3,
    },
    "review_question": {
        "stage": "pre",
        "goal": "评估储能政策影响",
        "parent_question": "现有政策有哪些约束？",
        "question": "补贴退出后会发生什么？",
        "history_questions": "- 过去问过的问题",
        "known_facts": "- 已知事实",
        "current_answer": "暂无回答",
        "path_questions": "- 路径问题",
        "recent_values": "6.0, 7.0",
    },
    "dedupe_facts": {
        "existing_facts": '- id="fact-1", confidence=0.90, content="已有事实"',
        "new_facts": '- id="fact-2", confidence=0.95, content="新事实"',
    },
    "extract_facts": {
        "text": "这是需要抽取事实的回答。",
    },
    "summarize_pruned_path": {
        "qa_text": "Q: 问题\nA: 回答",
        "context_note": "该路径因低价值被剪枝。",
    },
    "generate_report": {
        "goal": "评估储能政策影响",
        "facts": "- 事实 1",
        "main_paths": "- 路径 1",
        "key_insights": "- 见解 1",
    },
    "extract_key_insights": {
        "facts_text": "- 事实 1\n- 事实 2",
    },
    "suggest_next_steps": {
        "goal": "评估储能政策影响",
        "facts_summary": "- 事实概览",
    },
    "generate_executive_summary": {
        "goal": "评估储能政策影响",
        "report_content": "报告正文",
    },
    "process_node_answer": {
        "goal": "评估储能政策影响",
        "facts_text": "- 已知事实",
        "question": "下一步需要验证什么？",
    },
}


def test_prompt_manager_real_prompt_keys_match_active_callsites():
    manager = PromptManager()

    assert set(manager.list_prompts().keys()) == set(ACTIVE_PROMPT_FIXTURES.keys())


@pytest.mark.parametrize(
    ("prompt_key", "kwargs"),
    ACTIVE_PROMPT_FIXTURES.items(),
)
def test_prompt_manager_renders_each_active_prompt(
    prompt_key: str, kwargs: dict[str, object]
):
    manager = PromptManager()

    rendered = manager.render(prompt_key, **kwargs)

    assert isinstance(rendered, str)
    assert rendered.strip()


def test_prompt_manager_missing_key_raises_key_error(tmp_path: Path):
    prompt_file = tmp_path / "prompts.yaml"
    prompt_file.write_text("known: |\n  hello\n", encoding="utf-8")
    manager = PromptManager(prompt_file=str(prompt_file))

    with pytest.raises(KeyError):
        manager.render("missing")


def test_prompt_manager_missing_variable_raises_template_error(tmp_path: Path):
    prompt_file = tmp_path / "prompts.yaml"
    prompt_file.write_text("sample: |\n  hello {{ name }}\n", encoding="utf-8")
    manager = PromptManager(prompt_file=str(prompt_file))

    with pytest.raises(TemplateError):
        manager.render("sample")


def test_prompt_manager_reload_refreshes_templates(tmp_path: Path):
    prompt_file = tmp_path / "prompts.yaml"
    prompt_file.write_text(
        textwrap.dedent(
            """
            sample: |
              hello {{ name }}
            """
        ).strip(),
        encoding="utf-8",
    )
    manager = PromptManager(prompt_file=str(prompt_file))

    assert manager.render("sample", name="world") == "hello world"

    prompt_file.write_text(
        textwrap.dedent(
            """
            sample: |
              hi {{ name }}
            """
        ).strip(),
        encoding="utf-8",
    )

    manager.reload()

    assert manager.render("sample", name="world") == "hi world"
