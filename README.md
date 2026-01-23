# DeepQuestionTree

DeepQuestionTree 是一个基于 **MCTS (蒙特卡洛树搜索)** 和 **LLM (大语言模型)** 的深度问题探索系统。它通过“提问-回答-评估-再提问”的递归过程，构建一棵思维树，以深化对复杂问题的认知。

## 🎯 核心目标

深化对问题的认识，通过不断提问的方式尽可能让 AI 分析透彻问题并推演各种可能的情况。

## ✨ 核心特性

-   **提问树结构**: 动态生成的思维树（Questions & Answers）。
-   **MCTS 驱动**: 使用 UCT 算法平衡“探索”与“利用”，智能选择最有价值的提问路径。
-   **启发式评估**: LLM 扮演“裁判”，并在 Rollout 阶段预估信息增益，而非单纯生成长文。
-   **事实压缩**: 维护“已确认事实”列表，有效管理上下文窗口。
-   **多模式基准**:
    -   🔬 **科研 Idea 探索**
    -   📚 **全面主题回答**
    -   🔍 **根本原因寻找**

## 🛠️ 技术栈

-   **语言**: Python 3.12.11
-   **核心**: MCTS (Custom Implementation)
-   **LLM**: OpenAI API
-   **Embedding**: Sentence-Transformers (`DMetaSoul/sbert-chinese-general-v2-distill`) / API
-   **可视化**: Next.js + React Flow (Frontend)

## 📂 目录结构

```
DeepQuestionTree/
├── config/             # 配置文件 (settings, prompts)
├── src/
│   ├── backend/
│   │   ├── core/       # MCTS 引擎, 节点定义
│   │   ├── modules/    # 提问, 压缩, 剪枝, 持久化
│   │   ├── llm/        # LLM Client, Embedding
│   │   └── main.py     # 入口
│   └── frontend/       # Next.js 项目
└── requirements.txt    # Python 依赖
```

## 🚀 快速开始

### 1. 环境准备

确保安装 Python 3.12.11。

```bash
pip install -r requirements.txt
```

### 2. 配置

复制 `.env.example` (如有) 或直接修改 `config/settings.yaml` 配置你的 API Key。

### 3. 运行

#### 后端 (Backend)

**直接启动**:
```bash
python src/backend/main.py
```

**其它启动方式**:
```bash
uvicorn src.backend.main:app --reload --host 0.0.0.0 --port 8001
```

#### 前端 (Frontend)

```bash
cd src/frontend
npm run dev
```


### 4. 默认端口说明

- **3000**: 前端网页 (Web UI) - 默认对本地开放 (http://localhost:3000)

- **8001**: 后端 API (Backend) - 默认对本地开放 (http://localhost:8001)

若希望自定义端口，则修改frontend/.env.local文件