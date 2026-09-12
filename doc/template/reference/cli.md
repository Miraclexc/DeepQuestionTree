# paper 命令

> Last Updated: 2026-09-12; imported from PaperTemplate (Agent profile).

| 命令 | 用途 |
|---|---|
| `paper validate <study.yaml>` | 加载所选方向、组件与输入，检查配置/划分/报告 |
| `paper plan <study.yaml>` | 列出业务节点和报告的 RUN、REUSE、STALE 状态，不执行方法或构建索引 |
| `paper plan <study.yaml> --visualize [overview\|detail\|full]` | 保存依赖图预览；需要 viz extra 和系统 Graphviz |
| `paper run <study.yaml> --progress` | 本地运行并发布完整运行索引 |
| `paper force <study.yaml> [--node <logical_id>]` | 强制指定节点及下游；省略节点则重做整个业务流程 |
| `paper export <study_dir> <output.csv>` | 导出 latest 完整运行的指标；可加 --method、--metric、--split |
| `paper archive <study_id>` | 在 outputs/archives 保存完整可访问快照 |
| `paper cache status <study_id>` | 查看占用、引用与可回收缓存 |
| `paper cache gc <study_id> [--apply] [--include-failures]` | 预览或执行回收，保护保留运行 |
| `paper template export <profile> <target>` | 按文件清单导出完整单方向源码项目 |
| `paper submit <study.yaml> [--dry-run]` | 生成/提交 Slurm 方法 worker 与 afterok 汇总作业 |
| `paper worker <study.yaml> --method <id>` | 运行该方法的所有试验，保存运行记录但不发布 Study latest |
| `paper finalize <study.yaml>` | 要求全部业务产物已完成，然后生成统一报告与 latest |
| `paper materialize <study.yaml>` | 调用显式配置的工程数据准备 hook |

Slurm 配置示例：

```yaml
runtime:
  backend: slurm
  max_workers: 1
  slurm:
    cpus_per_task: 4
    memory_gb: 16
    time_limit: "02:00:00"
    # partition 与 gres 按本地集群明确填写，无内置集群名称。
  hooks:
    materialize: project.hooks:materialize
    validate_submit: project.hooks:validate_submit
```

worker 以方法为调度单位，包含该方法的所有候选参数；每个 worker 使用独立 Python 进程，产物锁协调共享目录。汇总作业只在所有 worker 成功后执行，不申请 worker 的 GPU gres。脚本需要计算节点访问同一项目、uv 环境和 outputs 目录。

`--dry-run` 不调用 sbatch。测试覆盖脚本生成、模拟 job ID 与 afterok 依赖，以及本地模拟 worker/finalize；真实集群资源、文件系统和队列权限仍需在目标集群验证。
