# DeepQuestionTree

> Last Updated: 2026-09-12

基于问题搜索树与 LLM 的独立科研实验项目。采用 PaperTemplate 的 Agent 工作流，将数据、方法执行、独立评分和论文结果汇总分开管理。原有前后端工作台、HTTP API 和 SQLite 会话服务已从代码中移除；MCTS、提问、核查、事实压缩及回答整合算法位于 `src/project/dqt/`。

## 开始实验

只需要 Python 3.12 和 UV，无需 Node 或数据库。

```powershell
uv sync --group dev
uv run paper validate configs/studies/smoke.yaml
uv run paper plan configs/studies/smoke.yaml
uv run paper run configs/studies/smoke.yaml --progress
uv run paper run configs/studies/smoke.yaml --progress
```

`smoke.yaml` 使用原有 mock provider 验证真实搜索算法和实验流程；第二次执行应显示 `executed=0`。它不提供科学性能证据。

## DeepSeek Flash 实验

将凭据写入项目根目录 `.env`（已被 Git 忽略）：

```dotenv
LLM__API_KEY=your-key
```

已配置的生成与核查模型均为 `deepseek-flash`，即截至 2026-09-12 官方提供的 DeepSeek-V4.1-Flash。模型和预算在版本化 YAML 中管理；`.env` 只向实验 worker 提供指定的凭据，进程环境优先。模型别名可能随服务升级变化，服务升级后应更新方法 `version`。

```powershell
uv run paper validate configs/studies/tree-search.yaml
uv run paper plan configs/studies/tree-search.yaml
uv run paper run configs/studies/tree-search.yaml --progress
uv run paper export outputs/studies/dqt-tree-search outputs/tree-search-metrics.csv
uv run paper archive dqt-tree-search
```

真实配置目前是迁移示例：2 个测试问题、2 次重复，每棵树最多 3 次搜索步骤，整次运行的预算为 900 秒、50,000 tokens。示例问题没有标准答案，`exact_match` 为 null；`completed` 仅表示执行成功，不代表答案正确。真实 benchmark、基线与消融设计留待下一阶段确定。

## 结果与验证

完整运行入口是 `outputs/studies/<id>/latest.json`。它指向不可变运行目录，包含配置快照、依赖版本、指标、产物索引及报告索引。每个执行产物包含 `result.json`、`tree.json`、`trace.json`、`answer_report.json` 和日志；论文比较表为 `comparison.csv` / `comparison.md`。用 `ResultStore` 读取一次完整运行，不直接拼接不同运行的结果。

```powershell
uv run pytest tests/ -v
uv run python run_tests.py quality
uv run pytest tests/e2e/ -v --run-e2e
```

真实 E2E 会消耗已配置的 Flash API；默认测试不执行真实调用。

- [文档索引](doc/README.md)
- [实验配置与自动化操作](doc/experiment-guide.md)
- [目录与开发边界](doc/developer-guide.md)
- [迁移说明与验收记录](doc/migration.md)
- [测试约定](doc/testing-and-e2e.md)
