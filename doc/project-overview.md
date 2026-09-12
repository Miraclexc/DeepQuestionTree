# 项目架构

> Last Updated: 2026-09-12

DeepQuestionTree 是基于问题搜索树的 Agent 研究项目。当前迁移解决可复现实验与结果汇总问题；研究假设、正式 benchmark、对照方法及消融不在本次迁移中预先定论。

## 分层流程

```text
configs/studies/*.yaml + datasets/*.jsonl
              ↓
framework: 配置、DAG、内容指纹、原子提交、运行索引
              ↓
workflows/agent: case × method × trial × repeat
              ↓
project.methods: 为每次执行启动独立 Python 进程
              ↓
project.worker → project.dqt: MCTS / checker / questioner / compressor / integrator
              ↓
result.json + tree.json + trace.json + answer_report.json
              ↓
project.evaluation → metrics.json
              ↓
project.reports → comparison.csv / comparison.md
```

## 实验隔离

每个 case/repeat 的 worker 都有独立配置、随机数状态、搜索树、模型客户端与日志。多个独立问题可通过 `runtime.max_workers` 并行；单棵树使用一个 worker，保留原并发算法但不共享全局状态。没有 Web server、API token、数据库或进程内的多用户会话管理。

隐藏参考答案仅在评分节点读取；worker 的 case 只含 id、input、公开 metadata。不要把隐藏标签放到 metadata 中。

实验方法的参数和代码依赖参与缓存指纹；凭据只通过子进程环境传递。所有 LLM 行为配置来自版本化配置，普通应用环境变量不会隐式改变一次实验。执行目录内的 request.json 不包含 API key。

## 两类报告

`answer_report.json` 是 Agent 对一个问题的最终回答，由原 Integrator 调用模型生成，属于方法执行与预算的一部分。

`comparison.csv` / `comparison.md` 是论文实验汇总，仅消费已经提交的指标。修改评分器或论文报告不重新调用 Agent；修改模型、提示词或搜索算法会使执行及下游失效。

## 可复现边界

seed 固定本地随机状态与重复编号；不能保证外部模型返回逐字一致结果。原有 UUID 与时间戳保留在诊断快照中。复用缓存不算新的独立重复；每次 CLI 运行有独立 run_id，实际生成来源保存在 source_run_id。

本次仅迁入 Agent 方向和模板公共核心；没有深度学习、RAG 或模型训练依赖。完整缓存与发布契约见 [模板说明](template/reference/artifacts.md)。
