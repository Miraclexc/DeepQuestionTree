# DeepQuestionTree Project Overview

> Last Updated: 2026-05-04
>
> 本页唯一负责：记录当前代码已经落地的真实架构、运行时约束、配置边界、数据流与已知原型边界。

本文描述的是当前仓库中的真实实现，而不是历史设计目标。

## 1. Project Positioning

DeepQuestionTree 当前是单用户原型工作台，不是多租户生产系统。

当前稳定边界：

- 单活跃会话
- 本地 SQLite 持久化
- 前后端同仓库但配置边界分离
- 无数据库、任务队列、WebSocket 或实时协作

## 2. High-Level Architecture

```text
Frontend (Next.js)
   ├─ components/
   ├─ hooks/
   └─ lib/
        ↓ HTTP
Backend (FastAPI app factory)
   ├─ api/router.py
   ├─ services/runtime.py
   ├─ services/*_service.py
   ├─ services/coordinator.py
   ├─ core/mcts_engine.py
   ├─ modules/*
   └─ infrastructure/session_store.py
        ↓
   data/sessions/deepquestiontree.sqlite3
```

### 2.1 Backend modules

| Module | Responsibility | Key Files |
|---|---|---|
| App entry | 创建 FastAPI app、挂载 runtime、注册 middleware 与异常处理 | `src/backend/main.py` |
| API layer | 路由、鉴权依赖、DTO 与 read-model 组装 | `src/backend/api/*` |
| Runtime facade | 向 FastAPI 暴露命令、查询、报告与配置重载能力 | `src/backend/services/runtime.py` |
| Application services | Command / Query / Report / Configuration 服务拆分 | `src/backend/services/*_service.py` |
| Runtime coordinator | 管理单活跃会话、MCTS engine 与后台任务生命周期 | `src/backend/services/coordinator.py` |
| Repository boundary | 将 SQLite `SessionManager` 包装成显式应用层仓储 | `src/backend/services/session_repository.py` |
| Core | 领域对象与 MCTS engine | `src/backend/core/*` |
| Domain modules | checker、questioner、compressor、pruner、integrator | `src/backend/modules/*` |
| Infrastructure | SQLite 会话库与报告缓存 adapter；`modules/persistence.py` 仅保留兼容导入 | `src/backend/infrastructure/session_store.py` |
| LLM / checker | OpenAI-compatible client（默认真实 provider 为 DeepSeek V4 Preview）、mock client、基于 `purpose` 的模型路由、结构化输出契约 | `src/backend/llm/*` |

### 2.2 Frontend modules

| Module | Responsibility | Key Files |
|---|---|---|
| App shell | 挂载主工作台 | `src/frontend/app/page.tsx` |
| Workspace shell | 组合 Sidebar、WorkspaceHeader、TreeCanvas、NodePanel、ReportView | `src/frontend/components/DeepQuestionTree.tsx` |
| Hooks | 轮询、会话命令、节点详情、报告状态、全局错误 | `src/frontend/hooks/*` |
| Request layer | API client、contracts、共享类型 | `src/frontend/lib/*` |

## 3. Runtime Model

### 3.1 App startup

启动时：

1. `create_app()` 创建 FastAPI 应用
2. `application.state.runtime = ExplorationRuntime()`
3. `lifespan` 在关闭时调用 `runtime.shutdown()`

这意味着运行时状态不依赖 `main.py` 的模块级全局变量。

### 3.2 Single active session

单活跃会话约束由 [`../src/backend/services/coordinator.py`](../src/backend/services/coordinator.py) 明确表达：

- `single_session_mode = True`
- `_active_session`
- `_mcts_engine`
- `_mcts_task`
- `_mcts_running`

当前行为：

- 新会话启动前，如果已有运行中的会话，会先把旧会话停到 `paused`
- 活跃会话保留在运行时内存中，便于高频读写
- 历史会话通过 SQLite 仓储恢复
- 致命 worker / engine / persistence 异常会把活跃会话置为 `error`，写入 `error_message`
- 恢复会话时会清空旧错误，并重新进入 `running`

