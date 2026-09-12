# Study 配置 v2

> Last Updated: 2026-09-12; imported from PaperTemplate (Agent profile).

```yaml
schema_version: 2
id: my-study
profile: agent
datasets:
  - id: cases
    factory: project.agent:cases
    version: "1"
tasks:
  - id: respond
    params: {}
methods:
  - id: agent
    factory: project.agent:runner
    params: {use_tool: true}
experiments:
  - id: evaluation
    dataset_ids: [cases]
    task_id: respond
    method_ids: [agent]
    flow: evaluate
    params:
      limits: {max_steps: 3}
    evaluation:
      factory: framework.scoring:exact_match
    repeats: 2
    search:
      strategy: grid
      mode: compare
      parameters: {use_tool: [false, true]}
reports: []
runtime: {seed: 0, device: cpu, max_workers: 1, backend: local}
```

`id` 在各自的组件类别内唯一，允许字母、数字、下划线、点和短横线；一个实验必须引用已声明的任务、数据和方法。只支持配置版本 2；旧配置不会自动转换或命中旧格式缓存。

组件统一包含 `id`、`factory`、`params`、`version`、`code_dependencies`、可选 `hydra_config`。`factory` 指向工厂函数，参数按关键字传入。`code_dependencies` 是参与指纹的文件或目录列表，适合辅助代码、提示词模板或模型文件；远程模型、数据、服务行为需要用 `version` 显式固定版本。工厂函数可用 `__paper_dependencies__ = (HelperClass, helper_function)` 声明 Python 实现依赖。

Hydra 可用 `hydra_config: configs/model#tiny` 组合参数，需安装 hydra extra；显式 `params` 覆盖组合结果的同名顶层参数。组件内部使用工厂配置时也支持这一契约。

| 字段 | 说明 |
|---|---|
| `profile` | `deep_learning`、`agent`、`rag` 三选一 |
| `tasks[].params` | 方向任务描述；深度学习含 feature、target、prediction_kind |
| `experiments[].flow` | 由方向验证的流程名 |
| `experiments[].params` | 划分、执行预算、语料/问题引用、已有模型等方向配置 |
| `experiments[].evaluation` | Agent/RAG 的评分组件；深度学习用 `metrics: [accuracy, macro_f1]` |
| `experiments[].repeats` | 独立重复次数，种子为 runtime.seed + repeat |
| `runtime` | 执行环境；学习率、batch size、优化器归方向方法管理 |

搜索目前支持有限显式列表：

```yaml
search:
  strategy: random
  mode: select
  seed: 17
  n_trials: 3
  parameters:
    retriever.params.top_k: [1, 2, 3]
    generator.params.prompt: ["Use evidence.", "Quote evidence."]
  metric: exact_match
  direction: maximize
```

网格使用 `strategy: grid`；不搜索可省略或设为 `none`。随机搜索在去重后的笛卡尔积上固定种子、无放回抽样。`trial_id` 来自最终解析参数的稳定哈希，与搜索顺序无关。当前不支持概率分布、在线优化器或 Optuna。

`mode: compare` 报告所有候选的测试结果，不能把同一测试集上的最佳值当作无偏最终成绩。`mode: select` 必须提供开发/验证数据，深度学习可提供内层 CV。选择节点只读取开发/验证评分，测试执行依赖已选候选。Agent/RAG 为未选候选保存 `not_selected` 状态并省略其测试指标。

配置中的学习模型、数据、提示词和执行预算都应可序列化。凭据通过工程环境提供；不要把密钥放入 params，因为解析配置会被保存到运行快照。
