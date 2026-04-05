# Testing And E2E

> Last Updated: 2026-04-05
>
> 本页唯一负责：维护项目级测试总览、`run_tests.py` 语义、CI 约束、真实 provider E2E 与手动验收主流程。

前端测试的 Vitest / MSW / Playwright 细节不在本页维护，统一见 [`frontend-testing.md`](./frontend-testing.md)。

## 1. Test Layers

当前测试分为六层：

| Layer | Location | Default Behavior |
|---|---|---|
| Quality | `black / isort / mypy` | 默认纳入 `run_tests.py quality` 与 `run_tests.py ci` |
| Unit | `tests/unit/` | 默认执行 |
| Integration | `tests/integration/` | 默认执行 |
| Backend acceptance | `pytest tests/ -v --cov-fail-under=80` | 默认纳入 `run_tests.py ci` |
| Real API E2E | `tests/e2e/` | 默认不收集，必须显式开启 |
| Frontend acceptance | `cd src/frontend && npm run test:ci` | 默认纳入 `run_tests.py ci` |

## 2. Canonical Commands

日常质量门禁：

```bash
uv run python run_tests.py quality
```

项目级本地 CI 验收：

```bash
uv run python run_tests.py ci
```

后端验收：

```bash
uv run pytest tests/ -v --cov-fail-under=80
```

项目级完整回归：

```bash
uv run python run_tests.py all
```

真实 provider E2E：

```bash
uv run pytest tests/e2e/ -v --run-e2e --e2e-provider openai-compatible
```

说明：

- `uv run pytest tests/ -v` 只覆盖 Python 测试，不执行前端 `.ts/.tsx`
- `run_tests.py all` 会跑后端 pytest 和前端 `npm run test:ci`

## 3. `run_tests.py` Semantics

[`../run_tests.py`](../run_tests.py) 当前命令语义如下：

| Command | Behavior |
|---|---|
| `quality` | 执行 `black --check`、`isort --check-only`、`mypy src/backend` |
| `ci` | 先跑 `quality`，再跑后端验收和前端 `npm run test:ci`，并检查默认 `data/` 目录不被污染 |
| `all` | 跑 `pytest tests/ -v`，然后跑前端 `npm run test:ci` |
| `frontend` | 跑前端 Vitest 和构建 |
| `frontend-e2e` | 跑前端 Playwright smoke |
| `frontend-coverage` | 跑前端覆盖率 |
| `e2e [provider]` | 跑真实 provider E2E |

## 4. CI Constraints

默认 CI 工作流位于 [`../.github/workflows/ci.yml`](../.github/workflows/ci.yml)，当前阻塞环境固定为：

- `windows-latest`
- `Python 3.12`
- `Node 20`

当前阻塞项：

- `uv run python run_tests.py quality`
- `uv run python run_tests.py ci`

`run_tests.py ci` 会在执行前后快照以下目录：

- `data/sessions`
- `data/logs`

如果发现新增或删除运行产物，CI 验收直接失败。

## 5. Real Provider E2E

### 5.1 Execution model

真实 API E2E 位于 `tests/e2e/`，不使用进程内 `ASGITransport`。它会：

1. 为每次测试分配独立临时数据目录
2. 动态选择空闲端口
3. 通过真实入口启动后端进程：

```bash
uv run python -m src.backend.main
```

4. 通过 HTTP 调用：
   - `/api/status`
   - `/api/start`
   - `/api/sessions/{session_id}`
   - `/api/sessions/{session_id}/tree`
   - `/api/sessions/{session_id}/report`
5. 等待探索完成并校验会话文件是否落盘

### 5.2 Supported providers

当前支持两类 provider profile：

#### `deepseek`

必填环境变量：

- `E2E_DEEPSEEK_API_KEY`

可选环境变量：

- `E2E_DEEPSEEK_BASE_URL`
- `E2E_DEEPSEEK_GENERATION_MODEL`
- `E2E_DEEPSEEK_DECISION_MODEL`

默认值：

- `base_url=https://api.deepseek.com/v1`
- `generation_model=deepseek-chat`
- `decision_model=deepseek-chat`

#### `openai-compatible`

必填环境变量：

- `E2E_OPENAI_COMPATIBLE_API_KEY`
- `E2E_OPENAI_COMPATIBLE_BASE_URL`
- `E2E_OPENAI_COMPATIBLE_GENERATION_MODEL`
- `E2E_OPENAI_COMPATIBLE_DECISION_MODEL`

### 5.3 Shared E2E environment variables

| Variable | Purpose | Default |
|---|---|---|
| `E2E_PROVIDER` | 当未传 `--e2e-provider` 时的 provider 选择 | 无 |
| `E2E_API_TOKEN` | 注入给后端 Bearer 鉴权的测试 token | `test-token` |
| `E2E_TIMEOUT_SECONDS` | 服务可用与会话完成超时 | `180` |
| `E2E_MAX_SIMULATIONS` | 控制 smoke 成本的最大模拟次数 | `2` |

## 6. Manual Prototype Acceptance

单用户原型手动验收固定走一条主干：

1. 启动后端和前端
2. 设置 Bearer Token
3. 创建新会话
4. 等待树渲染
5. 点击节点打开 `Node Details`
6. 点击 `Generate Report` 或 `Stop & Report`
7. 刷新页面，确认 `History` 可恢复
8. 删除会话，确认对应文件被移除

通过标准：

- UI 主闭环正常
- 会话文件写入当前配置的 sessions 目录
- 删除后文件确实被清理
- 默认 `data/sessions`、`data/logs` 不被测试命令污染

## 7. Current Boundaries

- 后端真实 E2E 只覆盖独立进程 HTTP API
- 前端浏览器链路由 [`frontend-testing.md`](./frontend-testing.md) 维护
- provider 抽象只存在于测试层，不改业务 DTO
- 默认保持 `EMBEDDING__USE_LOCAL=true`，避免 Deepseek E2E 依赖 embedding API
