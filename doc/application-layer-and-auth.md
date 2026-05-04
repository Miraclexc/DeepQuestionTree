# Application Layer And Auth

> Last Updated: 2026-05-04
>
> 本页唯一负责：作为统一 API、鉴权规则、错误响应与 read-model 契约的单一事实来源。

本文以当前代码中的真实路由和 DTO 为准。

## 1. Backend Application Layer

后端当前职责拆分如下：

| Layer | Responsibility | Key Files |
|---|---|---|
| Controller | 接收 HTTP 参数、调用应用服务、返回 DTO | `src/backend/api/router.py` |
| Auth dependency | 校验 Bearer Token | `src/backend/api/dependencies.py` |
| DTO / contract | 请求/响应模型定义 | `src/backend/api/dto.py` |
| Read-model builders | session、tree、node、report 响应归一化 | `src/backend/api/read_models.py` |
| Command service | 启动、停止、删除会话 | `src/backend/services/session_command_service.py` |
| Query service | 状态、会话、树、节点查询 | `src/backend/services/session_query_service.py` |
| Report service | 基于会话版本做缓存判定、报告生成与稳定输出 | `src/backend/services/report_service.py` |
| Configuration service | 配置重载与模块重建 | `src/backend/services/configuration_service.py` |
| Runtime coordinator | 活跃会话、MCTS engine、后台任务生命周期 | `src/backend/services/coordinator.py` |
| Runtime facade | 挂到 FastAPI `app.state` 的统一门面 | `src/backend/services/runtime.py` |

## 2. Endpoint Matrix

所有当前公开路由都位于 `/api/*` 下。

| Method | Path | Purpose | Primary Response |
|---|---|---|---|
| `POST` | `/api/start` | 创建新会话或基于 `session_id` 恢复并启动探索 | `StartResponse` |
| `POST` | `/api/stop` | 停止当前活跃探索 | `StopResponse` |
| `GET` | `/api/status` | 返回运行时状态、活跃会话和树统计摘要 | `SystemStatusResponse` |
| `POST` | `/api/config/reload` | 重载后端配置并重建模块 | `MessageResponse` |
| `GET` | `/api/sessions` | 返回会话摘要列表 | `list[SessionSummary]` |
| `GET` | `/api/sessions/{session_id}` | 返回单个会话 read-model | `SessionReadModel` |
| `GET` | `/api/sessions/{session_id}/tree` | 返回树渲染 read-model | `TreeResponse` |
| `GET` | `/api/sessions/{session_id}/nodes/{node_id}` | 返回节点详情 read-model | `NodeDetailResponse` |
| `GET` | `/api/sessions/{session_id}/report` | 返回指定会话报告 | `ReportResponse` |
| `DELETE` | `/api/sessions/{session_id}` | 删除指定会话 | `204 No Content` |

补充说明：

- `POST /api/start` 的请求体支持可选 `session_id`；前端当前通过 `History` 行内 `Resume Session` 动作接入该能力，`New Exploration` 仍只用于创建新会话。
- 若目标 session 属于旧 token 账本（`token_accounting_version=1`），`POST /api/start` 会返回 `409`，错误码固定为 `legacy_session_resume_unsupported`
- `GET /api/sessions/{session_id}/report` 是当前唯一真实报告读取路径；不存在 `/api/report`。

## 3. Authentication

所有 `/api/*` 请求都要求：

```http
Authorization: Bearer <token>
```

后端 Token 来源：

- `config/settings.yaml` 中的 `security.api_token`
- 或环境变量 `SECURITY__API_TOKEN`

前端 Token 提供顺序：

1. `localStorage["dqt.apiToken"]`
2. `NEXT_PUBLIC_API_TOKEN`
3. 默认回退 `dev-token`

浏览器调试命令：

```js
localStorage.setItem("dqt.apiToken", "dev-token");
```

## 4. Error Response Contract

应用层异常定义在 [`../src/backend/services/errors.py`](../src/backend/services/errors.py)，FastAPI 全局异常处理注册在 [`../src/backend/main.py`](../src/backend/main.py)。

统一错误 shape：

```json
{
  "detail": "human readable message",
  "code": "machine_readable_code"
}
```

请求校验错误额外返回：

