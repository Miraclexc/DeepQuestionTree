# DeepQuestionTree Project Overview

> Last Updated: 2026-03-08
>
> 本文基于当前仓库代码、配置和测试整理，目标是补充根目录 `README.md` 的简要说明，帮助读者快速理解：
> - 项目现在是怎么跑起来的
> - 一次探索会话经历了哪些步骤
> - 前后端分别承担什么职责
> - 目前代码已经支持哪些功能、哪些能力还没有落地

## 1. Project Positioning

DeepQuestionTree 是一个“围绕复杂问题持续追问”的探索系统。它不是一次性给出一个静态答案，而是把问题拆成一棵逐步展开的树：

1. 用户给出一个全局目标问题。
2. 后端以这个问题为根节点启动一轮 MCTS（蒙特卡洛树搜索）。
3. 系统会持续执行“选择节点 → 生成回答 → 评估是否剪枝 → 生成子问题 → 给新问题打分 → 回传播”的循环。
4. 在每次回答后，系统会提取新事实并合并进全局事实池。
5. 最终会基于整棵树和事实池生成一份综合报告。

从代码实现上看，项目当前更像一个“研究/分析工作台”：

- 后端负责探索、状态管理、持久化和报告生成。
- 前端负责可视化树、查看节点详情、浏览历史会话和查看报告。
- 会话数据会以 JSON 形式持久化到本地目录，方便回看与继续分析。

## 2. High-Level Architecture

```text
User Goal
   ↓
Frontend (Next.js)
   ↓ HTTP API
Backend (FastAPI)
   ├─ Session lifecycle
   ├─ MCTS engine
   ├─ Question generation / answering
   ├─ Fact extraction / merging
   ├─ Pruning / duplicate detection
   ├─ Report integration
   └─ Session persistence
        ↓
   data/sessions/*.json
```

### 2.1 Backend modules

| Module | Responsibility | Key Files |
|---|---|---|
| API entry | 启动 FastAPI、管理当前活动会话、启动/停止后台 MCTS 循环 | `src/backend/main.py` |
| Core schema | 定义事实、问答、节点、会话、树响应等核心数据结构 | `src/backend/core/schema.py` |
| MCTS engine | 实现 Selection / Expansion / Simulation / Backpropagation | `src/backend/core/mcts_engine.py` |
| Questioner | 生成候选问题、回答问题、评估问题价值 | `src/backend/modules/questioner.py` |
| Compressor | 从回答中抽取事实、压缩上下文、去重合并事实 | `src/backend/modules/compressor.py` |
| Pruner | 判定路径是否应剪枝，并为被剪枝路径生成摘要 | `src/backend/modules/pruner.py` |
| Integrator | 汇总事实、最佳路径、剪枝信息和 LLM 用量，生成最终报告 | `src/backend/modules/integrator.py` |
| Persistence | 会话的保存、加载、删除、列举、报告缓存 | `src/backend/modules/persistence.py` |
| Visualizer API | 给前端提供按会话读取树结构和节点细节的接口 | `src/backend/modules/visualizer_api.py` |
| LLM / Embedding | 兼容 OpenAI 协议的模型客户端、Mock 客户端、向量去重 | `src/backend/llm/*.py` |
| Configuration | 加载 `config/settings.yaml` 并融合 `src/frontend/.env.local` | `src/backend/config_loader.py` |

### 2.2 Frontend modules

| Module | Responsibility | Key Files |
|---|---|---|
| App shell | 首页直接挂载主工作台组件 | `src/frontend/app/page.tsx` |
| Main workspace | 管理会话列表、当前树、轮询、弹窗、报告与错误状态 | `src/frontend/components/DeepQuestionTree.tsx` |
| Sidebar | 浏览历史会话、创建新探索、删除会话、查看连接状态 | `src/frontend/components/Sidebar.tsx` |
| Tree canvas | 使用 React Flow + Dagre 渲染问题树 | `src/frontend/components/TreeCanvas.tsx` |
| Node panel | 查看单个节点的问题、回答、摘要、事实和统计信息 | `src/frontend/components/NodePanel.tsx` |
| Report view | 查看最终报告、被剪枝路径、LLM 用量，并导出 PDF/JSON | `src/frontend/components/ReportView.tsx` |
| API client | 调用后端接口 | `src/frontend/lib/api.ts` |
| Shared types | 前端使用的会话、节点、树数据类型 | `src/frontend/lib/types.ts` |

