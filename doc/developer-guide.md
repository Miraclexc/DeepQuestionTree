# Developer Guide

> Last Updated: 2026-04-07
>
> 本页唯一负责：面向开发者说明环境基线、目录职责、调试入口、变更同步点和文档维护规则。

如果你只是想使用系统，请优先阅读 [`user-guide.md`](./user-guide.md)。

## 1. Environment Baseline

- Python 基线：[`../.python-version`](../.python-version) 固定为 `3.12`
- Python 依赖来源：[`../pyproject.toml`](../pyproject.toml) 和 [`../uv.lock`](../uv.lock)
- Python 环境管理：只使用 `uv`
- Node 基线：CI 采用 `Node 20`

禁止直接使用：

- `pip install`
- 手工编辑 `uv.lock`

常用初始化命令：

```bash
uv sync --group dev
cd src/frontend
npm ci
```

## 2. Development Entry Points

### 2.1 后端

启动后端：

```bash
uv run python -m src.backend.main
```

开发态热重载：

```bash
uv run uvicorn src.backend.main:app --reload --host 0.0.0.0 --port 8001
```

关键入口文件：

- [`../src/backend/main.py`](../src/backend/main.py)
- [`../src/backend/api/router.py`](../src/backend/api/router.py)
- [`../src/backend/services/runtime.py`](../src/backend/services/runtime.py)

### 2.2 前端

启动前端：

```bash
cd src/frontend
npm run dev
```

关键入口文件：

- [`../src/frontend/app/page.tsx`](../src/frontend/app/page.tsx)
- [`../src/frontend/components/DeepQuestionTree.tsx`](../src/frontend/components/DeepQuestionTree.tsx)

## 3. Directory Responsibilities

### 3.1 Backend

| Path | Responsibility |
|---|---|
| `src/backend/api/` | 路由、DTO、鉴权依赖 |
| `src/backend/services/` | 运行时门面、应用服务、协调器、串行 commit 通道、仓储边界 |
| `src/backend/core/` | 领域对象、MCTS engine、snapshot/proposal 并发提交流程 |
| `src/backend/modules/` | checker、questioner、compressor、pruner、integrator、persistence |
| `src/backend/llm/` | LLM client、基于 `purpose` 的 generation/decision 模型路由、prompt manager、mock client |
| `config/` | 默认配置与 prompts |

### 3.2 Frontend

| Path | Responsibility |
|---|---|
| `src/frontend/app/` | Next.js app shell |
| `src/frontend/components/` | 页面组件与细分展示组件 |
| `src/frontend/hooks/` | 轮询、命令、节点详情、报告状态、全局错误 |
| `src/frontend/lib/` | API client、contracts、共享类型、工具函数 |
| `tests/frontend/` | 前端 Vitest、MSW、Playwright 测试文件 |

### 3.3 Runtime Data

默认运行产物目录：

- `data/sessions`
- `data/sessions/deepquestiontree.sqlite3`
- `data/logs`

提交代码前不要把新的运行产物带入版本库。

## 4. Configuration Boundaries

后端配置优先级：

```text
代码默认值 < config/settings.yaml < 根目录 .env < 进程环境变量
```

关键事实：

- 后端配置加载实现在 [`../src/backend/config_loader.py`](../src/backend/config_loader.py)
- 后端不会读取 `src/frontend/.env.local`
- 前端只读取自己的 `NEXT_PUBLIC_*` 环境变量
- Bearer Token 后端来源是 `security.api_token` 或 `SECURITY__API_TOKEN`
- 浏览器端优先使用 `localStorage["dqt.apiToken"]`
- 会话和报告缓存统一落在 `storage.session_db_path`
- 默认 SQLite 文件路径是 `data/sessions/deepquestiontree.sqlite3`

## 5. Change Synchronization Points

### 5.1 改后端 API 时

同步检查以下位置：

- [`../src/backend/api/router.py`](../src/backend/api/router.py)
- [`../src/backend/api/dto.py`](../src/backend/api/dto.py)
- [`../src/frontend/lib/api.ts`](../src/frontend/lib/api.ts)
- [`../src/frontend/lib/contracts.ts`](../src/frontend/lib/contracts.ts)
- [`./application-layer-and-auth.md`](./application-layer-and-auth.md)

