# Frontend Testing

> Last Updated: 2026-04-07
>
> 本页唯一负责：维护前端专属测试布局、Node 工具链命令、Vitest / MSW / Playwright 细节与浏览器 smoke 约束。

项目级测试总览、CI 语义和真实 provider E2E 统一见 [`testing-and-e2e.md`](./testing-and-e2e.md)。

## 1. Layout

前端测试文件统一位于：

```text
tests/frontend/
├── components/
├── e2e/
├── fixtures/
├── hooks/
├── lib/
├── msw/
└── setup/
```

对应配置文件位于：

```text
src/frontend/vitest.config.ts
src/frontend/playwright.config.ts
```

## 2. Frontend Commands

在仓库根运行：

```bash
uv run python run_tests.py frontend
uv run python run_tests.py frontend-e2e
uv run python run_tests.py frontend-coverage
```

在前端目录运行：

```bash
cd src/frontend
npm run test
npm run build
npm run test:e2e
npm run test:coverage
npm run test:ci
```

命令语义：

- `npm run test`：Vitest
- `npm run build`：Next.js 构建与类型回归
- `npm run test:e2e`：Playwright 浏览器 smoke
- `npm run test:ci`：Vitest + build + Playwright

## 3. Vitest Stack

当前 Vitest 栈：

- `Vitest`
- `@testing-library/react`
- `@testing-library/jest-dom`
- `MSW`
- `jsdom`

当前覆盖重点：

- `api-client`
- `contracts`
- hooks
- 关键组件与组合层

[`../src/frontend/vitest.config.ts`](../src/frontend/vitest.config.ts) 当前关键约束：

- `include` 指向根 `tests/frontend/**/*.{test,spec}.{ts,tsx}`
- `exclude` 明确排除 `tests/frontend/e2e/`
- 通过 alias 指向前端 `node_modules` 和根目录 `tests/frontend/setup`

## 4. Support Files And Stubs

`tests/frontend/setup/vitest.setup.ts` 负责：

- 注册 `jest-dom`
- 清理 `localStorage`
- 复位 MSW handlers
- stub `confirm` / `alert`
- stub `navigator.clipboard`
- stub `URL.createObjectURL` / `URL.revokeObjectURL`

`tests/frontend/msw/handlers.ts` 默认覆盖：

- `GET /api/status`
- `GET /api/sessions`
- `POST /api/start`
- `POST /api/stop`
- `GET /api/sessions/:id`
- `DELETE /api/sessions/:id`
- `GET /api/sessions/:id/tree`
- `GET /api/sessions/:id/nodes/:nodeId`
- `GET /api/sessions/:id/report`

`html2pdf.js` 在 Vitest 层通过 `tests/frontend/setup/stubs/html2pdf.ts` 替代真实导出逻辑。

## 5. Playwright Browser Smoke

[`../src/frontend/playwright.config.ts`](../src/frontend/playwright.config.ts) 会自动启动两个本地服务。

### 5.1 Backend

命令：

```bash
uv run python -m src.backend.main
```

关键环境变量：

- `APP__MOCK_LLM=true`
- `APP__DEBUG=false`
- `APP__API_PORT=<playwright-backend-port>`
- `APP__FRONTEND_HOST=http://127.0.0.1`
- `APP__FRONTEND_PORT=<playwright-frontend-port>`
- `MCTS__MAX_SIMULATIONS=2`
- `MCTS__PARALLEL_WORKERS=1`
- `SECURITY__API_TOKEN=test-token`
- `STORAGE__DATA_DIR=<temp>`
- `STORAGE__SESSIONS_DIR=<temp>`
- `STORAGE__LOGS_DIR=<temp>`

### 5.2 Frontend

命令：

```bash
npm run build && npm run start -- --hostname 127.0.0.1 --port <playwright-frontend-port>
```

关键环境变量：

- `NEXT_PUBLIC_API_HOST=http://127.0.0.1`
- `NEXT_PUBLIC_API_PORT=<playwright-backend-port>`
- `NEXT_PUBLIC_API_TOKEN=test-token`

补充约束：

- Playwright 不再注入任何 `EMBEDDING__*` 环境变量
- 当 provider 为真实模型时，后端核查链路统一复用 `LLM__DECISION_MODEL`

## 6. Current Boundaries

- jsdom 层不深测 React Flow 内部布局和拖拽细节
- 浏览器 smoke 只保留一条主干 happy path：
  - 首页加载
  - `New Exploration`
  - `History` 中出现 session
  - tree 出现节点
  - 点击节点打开 `Node Details`
  - 关闭节点面板后打开 `Exploration Report`
- 不做多浏览器矩阵
- 不做视觉回归
- 不做前端真实 provider 矩阵
