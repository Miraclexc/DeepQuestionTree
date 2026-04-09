# LLM Structured Output Contract

> Last Updated: 2026-04-08
>
> 本页唯一负责：定义后端 LLM 调用的结构化输出契约、调用方映射、provider 边界、异常与 fallback 语义。

## 1. Contract Types

当前 `BaseLLMClient.chat_completion()` 不再使用布尔 `json_mode`，而是声明显式 `response_contract`：

| Contract | Intended shape | Provider enforcement | Client validation |
|---|---|---|---|
| `text` | 普通文本 | 无 | 不做 JSON 解析 |
| `json_object` | 顶层 JSON 对象 | `response_format={"type":"json_object"}` | 校验顶层必须为对象 |
| `json_array` | 顶层 JSON 数组 | 不向 provider 声明 `json_object` | 客户端 `json.loads()` 后校验顶层必须为数组 |

约束：

- `json_object` 只用于明确要求对象形状的调用。
- `json_array` 依赖 Prompt 明确要求数组，并由客户端兜底校验顶层形状。
- `PromptManager` 使用 Jinja `StrictUndefined`；缺模板变量或缺 key 会直接抛错，视为配置问题而不是普通模型噪声。

## 2. Callsite Matrix

当前后端调用与契约映射如下：

| Caller | Prompt / behavior | Contract | Expected payload |
|---|---|---|---|
| `Questioner.generate_candidates()` | 生成后续问题 | `json_array` | `list[str]` |
| `Checker.review_question()` | 统一执行问题预审、路径复核和价值打分 | `json_object` | `{"score": ..., "is_duplicate": ..., "reason": ...}` |
| `Questioner.evaluate_question_value()` | 通过 `Checker.review_question(stage="score")` 复用价值打分，不再单独维护 prompt | `json_object` | 同 `QuestionReview` 载荷 |
| `Checker.dedupe_facts()` | 生成事实合并计划 | `json_object` | `{"replace_existing": ..., "discard_new": ..., "keep_new": ...}` |
| `Questioner.answer_question()` | 生成回答 | `text` | 普通文本 |
| `Compressor.extract_facts()` | 提取事实 | `json_array` | `list[{"content": ..., "confidence": ...}]` |
| `Integrator._extract_key_insights()` | 提取关键见解 | `json_array` | `list[str]` |
| `Integrator._suggest_next_steps()` | 建议后续步骤 | `json_array` | `list[str]` |
| 报告 / 摘要 / 剪枝摘要 | 长文本生成 | `text` | 普通文本 |

## 3. Provider Boundary

当前实现继续基于 `chat.completions`：

- 默认真实 provider 是 Deepseek，但运行时接口仍保持通用 `LLM__*` 配置与 OpenAI-compatible client。
- 不引入 provider 专属 `json_schema` 或 Responses API。
- `json_object` 可以使用通用兼容层的对象强约束。
- `json_array` 在 OpenAI-compatible 生态中没有统一强约束，因此由 Prompt + 客户端校验共同保证。

这意味着：

- provider 若返回非 JSON 文本，客户端会抛出契约异常；
- provider 若返回 JSON 但顶层形状错误（例如对象替代数组），客户端也会抛出契约异常；
- 这类错误被视为“契约错误”，不再作为普通解析噪声静默吞掉。

## 4. Exceptions And Fallbacks

客户端会在结构化调用中抛出 `StructuredOutputContractError`，用于区分：

- provider / 模型没有遵守声明的响应形状；
- 业务代码自身的后续处理错误。

业务层 fallback 规则：

- `Questioner.generate_candidates()`：失败时回退到默认问题列表。
- `Checker.review_question()`：在 `CHECKER__FAIL_OPEN=true` 时回退到 fail-open 结果。
- `Checker.dedupe_facts()`：在 `CHECKER__FAIL_OPEN=true` 时保留全部新事实。
- `Compressor.extract_facts()`：失败时回退到规则提取事实。
- `Integrator._suggest_next_steps()`：失败时回退到内置建议。
- `Integrator._extract_key_insights()`：失败时返回空列表。

禁止的旧行为：

- 不能再把 `json_array` 请求伪装成 `json_object`。
- 不能再在多个调用方里重复做“先收文本，再猜是对象还是数组”的散落解析。

## 5. Extension Rules

新增结构化调用时遵守以下规则：

1. 先决定顶层形状是 `json_object` 还是 `json_array`，不要复用模糊布尔标记。
2. Prompt 中必须把目标形状写死，并给出最小示例。
3. 在模块层只消费 `CompletionResponse.structured_content`，不要重复 `json.loads()`。
4. 同步更新：
   - `src/backend/llm/client_interface.py`
   - 相关模块测试
   - 本文档
5. 若新增真实 provider 验证路径，同时补 `tests/e2e/` 中的 contract smoke。
