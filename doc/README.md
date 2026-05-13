# Documentation Index

> Last Updated: 2026-05-12
>
> 本页唯一负责：按受众和职责组织文档入口，不承载实现细节本身。

先从根目录 [`README.md`](../README.md) 获取最短启动路径，再按下面的受众选择文档。

## 用户使用

| Document | 唯一职责 |
|---|---|
| [user-guide.md](./user-guide.md) | 面向本地使用者的完整操作手册：启动、Token 设置、创建探索、查看节点、生成报告、导出、清理数据与常见问题。 |

## 开发维护

| Document | 唯一职责 |
|---|---|
| [developer-guide.md](./developer-guide.md) | 面向开发者的环境基线、目录职责、read-model / infrastructure 边界、前后端调试方式、变更同步点和文档维护规则。 |

## 测试与验收

| Document | 唯一职责 |
|---|---|
| [testing-and-e2e.md](./testing-and-e2e.md) | 项目级测试总览：`run_tests.py` 语义、质量门禁、本地验收约束、真实 provider E2E 与手动验收主流程。 |
| [frontend-testing.md](./frontend-testing.md) | 前端专属测试细节：Vitest、MSW、Playwright、stub、浏览器 smoke 和前端命令。 |

## 架构与接口

| Document | 唯一职责 |
|---|---|
| [project-overview.md](./project-overview.md) | 当前真实架构、运行时约束、配置边界、数据流和已知原型边界。 |
| [application-layer-and-auth.md](./application-layer-and-auth.md) | 统一 API 路由、鉴权规则、错误响应与 read-model 契约。 |
| [llm-structured-output-contract.md](./llm-structured-output-contract.md) | 后端 LLM 结构化输出契约：`text` / `json_object` / `json_array`、调用方映射、provider 边界与 fallback 规则。 |

## Recommended Reading Paths

### 如果你是使用者

1. [`README.md`](../README.md)
2. [`user-guide.md`](./user-guide.md)

### 如果你是开发者

1. [`README.md`](../README.md)
2. [`developer-guide.md`](./developer-guide.md)
3. [`project-overview.md`](./project-overview.md)
4. [`llm-structured-output-contract.md`](./llm-structured-output-contract.md)
5. [`application-layer-and-auth.md`](./application-layer-and-auth.md)
6. [`testing-and-e2e.md`](./testing-and-e2e.md)
