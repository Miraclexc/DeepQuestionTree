# 从旧模板迁移

> Last Updated: 2026-09-12; imported from PaperTemplate (Agent profile).

本次保留核心 DAG、内容指纹、原子产物、增量复用、数据划分、训练和科学指标实现，更新 Python 边界和 YAML；不维护完整旧接口兼容层。

| 原入口/模块 | 新位置或方式 |
|---|---|
| decoding 命令 | paper |
| 旧 Study/Algorithm YAML | framework.config 的 schema_version: 2，methods + factory |
| framework.algorithms | workflows.deep_learning.algorithms |
| framework.data | workflows.deep_learning.data |
| framework.experiments | workflows.deep_learning.experiments（方向内部底层定义） |
| framework.evaluation | workflows.deep_learning.evaluation；通用统计移至 framework.statistics |
| framework.runtime.benchmark | workflows.deep_learning.benchmark |
| 自动发现顶层 algorithms、data | src/project 中显式组件工厂 |
| PaperResultStore / 旧结果视图 | framework.results.ResultStore，或不可变运行 JSON 索引 |
| 特定算法 Slurm 作业 | 方法 worker，含该方法的所有候选试验 |
| 依靠链接访问结果 | latest.json + runs/<run_id> + 相对产物引用 |

迁移步骤：

1. 确定一个 profile，把真实工程代码放入 project 包。
2. 调整领域导入路径，保留原数据、适配器和评估逻辑。
3. datasets 与 methods 配置 factory、params、version，显式声明辅助代码/模型/数据版本依赖。
4. 将训练超参数放入深度学习方法的 training 参数；其他方向用自己的 limits 和组件参数。
5. 声明 flow、split/CV、search、repeats、evaluation；报告按方法、trial、统计单位组织。
6. 先 validate/plan，再离线 run，检查 split_index、metric rows、report_index。

不要复制原输出作为新版成功缓存；schema 已隔离。需要保留旧论文结果时应留存完整旧工程快照。历史领域说明移到 `docs/profiles/deep_learning/legacy`，仅包含在深度学习导出中。

模板导出采用 template-manifest.json 的显式文件清单。新增工程文件、配置或测试后，若需要继续把它作为模板导出，必须把文件加入对应 common 或 profile 清单。导出不会复制运行输出、虚拟环境、凭据或任意未列出的文件。
