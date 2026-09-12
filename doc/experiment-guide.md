# 实验操作指南

> Last Updated: 2026-09-12

## 1. 选择入口

- `configs/studies/smoke.yaml`：原 mock provider + 真实搜索代码的离线集成验证。
- `configs/studies/tree-search.yaml`：DeepSeek Flash 的真实实验起点。
- `configs/studies/agent.yaml`：原模板的 echo 接口示例，供框架回归使用。

先 `paper validate`，再 `paper plan`，确认待执行 case/method/trial/repeat 与预算后 `paper run --progress`。validate/plan 会读取数据与组件实现，但不调用模型。

## 2. 数据与划分

数据工厂 `project.datasets:load_cases` 读取 UTF-8 JSONL：

```json
{"id":"q1","input":"问题内容","split":"test","reference":null,"unit_id":"q1","metadata":{"category":"reasoning"}}
```

id 必须是唯一非空字符串，input 必须是非空字符串。split 支持 train/dev/validation/test，缺省为 test；metadata 是公开对象。reference 可为文本、可接受答案列表或 null。unit_id 默认为问题 id，用于先在独立问题内平均重复运行，再跨问题汇总。

当前问题文件仅用于迁移示例，没有答案标签和 benchmark 资格。实际数据集应记录来源、版本、授权、划分和独立统计单位；不要把模型生成的“事实”当作已验证真值。

## 3. 方法与配置

方法工厂 `project.methods:tree_search` 提供以下参数：

| 参数 | 含义 |
|---|---|
| mock | 是否使用原 MockClient；真实实验配置为 false |
| api_key_env | 凭据变量名，默认 LLM__API_KEY |
| llm | 生成/决策模型、endpoint、thinking 和请求超时的显式覆盖 |
| mcts | 深度、分支数、模拟次数、探索常数等原算法参数 |

先读取版本化 `config/settings.yaml`，再覆盖 method params。默认只使用 `deepseek-flash`；生成不开启 thinking，核查启用 high thinking。实验不自动切模型或重试失败请求。

`.env` 只用于读取 api_key_env 指定的凭据，进程环境优先；不要把密钥放入 YAML params，因为框架会保存 resolved_study.json。原应用的 APP、SECURITY、STORAGE 环境变量已无实验配置作用。

每次执行在单独子进程中装配算法，`runtime.max_workers` 控制并行 case 数；`mcts.parallel_workers` 必须为 1。与结果有关的文件列入 code_dependencies；远程模型版本用 method.version 明确记录。当前版本标签表示核实日期，并非供应商提供的不变模型快照。

## 4. 预算与状态

- `limits.max_steps`：MCTS 搜索步骤尝试次数上限，包括被剪枝的尝试；不是 LLM 请求数。另受原 max_simulations/max_depth/事实饱和停止条件限制。
- 搜索停止后，原 Integrator 仍会生成最终回答；它属于同一次方法执行，并计入 token 和时间预算。
- `limits.tokens`：累计模型报告的 tokens，收到响应后检查，可能超出最多一次响应的消耗。超限后不再发起模型调用。
- `limits.time_seconds`：模型调用前后与搜索步骤边界检查。阻塞请求受 llm.timeout 约束；子进程另有 time_seconds + 30 秒的硬超时（未配置 time_seconds 时为 3630 秒）。硬超时记为执行失败，不能保证保存最终树。
- `completed`：完成最终回答；`token_limit` / `time_limit`：业务预算终止，仍保存轨迹和已提交树，answer 为 null；请求异常导致节点失败，没有 SUCCESS。

达到预算时未提交的搜索提案不会混入树；trace 保留已经完成的真实调用及消耗。预算终止产物可以复用，需要增加预算或使用 force 才会重新调用模型。

tree.json 使用保留的 SessionStatus：完整回答为 completed，预算终止为 paused，运行异常为 error；result.json 保留更精确的 token_limit/time_limit 原因。

## 5. 候选比较与选择

在 experiment 中可配置有限网格，例如：

```yaml
search:
  strategy: grid
  mode: compare
  parameters:
    mcts.branch_factor: [2, 4]
    mcts.exploration_constant: [0.7, 1.414]
```

repeats 是独立执行次数，seed 为 runtime.seed + repeat。固定 seed 不保证远程模型输出一致；重放相同缓存不能作为新的实验重复。

`mode: compare` 展示所有候选，不能在同一测试集挑最好成绩后声称无偏结果。`mode: select` 要求 dev/validation 问题、一个有意义的评分指标和方向；模板先基于开发集选候选，再跑测试。当前没有标签的示例不适合作选择研究。

## 6. 独立评分与汇总

`project.evaluation:response_metrics` 输出 completed、exact_match、steps、simulations、tokens、llm_calls、elapsed_seconds、tree_nodes、tree_depth、facts、pruned_nodes、cost。exact_match 是去除首尾空白后的严格匹配；对于开放问题应另定义任务评分器。缺 reference 时保留 null，未知费用也是 null，不使用原客户端的简化价格估算。

只有执行成功时才可能 exact_match=1。completed 不代表回答正确，facts 只表示模型提取条目数。更换评分逻辑只重做 evaluate 及论文汇总，重新渲染报告不调用模型。

```python
from framework.results import ResultStore

store = ResultStore("outputs/studies/dqt-tree-search")
rows = store.metrics()
report = store.reports()["report:summary"] / "comparison.md"
```

用一次完整的 ResultStore 或固定 run_id 读取结果。所有路径由 artifact_index/report_index 显式记录；不遍历缓存拼“最新”结果。配对检验、独立单位 bootstrap 与多重比较参考[统计契约](template/reference/report-contract.md)。

## 7. 故障与自动化

`paper run` 返回非零时检查 `runs/<run_id>/manifest.json`、events.jsonl 及 artifacts/failures 中的 worker.log/trace.json。修复后重跑同一配置，已成功节点可以复用；默认没有隐式请求重试。`paper force` 会真的重新调用模型并产生新的来源身份。

`paper export` 导出结构化指标，`paper archive` 保存独立快照。`cache gc` 默认为预览。Slurm worker/finalize 接口已迁入，但未在真实集群验收；参见[命令参考](template/reference/cli.md)。AI 自动实验应修改版本化 Study，保留每次运行身份和研究结论的来源，并在报告中区分 mock、执行成功与科学效果。
