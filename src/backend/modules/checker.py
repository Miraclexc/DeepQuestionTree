"""
核查模块
负责问题审查与事实去重决策。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Literal

from ..config_loader import get_settings
from ..core.schema import Fact
from ..llm.client_interface import BaseLLMClient
from ..llm.prompt_manager import get_prompt_manager
from ..utils.logger import get_logger

logger = get_logger(__name__)

ReviewStage = Literal["pre", "post", "score"]


@dataclass(slots=True)
class QuestionReview:
    score: float = 5.0
    is_duplicate: bool = False
    is_off_topic: bool = False
    is_low_value: bool = False
    should_prune: bool = False
    reason: str | None = None
    explanation: str = ""


@dataclass(slots=True)
class FactDedupePlan:
    replace_existing: dict[str, str] = field(default_factory=dict)
    discard_new: list[str] = field(default_factory=list)
    keep_new: list[str] = field(default_factory=list)


class Checker:
    """统一封装决策模型的核查逻辑。"""

    def __init__(self, llm_client: BaseLLMClient, prompt_manager=None):
        self.llm = llm_client
        self.prompts = prompt_manager or get_prompt_manager()
        self.settings = get_settings()

    async def review_question(
        self,
        *,
        question: str,
        goal: str,
        history_questions: list[str] | None = None,
        parent_question: str = "初始问题",
        known_facts: list[Fact] | None = None,
        current_answer: str = "",
        path_questions: list[str] | None = None,
        recent_values: list[float] | None = None,
        stage: ReviewStage = "pre",
    ) -> QuestionReview:
        question_text = question.strip()
        history_questions = history_questions or []
        known_facts = known_facts or []
        path_questions = path_questions or []
        recent_values = recent_values or []

        if not question_text:
            return QuestionReview()

        if self._is_literal_duplicate(question_text, history_questions):
            return QuestionReview(
                score=0.0,
                is_duplicate=True,
                should_prune=True,
                reason="问题重复",
                explanation="命中字面归一化重复。",
            )

        prompt = self.prompts.render(
            "review_question",
            stage=stage,
            question=question_text,
            goal=goal or "未提供目标",
            parent_question=parent_question or "初始问题",
            history_questions=self._format_text_list(
                history_questions[-self.settings.checker.question_history_window :]
            ),
            known_facts=self._format_fact_list(known_facts),
            current_answer=current_answer or "暂无回答",
            path_questions=self._format_text_list(path_questions[-5:]),
            recent_values=", ".join(f"{value:.2f}" for value in recent_values)
            or "暂无价值统计",
        )

        try:
            response = await self.llm.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_contract="json_object",
                purpose="decision",
            )
            payload = response.structured_content or {}
            if not isinstance(payload, dict):
                payload = {}
            return self._coerce_review(payload, stage=stage)
        except Exception as exc:
            logger.error("问题核查失败: %s", exc)
            if not self.settings.checker.fail_open:
                raise
            return QuestionReview(
                score=5.0,
                explanation="checker unavailable, fail-open fallback",
            )

    async def dedupe_facts(
        self,
        existing_facts: list[Fact],
        new_facts: list[Fact],
    ) -> FactDedupePlan:
        if not new_facts:
            return FactDedupePlan()
        if not existing_facts:
            return FactDedupePlan(keep_new=[fact.id for fact in new_facts])

        prompt = self.prompts.render(
            "dedupe_facts",
            existing_facts=self._format_fact_records(existing_facts),
            new_facts=self._format_fact_records(new_facts),
        )

        try:
            response = await self.llm.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_contract="json_object",
                purpose="decision",
            )
            payload = response.structured_content or {}
            if not isinstance(payload, dict):
                payload = {}
            return self._coerce_dedupe_plan(payload, new_facts, existing_facts)
        except Exception as exc:
            logger.error("事实去重核查失败: %s", exc)
            if not self.settings.checker.fail_open:
                raise
            return FactDedupePlan(keep_new=[fact.id for fact in new_facts])

    def normalize_text(self, text: str) -> str:
        base = text.strip().lower()
        if not self.settings.checker.literal_normalization:
            return base
        return re.sub(r"[\s\W_]+", "", base)

    def _is_literal_duplicate(
        self, question: str, history_questions: Iterable[str]
    ) -> bool:
        normalized_question = self.normalize_text(question)
        if not normalized_question:
            return False
        return any(
            self.normalize_text(item) == normalized_question
            for item in history_questions
        )

    def _format_text_list(self, items: list[str]) -> str:
        if not items:
            return "暂无"
        return "\n".join(f"- {item}" for item in items)

    def _format_fact_list(self, facts: list[Fact]) -> str:
        if not facts:
            return "暂无"
        return "\n".join(f"- {fact.content}" for fact in facts[-20:])

    def _format_fact_records(self, facts: list[Fact]) -> str:
        if not facts:
            return "[]"
        lines = []
        for fact in facts:
            lines.append(
                f'- id="{fact.id}", confidence={fact.confidence:.2f}, content="{fact.content}"'
            )
        return "\n".join(lines)

    def _coerce_review(self, payload: dict, *, stage: ReviewStage) -> QuestionReview:
        score = self._coerce_float(payload.get("score"), default=5.0)
        is_duplicate = self._coerce_bool(payload.get("is_duplicate"))
        is_off_topic = self._coerce_bool(payload.get("is_off_topic"))
        is_low_value = self._coerce_bool(payload.get("is_low_value"))
        should_prune = self._coerce_bool(payload.get("should_prune"))
        explanation = str(payload.get("explanation") or "").strip()
        reason = payload.get("reason")
        if reason is not None:
            reason = str(reason).strip() or None

        if stage == "pre":
            should_prune = should_prune or is_duplicate or is_off_topic
            if is_duplicate:
                reason = "问题重复"
            elif is_off_topic:
                reason = "偏离主题"
            else:
                reason = reason if reason in {"问题重复", "偏离主题"} else None
        elif stage == "post":
            should_prune = should_prune or is_low_value
            if is_low_value:
                reason = "连续低价值路径"
            else:
                reason = reason if reason == "连续低价值路径" else None
        else:
            should_prune = False
            reason = None
            is_duplicate = False
            is_off_topic = False
            is_low_value = False

        return QuestionReview(
            score=max(0.0, min(10.0, score)),
            is_duplicate=is_duplicate,
            is_off_topic=is_off_topic,
            is_low_value=is_low_value,
            should_prune=should_prune,
            reason=reason,
            explanation=explanation,
        )

    def _coerce_dedupe_plan(
        self,
        payload: dict,
        new_facts: list[Fact],
        existing_facts: list[Fact],
    ) -> FactDedupePlan:
        new_ids = {fact.id for fact in new_facts}
        existing_ids = {fact.id for fact in existing_facts}

        raw_replace = payload.get("replace_existing")
        replace_existing: dict[str, str] = {}
        if isinstance(raw_replace, dict):
            for new_id, existing_id in raw_replace.items():
                if (
                    isinstance(new_id, str)
                    and isinstance(existing_id, str)
                    and new_id in new_ids
                    and existing_id in existing_ids
                ):
                    replace_existing[new_id] = existing_id

        discard_new = self._filter_id_list(
            payload.get("discard_new"), allowed_ids=new_ids
        )
        keep_new = self._filter_id_list(payload.get("keep_new"), allowed_ids=new_ids)

        planned_ids = set(replace_existing.keys()) | set(discard_new) | set(keep_new)
        unresolved_ids = [fact.id for fact in new_facts if fact.id not in planned_ids]
        keep_new.extend(unresolved_ids)

        return FactDedupePlan(
            replace_existing=replace_existing,
            discard_new=discard_new,
            keep_new=list(dict.fromkeys(keep_new)),
        )

    def _filter_id_list(self, value: object, *, allowed_ids: set[str]) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str) and item in allowed_ids]

    def _coerce_bool(self, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes"}
        return bool(value)

    def _coerce_float(self, value: object, *, default: float) -> float:
        if not isinstance(value, (int, float, str)):
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
