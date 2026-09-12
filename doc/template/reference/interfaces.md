# 公共接口

> Last Updated: 2026-09-12; imported from PaperTemplate (Agent profile).

`framework.config.StudySpec` 是统一配置；方向定义的业务字段保存在 `TaskSpec.params`、`ExperimentSpec.params` 和组件参数中。`WorkflowCompiler.compile(study)` 返回 `CompiledWorkflow`，包含 ExecutionPlan、WorkIdentity 映射、指标节点、样本/划分清单和候选选择关联。

```python
from framework.runtime.dag import ArtifactNode, ExecutionPlan

def action(output_dir, dependencies):
    # dependencies[node_id] 提供已提交的 ArtifactRef。
    # 所有本节点文件都写在 output_dir 中。
    ...

plan = ExecutionPlan([
    ArtifactNode("prepare", "prepare", {"version": 1}, "implementation-hash", action)
])
```

`ArtifactNode` 的逻辑身份用于查询；缓存身份由配置、组件代码、上游内容、随机条件和 schema 共同决定。节点必须声明所有真实依赖，不使用未声明的全局文件或可变对象影响结果。

`RunContext` 提供 `output_dir`、`seed`、`limits`、`task`、`resources`，保留可选 `run_id` 供自定义执行器使用。框架的缓存节点默认不传本次命令身份给业务实现；运行来源由执行器写入元数据。Agent/RAG 组件需要使用 context.seed 初始化自己的随机数生成器；不要在并发组件中修改全局随机种子。

| 记录 | 内容 |
|---|---|
| WorkIdentity | Study、Experiment、Method、Trial、Case、Repeat、Stage、可选 dimensions |
| ResultRecord | 逻辑身份、业务状态、产物相对路径、来源 run_id、内容指纹、是否复用 |
| MetricRecord | 身份、指标名、值或 null、统计 unit_id、split、可选 dimensions |

评分组件的工厂返回 `score(result, reference) -> dict[str, float | None]`。执行器不会向 Agent 或 RAG 模型传入 reference；只有评分节点读取它。`metadata` 是允许方法使用的公开信息，隐藏信息应放在 reference 中。这里提供的是 API 和数据视图隔离，组件仍是同一工程中的受信任 Python 代码，不是操作系统安全沙箱。

方向输出以文件载荷保存。深度学习支持模型与 NumPy 预测数组，Agent 保存 `result.json`、`trace.json`，RAG 保存文档、片段、索引、命中和引用。无需为了接入新模型改变公共 MetricRecord。

`framework.results.ResultStore(study_dir, run_id=None)` 固定读取一次完整运行，提供 metrics、artifacts、artifact_path、reports。不要靠遍历输出目录或符号链接推断“最新”的结果。