```json
{
  "detail": "Request validation failed",
  "code": "request_validation_error",
  "errors": []
}
```

当前常见异常类别：

- `AuthError` -> `401` 或 `403`
- `NotFoundError` -> `404`
- `RuntimeConflictError` -> `409`
- `ConfigurationError` -> `500`
- `PersistenceError` -> `500`
- `ReportGenerationError` -> `500`

补充语义：

- 当真实 provider 配置缺失或非法时，`POST /api/start` 会在模块装配前失败，并返回 `code=configuration_error`
- 当旧账本 session 尝试恢复时，`POST /api/start` 返回 `409` 且 `code=legacy_session_resume_unsupported`
- 协调器、MCTS 主循环或持久化边界发生致命异常时，活跃会话会被置为 `error`，并写入 `error_message`
- 恢复会话时会清空旧的 `error_message`

## 5. Stable Read-Model Contracts

### 5.1 Session, tree and node responses

前端消费的是 DTO read-model，而不是领域对象原型：

- `SessionReadModel`
- `TreeResponse`
- `NodeDetailResponse`

模型定义由 [`../src/backend/api/dto.py`](../src/backend/api/dto.py) 负责；响应组装和兼容归一化由 [`../src/backend/api/read_models.py`](../src/backend/api/read_models.py) 负责。

当前新增的轻量同步字段：

- `SystemStatusResponse.session_revision`
- `SystemStatusResponse.session_error_message`
- `TreeResponse.session_revision`
- `SessionSummary.is_legacy_token_accounting`
- `SessionReadModel.is_legacy_token_accounting`

这些字段用于前端的轻量状态轮询：先轮询 `/api/status`，只有 revision 变化时才重新请求树。

### 5.2 Report response

报告接口始终返回 `ReportResponse`，即使报告生成失败也不切换到另一种 shape。

固定核心字段：

- `session_id`
- `goal`
- `executive_summary`
- `full_report`
- `key_insights`
- `pruned_insights`
- `statistics`
- `llm_stats`
- `suggestions`
- `generated_at`
- `error_message`

旧缓存或失败载荷都会通过 `src/backend/api/read_models.py` 中的 `build_report_response()` 归一化。

`pruned_insights` 的当前语义是“独立诊断 read-model”：

- 前端继续通过单独的 `Pruned Paths` 标签页展示它
- 后端报告正文生成 prompt 不接收剪枝摘要
- `executive_summary` 与 `full_report` 只基于事实、主路径和关键见解生成

当前报告 freshness 语义：

- `GET /api/sessions/{session_id}/report` 会先拍当前会话快照，再判断是否存在同版本缓存
- 只有当缓存的 `source_session_version` 等于当前 `session.session_version` 时才会直接返回缓存
- 如果会话在报告生成期间继续推进，本次响应仍可返回，但不会覆盖最新版本的缓存
- 若 session 属于旧 token 账本且当前版本没有缓存报告，接口仍返回 `200 + ReportResponse`，但只填稳定错误字段，不再触发新的 LLM 报告生成

`SessionReadModel.report_available` 当前表示“该会话当前版本存在可复用报告”，不再表示“历史上生成过某份报告”。

当前 token 统计语义：

- `ReportResponse.llm_stats` 来自会话级 usage ledger，而不是节点 `interaction.tokens_used` 求和
- `session.total_tokens_used` 镜像整场会话的累计 LLM 消耗
- 节点 `interaction.tokens_used` 只保留节点回答和事实抽取的局部消耗

## 6. Frontend Request Layer

前端请求边界分为两层：

| Module | Responsibility |
|---|---|
| `src/frontend/lib/api-client.ts` | 拼接 base URL、注入 Bearer、归一化 HTTP 错误分发 |
| `src/frontend/lib/contracts.ts` | 把后端响应转换成前端稳定类型 |

这意味着：

- 如果后端字段名调整，优先改 `contracts.ts`
- 如果路由、鉴权或响应 shape 调整，必须同步更新本页

## 7. Related Documents

- 真实架构与边界：[`project-overview.md`](./project-overview.md)
- 用户操作说明：[`user-guide.md`](./user-guide.md)
- 项目级测试与验收：[`testing-and-e2e.md`](./testing-and-e2e.md)
