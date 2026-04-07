# DeepQuestionTree Project Overview

> Last Updated: 2026-04-07
>
> 本页唯一负责：记录当前代码已经落地的真实架构、运行时约束、配置边界、数据流与已知原型边界。

本文描述的是当前仓库中的真实实现，而不是历史设计目标。

## 1. Project Positioning

DeepQuestionTree 当前是单用户原型工作台，不是多租户生产系统。

当前稳定边界：

- 单活跃会话
- 本地 JSON 持久化
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
   └─ modules/persistence.py
        ↓
   data/sessions/*.json
```

### 2.1 Backend modules

| Module | Responsibility | Key Files |
|---|---|---|
| App entry | 创建 FastAPI app、挂载 runtime、注册 middleware 与异常处理 | `src/backend/main.py` |
| API layer | 路由、鉴权依赖、DTO / read-model | `src/backend/api/*` |
| Runtime facade | 向 FastAPI 暴露命令、查询、报告与配置重载能力 | `src/backend/services/runtime.py` |
| Application services | Command / Query / Report / Configuration 服务拆分 | `src/backend/services/*_service.py` |
| Runtime coordinator | 管理单活跃会话、MCTS engine 与后台任务生命周期 | `src/backend/services/coordinator.py` |
| Repository boundary | 将 `SessionManager` 包装成显式应用层仓储 | `src/backend/services/session_repository.py` |
| Core | 领域对象与 MCTS engine | `src/backend/core/*` |
| Domain modules | questioner、compressor、pruner、integrator、persistence | `src/backend/modules/*` |
| LLM / embedding | OpenAI-compatible client、mock client、embedding manager | `src/backend/llm/*` |

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
- 历史会话通过 JSON 仓储恢复

当前并发模型：

- `RuntimeCoordinator` 为活跃 session 持有单独的 commit 通道（`asyncio.Lock`）
- 多个 worker 可以并发执行 `prepare` 阶段的外部调用
- `MCTSEngine` 只在 `reserve` / `commit` 阶段写入 live `SessionData`
- 每次成功提交都会递增 `session_revision`
- 节点 reservation 通过 `processing_token` 标识；过期 proposal 在 commit 时会被拒绝并释放占用
- 查询接口直接读活跃 session，但 commit 临界区内不执行 `await`，因此外部读取只会看到已提交状态

### 3.3 Persistence boundary

持久化分两层：

- `SessionManager` 负责底层 JSON 文件读写与报告缓存
- `JsonSessionRepository` 负责向上提供显式应用层结果和异常

当前仓储接口约束：

- `get_session()`：找不到直接抛 `NotFoundError`
- `delete_session()`：找不到直接抛 `NotFoundError`
- `list_sessions()`：返回 `SessionSummaryRecord`

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

典型来源：

- 后端：`config/settings.yaml`、根 `.env`、进程环境变量
- 前端：`src/frontend/.env.local`

## 5. API And Read-Model Shape

当前统一 API 面只有一套 `/api/*` 路由。旧的 `/api/visualizer/*` 读取接口已移除。

当前前端消费的不是领域对象本身，而是 DTO 层构建的 read-model：

- 节点答案展示通过 `parse_display_answer()` 做输出归一化
- 报告响应通过 `build_report_response()` 保持稳定结构

这使后端内部字段调整不会直接打爆前端展示层。

## 6. Frontend Data Flow

当前前端数据流分四层：

1. `api-client.ts`：统一 base URL、Bearer、错误分发
2. `contracts.ts`：响应归一化
3. hooks：轮询与状态编排
4. 组件：只做展示与交互组合

当前轮询节奏：

- 系统状态：5 秒
- 会话列表：10 秒
- 树数据：2 秒

当前 UI 能力边界：

- 可以创建新探索
- 可以查看历史会话
- 可以查看节点详情
- 可以生成报告或停止后生成报告
- 可以删除会话

当前前端没有显式暴露“从历史会话继续运行探索”的按钮，尽管后端 `POST /api/start` 支持可选 `session_id`。

## 7. Current Boundaries And Gaps

- 不支持多用户并发探索
- 单活跃 session 内已改为“两阶段提交 + 串行 commit”，但并发 prepare 在 revision 变化后仍可能被丢弃重试
- 不引入数据库
- 不引入实时推送
- 仍然采用轮询式工作台
- `config/settings.yaml` 中的默认模型值仍需结合实际部署环境审查
- 浏览器 smoke 只覆盖一条 happy path，不做视觉回归和多浏览器矩阵

## 8. Related Documents

- 接口与鉴权：[`application-layer-and-auth.md`](./application-layer-and-auth.md)
- 用户操作：[`user-guide.md`](./user-guide.md)
- 开发维护：[`developer-guide.md`](./developer-guide.md)
- 测试与验收：[`testing-and-e2e.md`](./testing-and-e2e.md)