## 3. Current Runtime Workflow

下面这条链路描述的是“当前代码真正执行的工作流”，不是概念设计图。

### 3.1 Startup and configuration

项目启动时，后端会优先读取：

- `config/settings.yaml`
- `.env`（由 `pydantic-settings` 读取）
- `src/frontend/.env.local`（仅用于覆盖前后端 Host/Port）

当前配置重点包括：

| Config Area | Main Fields | Purpose |
|---|---|---|
| `app` | `debug`, `mock_llm`, `api_port`, `frontend_port` | 控制运行环境、端口和是否启用 Mock LLM |
| `llm` | `generation_model`, `decision_model`, `api_key`, `base_url` | 控制回答/评估使用的模型和 API 入口 |
| `mcts` | `max_depth`, `branch_factor`, `max_simulations`, `parallel_workers` | 控制搜索深度、分支数、模拟次数和并发 worker 数 |
| `embedding` | `use_local`, `model_path`, `similarity_threshold` | 控制本地向量模型和重复判定阈值 |
| `storage` | `data_dir`, `sessions_dir`, `logs_dir` | 控制本地数据与日志目录 |

### 3.2 Start a session

当用户从前端点击“New Exploration”后，前端会调用：

- `POST /api/start`

请求体核心字段：

```json
{
  "goal": "用户想深入探索的问题",
  "use_mock": false
}
```

后端收到请求后会做这些事情：

1. 如果当前已有探索正在运行，先停止旧任务。
2. 初始化 LLM、Embedding、Questioner、Compressor、Pruner、Integrator。
3. 创建新的 `SessionData`。
4. 创建根节点，根节点的问题就是用户输入的目标问题。
5. 立刻把初始会话保存到 `data/sessions/<session_id>.json`。
6. 创建 `MCTSEngine`。
7. 启动后台异步 MCTS 循环。

### 3.3 Background exploration loop

真正的探索发生在 `run_mcts_loop()` 中。它会按照配置启动多个并行 worker，每个 worker 不断调用 `MCTSEngine.run_step()`。

单次 `run_step()` 的顺序是：

1. **Selection**
   - 从根节点出发，根据 UCT 选择当前最值得继续探索的叶子节点。
   - 会跳过已经剪枝或正在处理中的子节点。

2. **Process current node**
   - 如果被选中的节点还没有有效回答，系统会先生成回答。
   - 回答生成后，立即从回答中抽取事实，并合并到全局事实池。

3. **Pruning**
   - 系统会判断当前路径是否应该停止继续展开。
   - 典型原因包括：
     - 达到最大深度
     - 问题重复
     - 连续低价值路径
     - 偏离主题
     - 全局事实已经足够多
   - 如果剪枝，会给该路径生成一句摘要，并对该节点做负向回传播。

4. **Expansion**
   - 如果没有被剪枝，系统会基于“路径事实 + 当前回答 + 全局目标”生成多个候选追问。
   - 新问题会被创建为子节点。

5. **Simulation**
   - 当前实现不是完整 rollout 文本推演，而是对新子节点中的第一个问题做启发式价值评估。
   - 评分范围是 `0.0 ~ 10.0`。

6. **Backpropagation**
   - 将该价值沿着当前节点到根节点整条路径回传播，累积访问次数和价值和。

7. **Auto save / stop condition**
   - worker 0 会定期自动保存当前会话。
   - 当满足最大模拟次数、最大深度或没有活跃节点时，探索结束。

### 3.4 Report generation

用户查看报告时，前端会调用：

- `GET /api/report`
- 或 `GET /api/report?session_id=<id>`

后端会先尝试从会话 JSON 中读取缓存报告；如果没有缓存，再实时生成。

报告生成链路包括：

1. 分析全局事实。
2. 提取“访问次数最多”的最佳路径。
3. 汇总被剪枝路径的摘要。
4. 提取关键见解。
5. 生成完整报告文本。
6. 生成执行摘要。
7. 生成后续探索建议。
8. 统计 LLM 调用次数、Token 使用量和模型分布。

