# 科研实验迁移记录

> Last Updated: 2026-09-12

## 目标与来源

参照用户提供的 `D:\Paper\PaperTemplate`，迁入公共核心和 Agent profile，形成不依赖原模板目录的独立源码工程。`template-origin.json` 保存逐文件来源和原始 SHA-256；没有复制原模板凭据、环境、输出或深度学习/RAG 实现。

## 迁移映射

| 原内容 | 当前状态 |
|---|---|
| src/backend/core | src/project/dqt/core，保留 MCTS 和数据结构 |
| src/backend/modules | src/project/dqt/modules，保留提问、核查、压缩、剪枝和回答整合 |
| src/backend/llm、utils | src/project/dqt/llm、utils，保留模型契约与日志 |
| src/backend/config_loader.py | src/project/dqt/config_loader.py，去除应用、端口、鉴权和数据库字段 |
| src/backend/api、services、infrastructure、main.py | 从代码删除 |
| src/frontend 与 tests/frontend 的受版本控制文件 | 删除 |
| 原 SQLite persistence adapter、API/前端专属测试和文档 | 删除 |
| 原算法单元/集成测试 | 保留并更新导入路径 |
| run_tests.py | 改为科研 Python 测试与质量入口 |
| 前端缓存、node_modules 等本地未跟踪文件 | 移至被忽略的 outputs/legacy-local，不属于实验工程 |
| 旧本地 data/sessions、data/logs | 不作为新实验输入或缓存，仍由 Git 忽略 |

实验层新增 datasets、methods、worker、evaluation、reports；原算法没有重新设计。原有假价格估算不会作为科研费用使用，科研结果费用保持 null。

## 来源适配

模板通用代码、Agent compiler 和缓存布局保留。模板测试放入 tests/integration/template，调整根路径；模板文档移至 doc/template 并修正安装命令、方向入口与日期。src/project/agent.py 保留原 echo 示例，实际研究从 tree_search 工厂进入。此仓库是研究工程，不维护向外导出的 template-manifest；`paper template export` 应从原 PaperTemplate 执行。

原有算法库仍保留部分内容级 fallback，研究 worker 用 RecordedClient 将供应商请求/结构化契约失败转为不可吞掉的 ProviderFailed，使失败不被误记为成功。预算终止与执行异常分开记录。论文汇总与问题最终回答明确分离；全部模型调用包含在 result/tree/answer_report 的一致 token 账本中。

## 模型配置

生成与决策统一使用 deepseek-flash。[DeepSeek 2026-09-10 官方公告](https://www.deepseek.com/en/news/deepseek-v4-1-flash/)将其标识为 DeepSeek-V4.1-Flash。2026-09-12 已通过真实 models 接口确认名称可用。用户提供的凭据保存在 Git 忽略的项目 .env，仅用于调用模型，不写入实验配置快照。

## 验收与研究边界

迁移前原算法的 121 项测试通过；迁移后验证原算法回归、模板缓存与统计、进程隔离、参考答案隔离、预算和失败恢复。真实 Flash E2E 完整执行 validate、plan、run、复用、CSV 导出及 archive。最终检查数量与示例输出见 outputs/validation/validation.json。

真实验收中观察到原算法可能在根回答抽取至少 50 条事实后触发“已有足够信息”规则，得到单根树。这个阈值是保留的原行为，未为了通过测试而改变算法；真实测试允许有明确剪枝原因的合法终止，离线集成另覆盖分支展开。

目前还不能据此声称搜索树优于其他方法：真实问题集合、可靠评分器、直接回答基线、等成本比较和消融研究尚未设计。示例的 completed 只说明执行成功；没有 reference 的 exact_match 为 null。后续科学设计可以直接通过 project 组件和 Study 配置扩展。
