# User Guide

> Last Updated: 2026-04-08
>
> 本页唯一负责：面向本地使用者说明如何启动并使用 DeepQuestionTree 工作台。

本文默认你是本地运行该系统的使用者，而不是维护代码的开发者。若你需要调试、改接口或维护测试，请转到 [`developer-guide.md`](./developer-guide.md)。

## 1. 运行前准备

需要以下工具：

- Python `3.12`
- Node `20`
- `uv`
- `npm`

安装依赖：

```bash
uv sync --group dev
cd src/frontend
npm ci
```

## 2. 本地配置

### 2.1 后端配置

从仓库根目录的 [`.env.example`](../.env.example) 复制出 `.env`：

```bash
copy .env.example .env
```

后端配置优先级：

```text
代码默认值 < config/settings.yaml < 根目录 .env < 进程环境变量
```

开发态默认 Bearer Token 来自 [`../config/settings.yaml`](../config/settings.yaml)：

```yaml
security:
  api_token: "dev-token"
```

默认真实 provider 样板为：

```env
LLM__BASE_URL=https://api.deepseek.com/v1
LLM__GENERATION_MODEL=deepseek-chat
LLM__DECISION_MODEL=deepseek-reasoner
```

如果你的部署环境不支持 `deepseek-reasoner`，请只覆盖 `LLM__DECISION_MODEL`；系统不会自动切回别的模型。

默认会话数据库文件位于：

- `data/sessions/deepquestiontree.sqlite3`

### 2.2 前端配置

前端只读取自己的公开变量。常见本地配置放在 `src/frontend/.env.local`：

```env
NEXT_PUBLIC_API_HOST=http://localhost
NEXT_PUBLIC_API_PORT=8001
NEXT_PUBLIC_API_TOKEN=dev-token
```

### 2.3 浏览器 Token 覆盖

浏览器会优先读取 `localStorage["dqt.apiToken"]`，没有时才回退到 `NEXT_PUBLIC_API_TOKEN`。开发态可在浏览器控制台执行：

```js
localStorage.setItem("dqt.apiToken", "dev-token");
```

如果以后要清除浏览器里的覆盖值：

```js
localStorage.removeItem("dqt.apiToken");
```

## 3. 启动系统

在仓库根目录启动后端：

```bash
uv run python -m src.backend.main
```

在 `src/frontend` 启动前端：

```bash
cd src/frontend
npm run dev
```

默认地址：

- 前端：`http://localhost:3000`
- 后端：`http://localhost:8001`

## 4. 页面导航与核心操作

### 4.1 新建一次探索

1. 打开左侧栏的 `New Exploration`。
2. 在弹窗里输入研究目标。
3. 点击 `Start Analysis`。
4. 创建成功后，当前会话会出现在左侧 `History`，主区域开始轮询树数据。

补充说明：

- 如果后端可用，底部连接状态会显示正常。
- `New Exploration` 只创建新的探索，不会复用旧会话 ID。

### 4.2 查看或恢复历史会话

左侧 `History` 会列出本地已保存的会话。点击某条记录后：

- 主区域会切换到该会话的问题树。
- 顶部会显示该会话的目标和短 ID。
- 你可以继续查看节点详情、打开报告或删除会话。

当会话状态是 `paused`、`completed` 或 `error` 时，把鼠标悬停到对应记录上，还会出现 `Resume Session` 按钮。点击后：

- 前端会调用现有恢复接口，继续使用原会话 ID 运行；
- 当前打开的 `Node Details` 和 `Exploration Report` 会先关闭；
- 主区域会回到树工作台，并重新选中该会话。

### 4.3 查看节点详情

在树上点击节点后，右侧会打开 `Node Details` 面板，里面会展示：

- Question
- Answer
- 新提取的 facts
- 节点路径
- 节点统计和元数据

关闭按钮是面板右上角的 `Close node details`。

### 4.4 生成或查看报告

选中会话后，顶部操作栏有两个按钮：

- `Generate Report`：直接打开当前会话的 `Exploration Report`。如果当前会话版本没有可复用缓存，后端会基于最新会话快照重新生成报告。
- `Stop & Report`：仅在会话仍处于运行中时可点击。点击后会先停止探索，再打开报告。

补充说明：

- 运行中先看过一次报告后，只要问题树继续推进，旧报告就会自动失效。
- 旧会话恢复运行后，恢复前生成的报告不会再被当作当前报告直接复用。
- `running` 会话不会显示 `Resume Session`，因为它本身已经处于活动状态。

报告视图支持三个层面：

- 主报告内容
- `Pruned Paths & Dead Ends`
- `LLM Utilization`

### 4.5 导出报告

在 `Exploration Report` 右上角可以：

- 导出 PDF
- 下载 JSON

说明：

- PDF 导出依赖前端已安装 `html2pdf.js`，默认已在 `src/frontend/package.json` 中声明。
- JSON 下载的是当前报告 read-model，适合归档或进一步处理。

### 4.6 删除会话

在左侧 `History` 的某条记录上悬停后，点击垃圾桶图标 `Delete Session`：

1. 系统会弹出确认框。
2. 确认后会调用删除接口。
3. 对应会话和报告缓存会从 SQLite 数据库中移除。

如果删除的是当前选中的会话，主区域会被重置。

## 5. 数据存放与清理

默认运行数据目录：

- 会话目录：`data/sessions`
- 会话数据库：`data/sessions/deepquestiontree.sqlite3`
- 日志：`data/logs`

你通常不需要手动编辑这些文件。常见清理方式：

- 删除单个会话：直接在 UI 中使用 `Delete Session`
- 清空本地历史：关闭系统后，删除 `data/sessions/deepquestiontree.sqlite3`
- 清理日志：关闭系统后，手动删除 `data/logs` 下生成的日志文件

如果目录里有 `.gitkeep`，请保留它。

## 6. 常见问题

### 页面显示 disconnected

先检查：

- 后端是否已启动
- `NEXT_PUBLIC_API_HOST` 和 `NEXT_PUBLIC_API_PORT` 是否正确
- 浏览器是否能访问 `http://localhost:8001/api/status`

### 请求返回 401 或 403

这通常说明 Bearer Token 缺失或错误。请确认：

- 后端 `security.api_token` 的值
- `src/frontend/.env.local` 中的 `NEXT_PUBLIC_API_TOKEN`
- 浏览器 `localStorage["dqt.apiToken"]` 是否残留了旧值

### 刷新页面后看不到旧会话

先检查：

- 后端是否仍指向同一个 `STORAGE__SESSION_DB_PATH`
- `data/sessions/deepquestiontree.sqlite3` 是否仍存在

系统会在启动时和 API 查询时从当前 SQLite 文件读取历史会话；如果数据库路径切换到了临时位置，旧历史不会自动出现在当前环境里。

### `Stop & Report` 按钮不可点击

只有当前会话状态是 `running` 时，该按钮才可用。若会话已经停止或完成，请直接使用 `Generate Report`。

### PDF 导出失败

先尝试下载 JSON。若仍需 PDF，请检查：

- 前端依赖是否完整安装
- 浏览器控制台是否有 `html2pdf.js` 相关错误
- 页面是否成功打开了 `Exploration Report`

## 7. 更多文档

- 开发维护入口：[`developer-guide.md`](./developer-guide.md)
- 真实架构边界：[`project-overview.md`](./project-overview.md)
- API 与鉴权规则：[`application-layer-and-auth.md`](./application-layer-and-auth.md)