最终返回的数据不只是报告正文，还包含统计和结构化分析，方便前端分标签展示。

## 4. Supported Features in Current Code

下面列的是“当前代码已经支持”的能力，而不是未来规划。

### 4.1 Exploration and reasoning

- 支持以一个全局问题为根启动探索会话。
- 支持基于 MCTS 的问题树扩展。
- 支持为节点生成回答。
- 支持把回答中的信息抽取为事实。
- 支持对问题进行价值评估，并据此回传播。
- 支持对重复、低价值、偏题或信息充分的路径执行剪枝。
- 支持多并行 worker 后台探索。
- 支持停止当前正在运行的全局探索任务。

### 4.2 Session management and persistence

- 会话会保存为本地 JSON 文件，默认位于 `data/sessions/`。
- 支持列出历史会话。
- 支持恢复指定会话。
- 支持删除历史会话。
- 支持为会话缓存最终报告。
- 支持统计会话数量、备份会话和清理旧会话。

### 4.3 Visualization and UI

- 支持单页 Web UI。
- 支持浏览历史会话列表。
- 支持新建探索并自动切换到新会话。
- 支持以树图形式查看问题扩展过程。
- 支持点击节点查看完整问题、回答、摘要、事实和 MCTS 状态。
- 支持查看最终报告。
- 支持查看被剪枝路径摘要。
- 支持查看 LLM 使用统计。
- 支持将报告导出为 PDF 和 JSON。
- 支持轮询刷新系统状态、会话列表和当前树。

### 4.4 LLM and model integration

- 支持 OpenAI 兼容协议客户端，而不仅限于 OpenAI 官方接口。
- 支持把“生成回答”和“价值评估”分配给不同模型。
- 支持 Mock LLM 客户端，便于开发和测试。
- 支持本地 `sentence-transformers` 嵌入模型。
- 支持 API 模式的 embedding。
- 支持用向量相似度做问题/事实去重。

## 5. API Surface in Current Implementation

项目当前存在两套风格并存的 API：

### 5.1 Session and workflow API

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/start` | `POST` | 创建或恢复会话，并启动后台探索 |
| `/api/stop` | `POST` | 停止当前全局运行中的探索任务 |
| `/api/status` | `GET` | 查看系统和当前活动会话状态 |
| `/api/report` | `GET` | 获取当前或指定会话的综合报告 |
| `/api/tree` | `GET` | 获取当前活动会话的树结构 |
| `/api/node/{node_id}` | `GET` | 获取当前活动会话里指定节点的详情 |
| `/api/sessions` | `GET` | 获取会话列表（旧接口风格） |
| `/api/session/{session_id}/load` | `POST` | 加载历史会话为当前活动会话 |
| `/api/config/reload` | `POST` | 重新加载配置并重建模块 |

### 5.2 Visualizer API

这套接口是前端现在主要使用的读取接口：

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/visualizer/sessions` | `GET` | 列出会话概要 |
| `/api/visualizer/sessions/{session_id}` | `GET` | 获取完整会话数据 |
| `/api/visualizer/sessions/{session_id}/tree` | `GET` | 获取适合 React Flow 渲染的树数据 |
| `/api/visualizer/sessions/{session_id}/nodes/{node_id}` | `GET` | 获取指定节点详情 |
| `/api/visualizer/sessions/{session_id}` | `DELETE` | 删除指定会话 |

## 6. Data Model and Persistence

### 6.1 Core domain objects

| Object | Meaning |
|---|---|
| `Fact` | 从某次回答中抽取出来的结构化事实，带来源节点和置信度 |
| `QAInteraction` | 单个节点上的问答记录，包含问题、回答、摘要、token 和模型信息 |
| `Node` | 树中的一个推理节点，含父子关系、深度、事实、价值统计、剪枝状态 |
| `SessionData` | 一次完整探索会话，包含根节点、全部节点、全局事实、运行统计、报告缓存 |

### 6.2 Persistence strategy

当前持久化是“本地文件 + 内存活动会话”的组合模式：

- 内存中的 `active_session` 用于当前前后端读写共享。
- 落盘文件用于历史记录和恢复。
- 保存会话时采用“临时文件 + 原子替换”的方式，减少写入中断损坏风险。
- 报告会合并保存到会话 JSON 中，同时兼容旧的独立报告文件格式。

