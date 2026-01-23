# DeepQuestionTree 测试套件

## 📋 测试概览

本项目包含完整的单元测试和集成测试，覆盖了所有核心功能模块。

### 测试结构

```
tests/
├── conftest.py              # Pytest 配置和公共 Fixtures
├── unit/                    # 单元测试
│   ├── test_schema.py       # 数据模型和 UCT 算法测试
│   ├── test_compressor.py   # 压缩模块测试
│   ├── test_questioner.py   # 提问模块测试
│   └── test_pruner.py       # 剪枝模块测试
├── integration/             # 集成测试
│   ├── test_mcts_flow.py    # MCTS 完整流程测试
│   ├── test_persistence.py  # 持久化功能测试
│   └── test_api.py          # FastAPI 端点测试
└── mock_data/               # Mock 数据
    └── sample_sessions.py   # 示例会话数据
```

## 🚀 快速开始

### 1. 安装测试依赖

```bash
pip install -r requirements.txt
```

测试相关依赖包括：
- `pytest` - 测试框架
- `pytest-cov` - 覆盖率报告
- `pytest-asyncio` - 异步测试支持
- `httpx` - API 测试客户端

### 2. 运行测试

#### 运行所有测试
```bash
pytest
# 或
python run_tests.py all
```

#### 仅运行单元测试
```bash
pytest tests/unit/ -m unit
# 或
python run_tests.py unit
```

#### 仅运行集成测试
```bash
pytest tests/integration/ -m integration
# 或
python run_tests.py integration
```

#### 生成覆盖率报告
```bash
pytest --cov=src/backend --cov-report=html
# 或
python run_tests.py coverage
```

覆盖率报告会生成在 `htmlcov/index.html`

#### 运行特定测试文件
```bash
pytest tests/unit/test_schema.py -v
# 或
python run_tests.py tests/unit/test_schema.py
```

#### 运行特定测试函数
```bash
pytest tests/unit/test_schema.py::TestNode::test_uct_value_calculation -v
```

## 📊 测试覆盖范围

### 单元测试 (Unit Tests)

#### 1. **test_schema.py** - 数据模型测试
- ✅ Fact 模型创建和验证
- ✅ QAInteraction 模型
- ✅ NodeState 平均值计算
- ✅ Node UCT 值计算（完整公式验证）
- ✅ SessionData 节点管理
- ✅ 最佳路径获取
- ✅ 树统计信息
- ✅ UCT 算法核心逻辑（探索 vs 利用平衡）

**关键测试点：**
- UCT 未访问节点返回 ∞
- UCT 公式：exploitation + C × sqrt(ln(N)/n)
- 探索奖励随访问次数衰减
- C 参数对探索的影响

#### 2. **test_compressor.py** - 压缩模块测试
- ✅ 事实提取（基本功能 + 空文本处理）
- ✅ 上下文压缩（需要/不需要压缩）
- ✅ 事实去重合并（无重复/有重复）
- ✅ 置信度替换逻辑
- ✅ 手动事实提取（降级方案）
- ✅ 交互总结
- ✅ 特殊字符处理
- ✅ 边界情况（空列表、空字符串）

#### 3. **test_questioner.py** - 提问模块测试
- ✅ 候选问题生成（不同 k 值）
- ✅ 问题价值评估（0-10 分范围）
- ✅ 重复问题检测（完全相同/相似）
- ✅ 相似度阈值测试
- ✅ 历史问题数量限制（1000 个）
- ✅ 从文本提取问题
- ✅ 分数解析（数字/JSON/文本）
- ✅ 默认问题生成
- ✅ 边界情况（空上下文、空字符串）

#### 4. **test_pruner.py** - 剪枝模块测试
- ✅ 深度限制剪枝
- ✅ 重复问题剪枝
- ✅ 低价值路径剪枝
- ✅ 信息饱和剪枝（50+ 事实）
- ✅ 正常节点不剪枝
- ✅ 路径摘要生成
- ✅ 到根节点的路径获取
- ✅ 子树剪枝（递归标记）
- ✅ 剪枝统计信息
- ✅ 历史问题获取

### 集成测试 (Integration Tests)

#### 1. **test_mcts_flow.py** - MCTS 流程测试
- ✅ MCTS 引擎初始化
- ✅ Selection 步骤（选择最优叶子）
- ✅ 单次 MCTS 迭代
- ✅ 多次迭代循环
- ✅ 停止条件（最大模拟次数/无活跃节点）
- ✅ 树统计信息
- ✅ 获取最佳子节点
- ✅ 回传播更新所有祖先
- ✅ 回传播价值累积

#### 2. **test_persistence.py** - 持久化测试
- ✅ 会话保存（原子写入）
- ✅ 会话加载（JSON 反序列化）
- ✅ 数据一致性验证
- ✅ 加载不存在的会话
- ✅ 会话删除
- ✅ 列出所有会话
- ✅ 会话备份
- ✅ 会话数量统计
- ✅ JSON 结构验证
- ✅ 临时文件机制验证
- ✅ 边界情况（空会话、损坏 JSON、空目录）