当前并发模型：

- `RuntimeCoordinator` 为活跃 session 持有单独的 commit 通道（`asyncio.Lock`）
- 多个 worker 可以并发执行 `prepare` 阶段的外部调用
- `MCTSEngine` 只在 `reserve` / `commit` 阶段写入 live `SessionData`
- 每次成功提交都会递增 `session_revision`
- 节点 reservation 通过 `processing_token` 标识；过期 proposal 在 commit 时会被拒绝并释放占用
- 查询接口直接读活跃 session，但 commit 临界区内不执行 `await`，因此外部读取只会看到已提交状态

### 3.3 Persistence boundary

持久化分两层：

- `SessionManager` 位于 `src/backend/infrastructure/session_store.py`，负责底层 SQLite 表读写与报告缓存
- `SqliteSessionRepository` 负责向上提供显式应用层结果和异常
- `src/backend/modules/persistence.py` 只作为旧导入兼容层保留，不再承载真实实现

当前仓储接口约束：

- `get_session()`：找不到直接抛 `NotFoundError`
- `delete_session()`：找不到直接抛 `NotFoundError`
- `list_sessions()`：返回 `SessionSummaryRecord`
- 报告缓存只在 `source_session_version == session.session_version` 时命中
- `SessionManager` 保存时会根据 `(session_revision, session_version, tokens, simulations, status)` 跳过重复快照
- 旧会话（`token_accounting_version=1`）加载时会根据节点 `interaction.tokens_used` 自动校准 `total_tokens_used`
- 新会话（`token_accounting_version=2`）持久化独立 `llm_usage` 账本；`session.total_tokens_used` 只是 `llm_usage.total_tokens` 的兼容镜像
- 当前活跃持久化边界以 `data/sessions/deepquestiontree.sqlite3` 为主；旧 `data/sessions/*.json` 快照已不再参与真实运行链路

## 4. Configuration Boundary

后端配置优先级：

```text
代码默认值 < config/settings.yaml < 根目录 .env < 进程环境变量
```

当前实现约束：

- 所有覆盖统一使用 `SECTION__FIELD`
- 先收集并深度合并，再由 `Settings` 做一次性校验
- 后端不读取 `src/frontend/.env.local`
- 前端只读取自己的 `NEXT_PUBLIC_*`
- 默认样板保持真实 provider 优先；离线 mock 另见根目录 `.env.mock.example`
- 默认真实 provider 为 DeepSeek V4 Preview，仍只通过 `LLM__*` 配置覆盖
- 默认 `LLM__BASE_URL=https://api.deepseek.com`
- 默认 `LLM__GENERATION_MODEL=deepseek-v4-pro`、`LLM__DECISION_MODEL=deepseek-v4-pro`
- 默认 generation 链路发送 `extra_body={"thinking":{"type":"disabled"}}`；decision 链路发送 `extra_body={"thinking":{"type":"enabled"}}` 并使用顶层 `reasoning_effort="high"`
- `deepseek-chat` / `deepseek-reasoner` 是旧兼容别名，官方停用窗口为 2026-07-24；系统不会自动 fallback 到别的模型

典型来源：

- 后端：`config/settings.yaml`、根 `.env`、进程环境变量
- 前端：`src/frontend/.env.local`

关键持久化配置：

- `storage.sessions_dir`：SQLite 文件所在目录
- `storage.session_db_path`：默认 `data/sessions/deepquestiontree.sqlite3`

### 4.1 LLM structured-output boundary

后端 LLM 层当前不再暴露布尔 JSON 模式，而是显式区分三种响应契约：

- `text`
- `json_object`
- `json_array`

当前真实边界：

