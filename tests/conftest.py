"""
Pytest 配置文件和公共 Fixtures
"""

import os
import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("SECURITY__API_TOKEN", "test-token")
os.environ.setdefault("APP__MOCK_LLM", "true")
os.environ.setdefault("APP__DEBUG", "true")
os.environ.setdefault("EMBEDDING__USE_LOCAL", "false")

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import src.backend.modules.persistence as persistence_module
from src.backend.config_loader import get_settings, reload_settings
from src.backend.core.schema import Fact, Node, QAInteraction, SessionData
from src.backend.llm.embedding import EmbeddingManager
from src.backend.llm.mock_client import MockClient
from src.backend.main import app
from src.backend.services.runtime import ExplorationRuntime
from tests.e2e.support import E2EConfigError, ManagedE2EServer, resolve_provider_profile

reload_settings()


TEST_DEFAULT_ENV = {
    "APP__MOCK_LLM": "true",
    "APP__DEBUG": "true",
    "EMBEDDING__USE_LOCAL": "false",
    "SECURITY__API_TOKEN": "test-token",
    "STORAGE__SESSION_DB_PATH": "data/sessions/deepquestiontree.sqlite3",
}


def pytest_addoption(parser):
    """注册 E2E 测试选项。"""
    group = parser.getgroup("e2e")
    group.addoption(
        "--run-e2e",
        action="store_true",
        default=False,
        help="Run real-provider E2E tests under tests/e2e.",
    )
    group.addoption(
        "--e2e-provider",
        action="store",
        default=None,
        choices=("openai-compatible", "deepseek"),
        help="Select the real provider profile used by tests/e2e.",
    )


def pytest_ignore_collect(collection_path, config):
    """默认不收集 tests/e2e，除非显式开启。"""
    path = Path(str(collection_path))
    normalized_parts = {part.lower() for part in path.parts}
    if "tests" in normalized_parts and "e2e" in normalized_parts:
        return not config.getoption("--run-e2e")
    return False


@pytest.fixture(scope="session")
def test_settings():
    """加载测试配置"""
    reload_settings()
    return get_settings()


@pytest.fixture
def mock_llm_client():
    """提供 Mock LLM 客户端"""
    return MockClient()


@pytest.fixture
def embedding_manager():
    """提供 Embedding 管理器"""
    manager = EmbeddingManager()
    manager.set_client(MockClient(), prefer_client=True)
    return manager


@pytest.fixture
def sample_session():
    """创建示例会话数据"""
    session = SessionData(global_goal="测试人工智能技术的未来发展趋势")

    # 创建根节点
    root_node = Node(
        id=session.root_node_id,
        depth=0,
        interaction=QAInteraction(
            question="测试人工智能技术的未来发展趋势",
            answer="人工智能技术正在快速发展...",
            summary="AI 技术发展概况",
        ),
    )
    session.add_node(root_node)
    session.bump_session_version()

    return session


@pytest.fixture
def sample_facts():
    """创建示例事实列表"""
    facts = [
        Fact(
            content="深度学习是机器学习的一个子领域",
            source_node_id="node_1",
            confidence=0.95,
        ),
        Fact(
            content="Transformer 架构于 2017 年提出",
            source_node_id="node_1",
            confidence=0.99,
        ),
        Fact(
            content="GPT-4 是目前最先进的语言模型之一",
            source_node_id="node_2",
            confidence=0.90,
        ),
    ]
    return facts


@pytest.fixture
def sample_nodes(sample_session):
    """创建示例节点树"""
    # 第一层子节点
    child1 = Node(
        parent_id=sample_session.root_node_id,
        depth=1,
        interaction=QAInteraction(
            question="深度学习的核心原理是什么？",
            answer="深度学习基于多层神经网络...",
            summary="深度学习原理",
        ),
    )
    child1.state.visit_count = 5
    child1.state.value_sum = 35.0  # 平均 7.0

    child2 = Node(
        parent_id=sample_session.root_node_id,
        depth=1,
        interaction=QAInteraction(
            question="AI 在医疗领域有哪些应用？",
            answer="AI 在医疗诊断、药物研发等方面...",
            summary="AI 医疗应用",
        ),
    )
    child2.state.visit_count = 3
    child2.state.value_sum = 18.0  # 平均 6.0

    # 第二层子节点
    grandchild = Node(
        parent_id=child1.id,
        depth=2,
        interaction=QAInteraction(
            question="神经网络是如何训练的？",
            answer="通过反向传播算法...",
            summary="神经网络训练",
        ),
    )
    grandchild.state.visit_count = 2
    grandchild.state.value_sum = 14.0  # 平均 7.0

    # 添加到会话
    sample_session.add_node(child1)
    sample_session.add_node(child2)
    sample_session.add_node(grandchild)

    # 更新父子关系
    root = sample_session.nodes[sample_session.root_node_id]
    root.children_ids = [child1.id, child2.id]
    child1.children_ids = [grandchild.id]

    return sample_session


