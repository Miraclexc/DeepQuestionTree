"""Pure algorithm fixtures and opt-in real-provider experiment tests."""

import tempfile
from pathlib import Path

import pytest

from project.dqt import config_loader
from project.dqt.core.schema import Fact, Node, QAInteraction, SessionData
from project.dqt.llm.mock_client import MockClient

_TEST_RUNTIME = tempfile.TemporaryDirectory(prefix="dqt-tests-")
config_loader._settings = config_loader.Settings(
    storage=config_loader.StorageConfig(logs_dir=str(Path(_TEST_RUNTIME.name) / "logs"))
)


def pytest_addoption(parser):
    parser.addoption(
        "--run-e2e",
        action="store_true",
        default=False,
        help="Run real DeepSeek Flash CLI experiments",
    )


def pytest_ignore_collect(collection_path, config):
    return "e2e" in Path(str(collection_path)).parts and not config.getoption(
        "--run-e2e"
    )


@pytest.fixture
def test_settings():
    return config_loader.get_settings()


@pytest.fixture
def mock_llm_client():
    """提供 Mock LLM 客户端"""
    return MockClient()


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
