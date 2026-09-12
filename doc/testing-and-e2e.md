# 测试与验收

> Last Updated: 2026-09-12

## 命令

| 命令 | 范围 |
|---|---|
| `uv run pytest tests/ -v` | 全部离线 Python 测试，默认不收集真实 E2E |
| `uv run python run_tests.py quality` | black、isort、原算法 mypy |
| `uv run python run_tests.py ci` | quality 后执行全部离线测试 |
| `uv run python run_tests.py unit` | 单元测试 |
| `uv run python run_tests.py integration` | 集成测试，包含模板缓存/统计/调度回归 |
| `uv run python run_tests.py e2e` | 真实 Flash CLI 完整流程 |
| `uv run pytest tests/e2e/ -v --run-e2e` | 显式真实 E2E 的 pytest 入口 |

已移除前端与 HTTP API 测试命令及相应依赖。`run_tests.py all` 仅执行科研 Python 测试。

## 验证层次

- 原算法回归：UCT、节点与事实、提问、checker、压缩、剪枝、整合、结构化输出及并发提交。
- 模板回归：DAG 原子失败恢复、复用/强制执行、统计单位去重、开发集候选选择、报告独立失效、导出、归档、Slurm 脚本与 worker/finalize 契约。
- 项目集成：用原 mock provider 驱动真实 MCTS 子进程，验证树与轨迹、跨进程状态隔离、预算、隐藏答案隔离，以及仅参考答案/评分/报告变化时复用模型执行。
- 真实 E2E：调用安装的 paper 命令执行 validate → plan → run → 缓存复用 → CSV export → archive，所有模型请求均为真实 deepseek-flash。

真实 E2E 使用项目 `.env` 或进程中的 `LLM__API_KEY`，缺凭据时失败，不会把缺配置或 mock 结果算作真实验收。固定规模为一个问题、一次重复、一个搜索步骤，600 秒/30,000 tokens 上限。

真实模型可能触发原有事实饱和剪枝，单根树也可能是合法结果。验收要求有回答、模型消耗、可恢复树与完整归档；单根树必须记录明确剪枝原因。分支展开逻辑由离线集成测试独立覆盖。

测试产物写入 pytest 临时目录，算法日志也重定向到临时目录。默认覆盖率针对 src/project；真实子进程不受默认覆盖率采集，不将该数字作为端到端覆盖率。