- `chat_completion(..., purpose="generation" | "decision")` 显式声明调用目的；
- `purpose="decision"` 固定走 `llm.decision_model`，并按 `llm.decision_thinking` 控制 DeepSeek thinking 开关，按顶层 `llm.decision_reasoning_effort` 控制推理强度；
- `json_object` 通过 OpenAI-compatible `response_format={"type":"json_object"}` 约束；
- `json_array` 不依赖 provider 的对象模式，而是由 Prompt 明确数组格式，再由客户端校验顶层必须是数组；
- 业务模块只消费解析后的结构化载荷，不再在多个模块里重复 `json.loads()`。
- `PromptManager` 使用单一 Jinja `Environment` + `StrictUndefined`；缺 key 或缺参都会直接失败，而不是静默渲染空字符串。

### 4.2 Checker boundary

当前问题剪枝和事实合并统一走 checker 链路：

- `checker.review_question()`：支持 `pre` / `post` / `score`
- `checker.dedupe_facts()`：一次性输出事实合并计划
- `pruner` 只保留编排职责与确定性规则（最大深度、事实饱和）
- `compressor.merge_facts()` 先做字面归一化短路，再做单次批量核查

结构化调用的唯一细则见 [`llm-structured-output-contract.md`](./llm-structured-output-contract.md)。

## 5. API And Read-Model Shape

当前统一 API 面只有一套 `/api/*` 路由。

当前前端消费的不是领域对象本身，而是 API 层构建的 read-model：

- `src/backend/api/dto.py` 只定义公开请求/响应模型
- `src/backend/api/read_models.py` 负责 `parse_display_answer()`、树/节点/session read-model 与 `build_report_response()` 归一化
- `pruned_insights` 作为独立诊断视图字段保留，但不进入报告正文 prompt，也不混入 `full_report` / `executive_summary`

这使后端内部字段调整不会直接打爆前端展示层。

当前 token 统计边界：

- `session.total_tokens_used` 不再只从节点回答反推，而是镜像整场会话的 `llm_usage.total_tokens`
- 节点 `interaction.tokens_used` 只表示该节点的“回答 + 事实抽取”局部消耗
- `llm_stats` 来自会话级 usage ledger，因此会覆盖问题生成、checker 决策、候选问题打分和报告生成
- legacy session 只允许查看/删除；没有当前版本缓存报告时不会再触发新的报告生成

## 6. Frontend Data Flow

当前前端数据流分四层：

1. `api-client.ts`：统一 base URL、Bearer、错误分发
2. `contracts.ts`：响应归一化
3. hooks：轮询与状态编排
4. 组件：只做展示与交互组合

当前轮询节奏：

- 系统状态：5 秒
- 会话列表：10 秒
- 树数据：不再固定轮询；仅在 `session_revision` 变化时刷新

当前 UI 能力边界：

- 可以创建新探索
- 可以查看历史会话
- 可以从 `History` 恢复 `paused` / `completed` / `error` 会话
- 可以查看节点详情
- 可以生成报告或停止后生成报告
- 可以删除会话
- 恢复会话时会关闭当前节点详情和报告视图，回到树工作台
- 当前树画布在拓扑不变时复用 Dagre 位置，只更新节点 payload

## 7. Current Boundaries And Gaps

- 不支持多用户并发探索
- 单活跃 session 内已改为“两阶段提交 + 串行 commit”，但并发 prepare 在 revision 变化后仍可能被丢弃重试
- 不引入外部数据库服务
- 不引入实时推送
- 仍然采用轮询式工作台
- 默认真实 provider 为 DeepSeek V4 Preview；其他 OpenAI-compatible 部署仍通过 `LLM__*` 手工覆盖
- 浏览器 smoke 覆盖创建、停止/报告、恢复和继续工作台的主干链路，但不做视觉回归和多浏览器矩阵

## 8. Related Documents

- 接口与鉴权：[`application-layer-and-auth.md`](./application-layer-and-auth.md)
- 用户操作：[`user-guide.md`](./user-guide.md)
- 开发维护：[`developer-guide.md`](./developer-guide.md)
- 测试与验收：[`testing-and-e2e.md`](./testing-and-e2e.md)