如果新增或重命名 session-scoped 路由，必须同时更新文档中的 endpoint matrix。

### 5.2 改前端数据流时

同步检查以下位置：

- [`../src/frontend/hooks/useDeepQuestionTree.ts`](../src/frontend/hooks/useDeepQuestionTree.ts)
- [`../src/frontend/hooks/useSessionCommands.ts`](../src/frontend/hooks/useSessionCommands.ts)
- [`../src/frontend/hooks/useNodeDetails.ts`](../src/frontend/hooks/useNodeDetails.ts)
- [`../src/frontend/hooks/useReportState.ts`](../src/frontend/hooks/useReportState.ts)
- [`./user-guide.md`](./user-guide.md)

如果按钮文案、交互路径或 Token 使用方式改变，用户手册必须同步。

### 5.3 改测试入口时

同步检查以下位置：

- [`../run_tests.py`](../run_tests.py)
- [`../src/frontend/package.json`](../src/frontend/package.json)
- [`./testing-and-e2e.md`](./testing-and-e2e.md)
- [`./frontend-testing.md`](./frontend-testing.md)

### 5.4 改 LLM client / prompts / structured output 时

同步检查以下位置：

- [`../src/backend/modules/checker.py`](../src/backend/modules/checker.py)
- [`../src/backend/llm/client_interface.py`](../src/backend/llm/client_interface.py)
- [`../src/backend/llm/llm_client.py`](../src/backend/llm/llm_client.py)
- [`../config/settings.yaml`](../config/settings.yaml)
- [`../.env.example`](../.env.example)
- [`../config/prompts.yaml`](../config/prompts.yaml)
- [`./llm-structured-output-contract.md`](./llm-structured-output-contract.md)
- `tests/unit/test_llm_client_contracts.py`
- `tests/unit/test_checker.py`

如果结构化输出的顶层形状、checker 决策字段、模型路由或 fallback 行为发生变化，必须同时更新契约文档和对应测试。

## 6. Quality And Validation

项目级测试与验收矩阵以 [`testing-and-e2e.md`](./testing-and-e2e.md) 为唯一事实来源。开发者日常至少应知道以下入口：

```bash
uv run python run_tests.py quality
uv run python run_tests.py ci
```

其中：

- `quality` 做 Python 格式、导入顺序和类型检查
- `ci` 做项目级本地验收，并校验默认 `data/` 工作区不被测试污染
- 并发 MCTS 回归位于 `tests/unit/test_mcts_concurrency.py` 与 `tests/integration/test_mcts_concurrency.py`

前端专属测试细节见 [`frontend-testing.md`](./frontend-testing.md)。

## 7. Documentation Maintenance Rules

本仓库当前文档分工如下：

- 根 [`../README.md`](../README.md)：入口页，不维护深度细节
- [`./user-guide.md`](./user-guide.md)：用户操作
- [`./developer-guide.md`](./developer-guide.md)：开发维护
- [`./project-overview.md`](./project-overview.md)：真实架构与边界
- [`./application-layer-and-auth.md`](./application-layer-and-auth.md)：接口与鉴权
- [`./llm-structured-output-contract.md`](./llm-structured-output-contract.md)：LLM 结构化输出契约
- [`./testing-and-e2e.md`](./testing-and-e2e.md)：项目级测试
- [`./frontend-testing.md`](./frontend-testing.md)：前端测试

更新文档时遵守以下规则：

- 每篇文档只维护自己的唯一职责，不复制另一篇的完整命令矩阵或接口表。
- 所有命令字面量、环境变量名、路径和按钮文案必须与代码一致。
- 每次改动文档时更新 `Last Updated`。
- 如果发现旧文档描述的是目标架构而不是当前实现，以当前代码为准并立即修文档。

## 8. Suggested Reading Sequence

1. [`../README.md`](../README.md)
2. [`./project-overview.md`](./project-overview.md)
3. [`./llm-structured-output-contract.md`](./llm-structured-output-contract.md)
4. [`./application-layer-and-auth.md`](./application-layer-and-auth.md)
5. [`./testing-and-e2e.md`](./testing-and-e2e.md)
6. [`./frontend-testing.md`](./frontend-testing.md)
