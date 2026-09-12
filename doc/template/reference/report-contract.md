# 论文报告与统计

> Last Updated: 2026-09-12; imported from PaperTemplate (Agent profile).

默认的 `summary` 报告输出 comparison.csv 与 comparison.md，每个实验、方法、trial、指标、split、level 分组。先在 unit_id 内平均重复观测，再在单位之间平均；表格分别显示 n_units、n_records、n_repeats。

Agent/RAG 默认单位为问题 id，可在数据记录中指定 unit_id。深度学习默认保留 fold、subject、session 等层次的指标；折本身通常不是独立实验对象，论文推断应显式选用适当层次和配对键。表格是描述统计，不能代替研究设计。

```python
from dataclasses import asdict
from framework.results import ResultStore
from framework.statistics import (
    bootstrap_mean_confidence_interval, paired_comparison, adjust_comparisons,
)

rows = [asdict(row) for row in ResultStore("outputs/studies/my-study").metrics()]
ci = bootstrap_mean_confidence_interval(
    rows, experiment_id="evaluation", method_id="agent", trial_id="t-...",
    metric="success", unit_keys=["unit_id"], seed=0,
)
comparison = paired_comparison(
    rows, experiment_id="evaluation", method_a="a", trial_a="t-...",
    method_b="b", trial_b="t-...", metric="success", pair_keys=["unit_id"],
)
corrected = adjust_comparisons([comparison], method="holm")
```

统计接口支持点路径键，例如 `dimensions.subject_id`。同一单位的重复观测先平均；相同 case/repeat/dimensions 的缓存重复记录去重，冲突值报错。bootstrap 在独立单位上重采样；配对比较使用单位差值的符号随机化检验，记录匹配数量和未匹配数量。多重比较支持 Holm 和 Benjamini–Hochberg。至少需要两个有效独立单位。

自定义报告：

```yaml
reports:
  - id: paper-table
    callable: project.reports:make_table
    params: {caption: "Main results"}
    inputs:
      results:
        experiments: [evaluation]
        methods: [agent]
        stages: [evaluate]
```

```python
def make_table(context, caption):
    # context.metrics 是已经保存的指标。
    # context.inputs["results"] 中的 ReportArtifact 含 path、fingerprint、identity。
    text = caption + "\n" + str(len(context.metrics)) + " metric rows\n"
    (context.output_dir / "table.md").write_text(text, encoding="utf-8")
```

报告选择器可按 experiments、methods、stages、trials 筛选，空选择器表示全部；没有匹配产物的显式输入会在 validate 时报错。自定义函数使用 keyword params；需要辅助实现时声明 `__paper_dependencies__` 或配置 `code_dependencies`。

可选 token、工具调用、费用、耗时指标未知时保存 null，不填成零。Agent 默认记录已知步数和工具次数、模型报告的 token、实际循环耗时；费用默认缺失。RAG 或自定义组件可返回这些载荷，并由评分器提取。绘图回调自行安装所需绘图库，核心不强制 Matplotlib。
