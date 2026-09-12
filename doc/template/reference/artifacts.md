# 结果身份、缓存与失败

> Last Updated: 2026-09-12; imported from PaperTemplate (Agent profile).

Study 的输出根为 `outputs/studies/<id>`。`runs/<run_id>` 保存 resolved_study、environment、manifest、events、split_index、metrics、summary、artifact_index、report_index；文件名除 events.jsonl 外均为 JSON。

每次命令执行分配新的 run_id，即使全部复用。Artifact 元数据中的 `source_run_id` 保留真正生成该产物的运行，run_id 不进入内容指纹。统计分析读取某次运行的指标，不把缓存回放算作新的独立样本。

完成发布时先提交不可变的运行文件，再原子更新 `latest.json`。根目录下同名 JSON 是便于查看的快照；程序应通过 ResultStore 或 latest 指针读取同一次完整运行。Windows 不需要符号链接或开发者模式。

缓存目录：

```text
artifacts/objects/<前两位>/<fingerprint>/  完整产物、artifact.json、SUCCESS
artifacts/failures/...                   失败的临时输出和 FAILED
artifacts/locks/                         活跃构建锁
artifacts/index.json                     逻辑节点最近产物索引
```

执行异常使运行标记 failed，不产生本节点 SUCCESS；上游完整结果保留。重跑会复用它们。业务失败，例如 Agent 达到步数或 token 上限，作为明确的结果状态保存，可以被评分器评估。框架默认不重试工具操作；强制重跑 Agent 会创建新的环境和记忆，调用方需要自行决定有副作用工具是否适合再次执行。

`paper cache gc <id>` 默认预览，`--apply` 真正清理。GC 保护所有保留的运行清单引用的成功产物，包括失败运行已完成的上游；不会因只保留 latest 索引而删除历史论文运行。需要释放某次运行时，先归档，并显式移除不再保留的运行目录；没有提供自动删除历史运行的策略。活动锁和未完成运行会阻止不安全清理。`--include-failures` 同时清理不再活动的失败目录。

`paper archive <id>` 在 outputs/archives 中创建包含运行清单、索引及所引用实际文件的独立副本，不创建符号链接。归档期间发现活动构建或 latest 变化会拒绝发布不一致归档。

强制执行会产生一次新的派生产物身份，并使其下游失效；原结果仍可审计。旧版 framework schema 与当前 `paper-template-2` 不共享成功缓存。