@pytest.fixture
def temp_session_dir(tmp_path):
    """创建临时会话存储目录"""
    session_dir = tmp_path / "sessions"
    session_dir.mkdir()
    return session_dir


@pytest.fixture
def isolated_api_runtime(tmp_path, monkeypatch):
    """为 API 测试提供隔离的运行时与持久化目录。"""
    data_dir = tmp_path / "data"
    sessions_dir = data_dir / "sessions"
    logs_dir = data_dir / "logs"
    session_db_path = sessions_dir / "test.sqlite3"

    sessions_dir.mkdir(parents=True)
    logs_dir.mkdir(parents=True)

    monkeypatch.setenv("STORAGE__DATA_DIR", str(data_dir))
    monkeypatch.setenv("STORAGE__SESSIONS_DIR", str(sessions_dir))
    monkeypatch.setenv("STORAGE__SESSION_DB_PATH", str(session_db_path))
    monkeypatch.setenv("STORAGE__LOGS_DIR", str(logs_dir))
    monkeypatch.setenv("APP__MOCK_LLM", "true")
    monkeypatch.setenv("APP__DEBUG", "true")
    monkeypatch.setenv("EMBEDDING__USE_LOCAL", "false")
    monkeypatch.setenv("MCTS__PARALLEL_WORKERS", "1")
    monkeypatch.setenv("MCTS__MAX_SIMULATIONS", "100")
    monkeypatch.setenv("MCTS__MAX_DEPTH", "10")

    reload_settings()

    persistence_module._session_manager = None
    app.state.runtime = ExplorationRuntime()

    yield sessions_dir

    for key, value in TEST_DEFAULT_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("STORAGE__DATA_DIR", "data")
    monkeypatch.setenv("STORAGE__SESSIONS_DIR", "data/sessions")
    monkeypatch.setenv(
        "STORAGE__SESSION_DB_PATH",
        "data/sessions/deepquestiontree.sqlite3",
    )
    monkeypatch.setenv("STORAGE__LOGS_DIR", "data/logs")
    monkeypatch.setenv("MCTS__PARALLEL_WORKERS", "1")
    monkeypatch.setenv("MCTS__MAX_SIMULATIONS", "20")
    monkeypatch.setenv("MCTS__MAX_DEPTH", "10")
    reload_settings()
    persistence_module._session_manager = None
    app.state.runtime = ExplorationRuntime()


@pytest.fixture
async def api_client(isolated_api_runtime):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {get_settings().security.api_token}"},
    ) as client:
        yield client


@pytest.fixture
async def raw_api_client(isolated_api_runtime):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture(scope="session")
def e2e_provider_profile(pytestconfig):
    """解析 E2E provider profile；缺配置时给出清晰 skip 信息。"""
    requested_provider = pytestconfig.getoption("--e2e-provider")
    try:
        return resolve_provider_profile(
            provider=requested_provider,
            environ=os.environ,
        )
    except E2EConfigError as exc:
        pytest.skip(f"E2E configuration is incomplete: {exc}")


@pytest.fixture
async def e2e_server(tmp_path, e2e_provider_profile):
    """启动独立后端进程，供真实 API E2E 使用。"""
    server = ManagedE2EServer.start(
        project_root=project_root,
        profile=e2e_provider_profile,
        data_dir=tmp_path / f"e2e-{e2e_provider_profile.provider}",
    )
    try:
        await server.wait_until_ready()
        yield server
    finally:
        await server.stop()


# Pytest 标记定义
def pytest_configure(config):
    """注册自定义标记"""
    config.addinivalue_line("markers", "unit: 单元测试标记")
    config.addinivalue_line("markers", "integration: 集成测试标记")
    config.addinivalue_line("markers", "slow: 慢速测试标记")
    config.addinivalue_line("markers", "asyncio: 异步测试标记")
    config.addinivalue_line("markers", "e2e: 真实模型服务商黑盒 E2E 测试标记")
