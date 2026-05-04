# DeepQuestionTree

> Last Updated: 2026-05-04
>
> 本页唯一负责：作为项目入口页，提供最短启动路径，并把用户与开发者分流到各自文档。

DeepQuestionTree 是一个基于 MCTS 和 LLM 的深度问题探索工作台。系统会围绕一个全局问题持续生成子问题、回答、事实和剪枝结果，最后输出问题树与总结报告。

## Quick Start

### Prerequisites

- Python `3.12`
- Node `20`
- `uv`
- `npm`

Python 依赖只通过 [`pyproject.toml`](./pyproject.toml) 和 [`uv.lock`](./uv.lock) 管理。请使用 `uv`，不要直接使用 `pip install`。

### Install Dependencies

```bash
uv sync --group dev
cd src/frontend
npm ci
```

### Configure Local Environment

真实 provider 默认样板在 [`.env.example`](./.env.example)，离线 mock 样板在 [`.env.mock.example`](./.env.mock.example)。

如果你要直接连真实 provider：

```bash
copy .env.example .env
```

如果你只想离线调试：

```bash
copy .env.mock.example .env
```

后端配置优先级固定为：

```text
代码默认值 < config/settings.yaml < 根目录 .env < 进程环境变量
```

当前模型分工固定为：

- `LLM__GENERATION_MODEL`：负责回答、提问、摘要和报告生成
- `LLM__DECISION_MODEL`：唯一的核查模型，负责问题预审、低价值路径复核与事实合并判定
- `CHECKER__*`：控制历史窗口、字面归一化短路和 fail-open 行为

默认真实 provider 已收敛为 DeepSeek V4 Preview，并通过 OpenAI-compatible client 接入：

- `LLM__BASE_URL=https://api.deepseek.com`
- `LLM__GENERATION_MODEL=deepseek-v4-pro`
- `LLM__DECISION_MODEL=deepseek-v4-pro`
- `LLM__GENERATION_THINKING=false`
- `LLM__DECISION_THINKING=true`
- `LLM__GENERATION_REASONING_EFFORT=high`
- `LLM__DECISION_REASONING_EFFORT=high`

`deepseek-chat` / `deepseek-reasoner` 是旧兼容别名，官方停用窗口为 2026-07-24；新部署请使用 `deepseek-v4-pro` 或按需覆盖为 `deepseek-v4-flash`。系统不会自动 fallback 到别的模型。DeepSeek thinking 开关通过 `extra_body.thinking` 发送；`reasoning_effort` 只在对应链路开启 thinking 时作为顶层请求参数发送。

默认会话与报告持久化文件为：

- `data/sessions/deepquestiontree.sqlite3`

前端公开配置放在 `src/frontend/.env.local`，常用变量如下：

```env
NEXT_PUBLIC_API_HOST=http://localhost
NEXT_PUBLIC_API_PORT=8001
NEXT_PUBLIC_API_TOKEN=dev-token
```

真实 provider 模式现在会在启动前做配置预检；如果 `LLM__API_KEY`、`LLM__BASE_URL` 或模型名缺失，会直接返回 `configuration_error`，并提示切到 mock 配置，而不是等到运行中才模糊失败。

真实 DeepSeek E2E 只通过进程环境变量读取测试 key，不把 key 写入仓库文件。默认 smoke 会把测试规模收敛到 `E2E_MAX_SIMULATIONS=1`、`E2E_BRANCH_FACTOR=2`、`E2E_TIMEOUT_SECONDS=600`，避免把慢速 provider 响应误判为系统不可用：

```bash
uv run pytest tests/e2e/ -v --run-e2e --e2e-provider deepseek
```

### Start the App

启动后端：

```bash
uv run python -m src.backend.main
```

启动前端：

```bash
cd src/frontend
npm run dev
```

默认访问地址：

- 前端：`http://localhost:3000`
- 后端：`http://localhost:8001`

如果浏览器请求返回 `401` 或 `403`，请先设置 Bearer Token：

```js
localStorage.setItem("dqt.apiToken", "dev-token");
```

运行中如果 MCTS worker / 引擎出现致命异常，会话会进入 `error` 状态，`/api/status` 与 session/tree read-model 会暴露最新 `session_revision` 和错误消息，前端只会在 revision 变化时重新拉树。

## Documentation

- 用户操作与常见问题：[`doc/user-guide.md`](./doc/user-guide.md)
- 开发环境、目录职责与协作约束：[`doc/developer-guide.md`](./doc/developer-guide.md)
- 文档总索引：[`doc/README.md`](./doc/README.md)

## Canonical References

- 真实架构与边界：[`doc/project-overview.md`](./doc/project-overview.md)
- API、鉴权与错误契约：[`doc/application-layer-and-auth.md`](./doc/application-layer-and-auth.md)
- 项目级测试、本地验收与真实 E2E：[`doc/testing-and-e2e.md`](./doc/testing-and-e2e.md)
- 前端测试细节：[`doc/frontend-testing.md`](./doc/frontend-testing.md)