#### 3. **test_api.py** - API 端点测试
- ✅ 启动会话 (POST /api/start)
- ✅ 获取状态 (GET /api/status)
- ✅ 停止会话 (POST /api/stop)
- ✅ 获取树数据 (GET /api/tree)
- ✅ 列出会话 (GET /api/sessions)
- ✅ 获取节点详情 (GET /api/node/{id})
- ✅ 加载会话 (POST /api/session/{id}/load)
- ✅ 获取报告 (GET /api/report)
- ✅ 重新加载配置 (POST /api/config/reload)
- ✅ 完整工作流测试
- ✅ 会话重启测试
- ✅ CORS 配置测试

## 🔧 测试配置

### pytest.ini
```ini
[pytest]
testpaths = tests
python_files = test_*.py
addopts =
    -v
    --strict-markers
    --tb=short
    --cov=src/backend
    --cov-report=html
    --asyncio-mode=auto
```

### 自定义标记 (Markers)
- `@pytest.mark.unit` - 单元测试
- `@pytest.mark.integration` - 集成测试
- `@pytest.mark.asyncio` - 异步测试
- `@pytest.mark.slow` - 慢速测试

### 公共 Fixtures (conftest.py)
- `test_settings` - 测试配置
- `mock_llm_client` - Mock LLM 客户端
- `embedding_manager` - Embedding 管理器
- `sample_session` - 示例会话
- `sample_facts` - 示例事实列表
- `sample_nodes` - 示例节点树
- `temp_session_dir` - 临时存储目录

## 📦 Mock 数据

### sample_sessions.py
提供预设的测试会话：
- `create_simple_session()` - 简单会话（仅根节点）
- `create_complex_session()` - 复杂会话（多层节点树）
- `create_session_with_pruned_nodes()` - 包含已剪枝节点
- `create_completed_session()` - 已完成的会话

还包括：
- `SAMPLE_QUESTIONS` - 10 个预设问题
- `SAMPLE_FACTS` - 10 个预设事实
- `SAMPLE_ANSWERS` - 回答模板（原理类/应用类/对比类）

## 🎯 测试最佳实践

### 1. 使用 Mock 模式
所有测试默认使用 `MockClient`，避免消耗 API Token：
```python
@pytest.fixture
def mock_llm_client():
    return MockClient()
```

### 2. 异步测试
使用 `@pytest.mark.asyncio` 标记异步测试：
```python
@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result is not None
```

### 3. 临时目录
使用 `tmp_path` Fixture 创建临时文件：
```python
def test_file_operation(tmp_path):
    file_path = tmp_path / "test.json"
    # 测试代码
```

### 4. 参数化测试
对多种输入进行测试：
```python
@pytest.mark.parametrize("depth,expected", [
    (0, False),
    (5, False),
    (10, True)
])
def test_depth_pruning(depth, expected):
    # 测试代码
```

## 📈 预期覆盖率

目标覆盖率：**80%+**

核心模块预期覆盖率：
- `core/schema.py` - 95%+
- `modules/compressor.py` - 85%+
- `modules/questioner.py` - 85%+
- `modules/pruner.py` - 85%+
- `modules/persistence.py` - 90%+
- `core/mcts_engine.py` - 75%+ （部分功能待实现）

## 🐛 故障排除

### 问题：导入错误
```
ModuleNotFoundError: No module named 'src'
```
**解决方案**：确保在项目根目录运行测试，或设置 PYTHONPATH：
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest
```

### 问题：异步测试失败
```
ScopeMismatch: You tried to access the function scoped fixture event_loop
```
**解决方案**：确保安装了 `pytest-asyncio` 并在 pytest.ini 中配置：
```ini
asyncio_mode = auto
```

### 问题：覆盖率报告未生成
**解决方案**：确保安装了 `pytest-cov`：
```bash
pip install pytest-cov
```

## 📝 添加新测试

### 添加单元测试
1. 在 `tests/unit/` 创建 `test_<module>.py`
2. 导入要测试的模块
3. 创建测试类和测试函数
4. 使用 `@pytest.mark.unit` 标记

### 添加集成测试
1. 在 `tests/integration/` 创建测试文件
2. 使用 `@pytest.mark.integration` 标记
3. 可能需要设置更复杂的 Fixtures

## 🔍 测试命令参考

```bash
# 详细输出
pytest -v

# 显示打印输出
pytest -s

# 运行失败的测试
pytest --lf

# 并行运行（需要 pytest-xdist）
pytest -n auto

# 只运行匹配的测试
pytest -k "test_uct"

# 生成 JUnit XML 报告
pytest --junit-xml=report.xml

# 只运行某个标记的测试
pytest -m unit

# 停止于第一个失败
pytest -x

# 显示最慢的 10 个测试
pytest --durations=10
```

## 📚 相关文档

- [Pytest 官方文档](https://docs.pytest.org/)
- [Pytest-asyncio 文档](https://pytest-asyncio.readthedocs.io/)
- [Coverage.py 文档](https://coverage.readthedocs.io/)

## ✅ 测试检查清单

在提交代码前确保：
- [ ] 所有测试通过 (`pytest`)
- [ ] 覆盖率 ≥ 80% (`pytest --cov`)
- [ ] 无 linting 错误 (`black src/ tests/`)
- [ ] 类型检查通过 (`mypy src/`)
- [ ] 新功能有对应测试
- [ ] 边界情况有测试覆盖

---

**最后更新**: 2026-01-21
**测试框架版本**: Pytest 7.4+
