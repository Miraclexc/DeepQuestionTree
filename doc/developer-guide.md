# 开发指南

> Last Updated: 2026-09-12

## 环境与目录

```powershell
uv sync --group dev
uv run python run_tests.py quality
uv run pytest tests/ -v
```

只通过 UV 管理 Python 环境和依赖，同时维护 pyproject.toml 与 uv.lock。本仓库为可安装的 src-layout 项目，`paper` 指向 `framework.runtime.cli:main`。请在仓库根执行命令；配置、prompts 和数据文件随源码管理。

| 路径 | 职责 |
|---|---|
| src/framework/ | 来自 PaperTemplate 的公共执行、缓存、报告、统计与调度核心 |
| src/workflows/agent/ | Agent workflow compiler、输入/参考答案隔离与评分 DAG |
| src/project/dqt/ | 迁入的搜索树核心与 LLM 模块 |
| src/project/methods.py | 方法工厂、公开参数校验、子进程隔离、凭据传递 |
| src/project/worker.py | 原算法装配、预算、调用轨迹、搜索树与回答产物 |
| src/project/datasets.py | JSONL 问题集合加载与验证 |
| src/project/evaluation.py | 独立离线评分和运行统计 |
| src/project/reports.py | 仅读取已提交指标的论文汇总 |
| src/project/agent.py | 原模板保留的离线接口示例，供模板回归使用 |
| config/ | 原算法默认参数和 Jinja prompts |
| configs/studies/ | 可执行 Study 配置 |
| datasets/ | 版本化实验输入，当前仅迁移示例 |
| tests/unit/、tests/integration/、tests/e2e/ | 分层验证 |
| outputs/ | 运行、缓存、归档及验证输出，Git 忽略 |
| template-origin.json | 迁入模板文件的原始 SHA-256 与来源映射 |

## 修改边界

新增算法时先写失败测试，再增加 `project` 中的方法工厂，返回提供 `run(case, context)` 的对象。不要让 DAG 核心识别具体搜索算法。

所有影响结果的辅助代码、prompt、配置必须列入方法的 `code_dependencies`；也可通过 `__paper_dependencies__` 声明 Python 实现依赖。当前 tree-search 配置覆盖 `src/project/dqt`、worker、prompts 和算法默认配置。不同的远程模型发布版必须更新方法 version。

数据文件内容由加载结果投影进入 case 身份。只修改 reference 时重做评分；若同时改了加载器版本或输入，相关执行会失效。不要将整个含 reference 的文件另加到 method 的 code_dependencies，否则会扩大失效范围。

评分函数只读取 result/reference；新增指标不会增加模型调用。报告只读取已提交产物；不能在报告函数中重建搜索树、重新问模型或覆写原始结果。

模板源码保持来源可追踪，格式检查不重排 framework/workflows 和原模板测试；项目算法与新增适配层继续执行 black/isort，原算法执行 mypy。真实 API 测试不能使用 mock。修改后同步 [实验指南](experiment-guide.md) 和有关契约；新文档加入索引。
