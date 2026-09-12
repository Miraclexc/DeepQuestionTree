# 模板离线接口示例

> Last Updated: 2026-09-12

在仓库根运行，仅用 UV 管理环境：

```powershell
uv sync --group dev
uv run paper validate configs/studies/agent.yaml
uv run paper plan configs/studies/agent.yaml
uv run paper run configs/studies/agent.yaml --progress
uv run paper run configs/studies/agent.yaml --progress
```

该示例使用本地 echo 工具，验证是否使用工具的参数比较、重复运行与缓存；没有远程模型调用。DeepQuestionTree 本身的集成验证入口是 configs/studies/smoke.yaml，真实模型入口是 configs/studies/tree-search.yaml。

第二次执行复用产物，仍产生新的 run_id。输出的 latest.json 指向完整运行；ResultStore 可固定读取该运行的指标和报告：

```python
from framework.results import ResultStore
store = ResultStore("outputs/studies/agent-demo")
rows = store.metrics(metric="success", split="test")
report = store.reports()["report:summary"] / "comparison.md"
```

```powershell
uv run paper export outputs/studies/agent-demo outputs/agent-metrics.csv --metric success
uv run paper archive agent-demo
uv run paper cache status agent-demo
```

本研究项目已独立包含核心源码，不需要访问原模板目录。需要导出一个全新的模板时，请从原 PaperTemplate 工程执行 template export；本仓库不维护该导出清单。