## 7. Frontend Interaction Flow

当前前端是一页式工作台，典型交互流程如下：

1. 页面加载后先查询系统状态。
2. 同时拉取历史会话列表。
3. 用户选择一个历史会话后，前端开始轮询这个会话的树数据。
4. 用户点击树节点后，前端拉取节点详情并在右侧面板展示。
5. 用户可以随时新建探索、删除会话、停止当前任务或查看报告。
6. 报告弹窗提供三个主要视角：
   - 综合报告
   - 被剪枝路径
   - LLM 资源使用

## 8. Test Coverage and What It Proves

当前仓库包含 Python 单元测试和集成测试，重点覆盖的是后端逻辑。

### 8.1 Unit tests cover

- 核心数据模型：`Fact`、`QAInteraction`、`NodeState`、`Node`、`SessionData`
- UCT 公式与探索/利用平衡逻辑
- `Questioner` 的问题提取、分数解析和默认问题回退
- `Compressor` 的事实抽取、上下文压缩和事实合并
- `Pruner` 的剪枝判断、路径追溯、剪枝统计与子树剪除

### 8.2 Integration tests cover

- MCTS 初始化、单步运行、多轮运行、停止条件、树统计和回传播
- 会话保存、加载、删除、列举、备份、原子写入和损坏文件处理
- FastAPI 主要端点的启动、状态、停止、树读取、加载会话、获取报告和完整工作流

### 8.3 Current testing boundary

- 当前没有前端测试代码。
- 当前测试大多使用 Mock LLM，而不是实际外部 API。
- 当前没有真正的端到端浏览器自动化测试。

## 9. Current Boundaries and Gaps

下面这些点对理解项目现状很重要：

### 9.1 Functional boundaries

- 当前会话停止接口是“停止当前全局任务”，不是按 `session_id` 精细停止。
- 当前前端更偏“观察与回看”，不支持手动编辑节点或人工扩展树。
- 当前没有用户系统、权限系统或多租户设计。
- 当前没有任务队列、中间件总线或数据库持久化；状态主要靠内存与本地 JSON 文件。
- 当前前端只有一个主页面，没有多页面信息架构。

### 9.2 Engineering boundaries

- 当前仓库仍以 `requirements.txt` 管理 Python 依赖，尚未形成 `pyproject.toml` + lockfile 的工程结构。
- 当前测试辅助脚本 `run_tests.py` 也是直接调用 `pytest`。
- 当前可视化读取 API 与旧的基础 API 并存，说明接口层还没有完全收敛。
- 仓库中的 `AGENTS.md` 属于项目协作协议文档，应纳入 Git 管理，而不是通过 `.gitignore` 排除。

### 9.3 Algorithmic boundaries

- 当前 simulation 阶段是“对新问题做启发式打分”，不是长链路 rollout。
- 当前报告质量高度依赖 LLM 输出和 prompt 设计。
- 当前事实抽取和重复判定依赖模型质量与向量相似度阈值。

## 10. Suggested Reading Path for Developers

如果你准备继续开发这个项目，建议按这个顺序阅读源码：

1. `src/backend/main.py`
2. `src/backend/core/schema.py`
3. `src/backend/core/mcts_engine.py`
4. `src/backend/modules/questioner.py`
5. `src/backend/modules/compressor.py`
6. `src/backend/modules/pruner.py`
7. `src/backend/modules/integrator.py`
8. `src/backend/modules/persistence.py`
9. `src/backend/modules/visualizer_api.py`
10. `src/frontend/components/DeepQuestionTree.tsx`
11. `src/frontend/components/TreeCanvas.tsx`
12. `tests/integration/test_api.py`
13. `tests/integration/test_mcts_flow.py`

## 11. Practical Summary

如果只用一句话总结当前实现：

> DeepQuestionTree 已经实现了“面向复杂问题的、可持久化的、带树可视化与报告输出的 MCTS + LLM 探索闭环”，并且前后端已经能形成完整的本地工作流。

如果再补一句当前边界：

> 它已经具备研究原型/内部分析工具的完整骨架，但在工程化、前端交互深度、接口收敛和真实 E2E 验证方面还有继续打磨空间。

