"""
Mock 数据 - 示例会话
提供预设的测试会话数据
"""
from src.backend.core.schema import (
    SessionData, Node, QAInteraction, Fact, SessionStatus
)


def create_simple_session():
    """创建简单的测试会话"""
    session = SessionData(global_goal="探索机器学习基础")

    # 根节点
    root = Node(
        id=session.root_node_id,
        depth=0,
        interaction=QAInteraction(
            question="探索机器学习基础",
            answer="机器学习是人工智能的一个分支...",
            summary="机器学习简介"
        )
    )
    session.add_node(root)

    return session


def create_complex_session():
    """创建复杂的测试会话（包含多层节点）"""
    session = SessionData(global_goal="深入理解深度学习")

    # 根节点
    root = Node(
        id=session.root_node_id,
        depth=0,
        interaction=QAInteraction(
            question="深入理解深度学习",
            answer="深度学习是机器学习的一个子领域...",
            summary="深度学习概述"
        )
    )
    root.state.visit_count = 10
    root.state.value_sum = 75.0
    session.add_node(root)

    # 第一层子节点
    child1 = Node(
        parent_id=root.id,
        depth=1,
        interaction=QAInteraction(
            question="神经网络的基本原理是什么？",
            answer="神经网络模拟人脑神经元的工作方式...",
            summary="神经网络原理",
            tokens_used=200
        )
    )
    child1.state.visit_count = 5
    child1.state.value_sum = 40.0
    child1.new_facts = [
        Fact(
            content="神经网络由输入层、隐藏层和输出层组成",
            source_node_id=child1.id,
            confidence=0.95
        ),
        Fact(
            content="反向传播是训练神经网络的主要算法",
            source_node_id=child1.id,
            confidence=0.92
        )
    ]
    session.add_node(child1)
    root.children_ids.append(child1.id)

    child2 = Node(
        parent_id=root.id,
        depth=1,
        interaction=QAInteraction(
            question="深度学习有哪些常见应用？",
            answer="深度学习广泛应用于图像识别、语音识别等领域...",
            summary="深度学习应用",
            tokens_used=180
        )
    )
    child2.state.visit_count = 4
    child2.state.value_sum = 28.0
    child2.new_facts = [
        Fact(
            content="深度学习在计算机视觉领域取得重大突破",
            source_node_id=child2.id,
            confidence=0.90
        )
    ]
    session.add_node(child2)
    root.children_ids.append(child2.id)

    # 第二层子节点
    grandchild = Node(
        parent_id=child1.id,
        depth=2,
        interaction=QAInteraction(
            question="什么是激活函数？",
            answer="激活函数引入非线性，使神经网络能够学习复杂模式...",
            summary="激活函数",
            tokens_used=150
        )
    )
    grandchild.state.visit_count = 3
    grandchild.state.value_sum = 21.0
    grandchild.new_facts = [
        Fact(
            content="常见的激活函数包括 ReLU、Sigmoid 和 Tanh",
            source_node_id=grandchild.id,
            confidence=0.98
        )
    ]
    session.add_node(grandchild)
    child1.children_ids.append(grandchild.id)

    # 添加全局事实
    for node in [child1, child2, grandchild]:
        for fact in node.new_facts:
            session.add_global_fact(fact)

    # 更新统计
    session.total_simulations = 15
    session.total_tokens_used = 530

    return session


def create_session_with_pruned_nodes():
    """创建包含已剪枝节点的会话"""
    session = create_complex_session()

    # 剪枝一个节点
    nodes_list = list(session.nodes.values())
    if len(nodes_list) > 2:
        nodes_list[2].mark_pruned("重复问题")

    return session


def create_completed_session():
    """创建已完成的会话"""
    session = create_complex_session()
    session.status = SessionStatus.COMPLETED
    return session


# 预定义的问题列表
SAMPLE_QUESTIONS = [
    "深度学习的核心原理是什么？",
    "Transformer 架构如何工作？",
    "什么是注意力机制？",
    "卷积神经网络有什么特点？",
    "循环神经网络适用于什么场景？",
    "如何防止过拟合？",
    "批量归一化的作用是什么？",
    "迁移学习有哪些应用？",
    "生成对抗网络的原理是什么？",
    "强化学习与监督学习有何不同？"
]

# 预定义的事实列表
SAMPLE_FACTS = [
    {
        "content": "深度学习是机器学习的一个子领域",
        "confidence": 0.98
    },
    {
        "content": "Transformer 架构于 2017 年由 Google 提出",
        "confidence": 0.99
    },
    {
        "content": "注意力机制允许模型关注输入的不同部分",
        "confidence": 0.95
    },
    {
        "content": "卷积神经网络特别适合处理图像数据",
        "confidence": 0.96
    },
    {
        "content": "LSTM 网络可以缓解循环神经网络的梯度消失问题",
        "confidence": 0.94
    },
    {
        "content": "Dropout 是一种常用的正则化技术",
        "confidence": 0.93
    },
    {
        "content": "Adam 优化器结合了动量和自适应学习率",
        "confidence": 0.92
    },
    {
        "content": "预训练模型可以大大减少训练时间",
        "confidence": 0.90
    },
    {
        "content": "GAN 由生成器和判别器组成",
        "confidence": 0.97
    },
    {
        "content": "强化学习通过奖励信号进行学习",
        "confidence": 0.91
    }
]

# 预定义的回答模板
SAMPLE_ANSWERS = {
    "原理类": [
        "该技术的核心原理是通过{method}来实现{goal}。",
        "从技术角度来看，{concept}主要依赖于{foundation}。",
        "这个机制的工作方式可以概括为：首先{step1}，然后{step2}，最后{step3}。"
    ],
    "应用类": [
        "该技术在{domain}领域有广泛应用，特别是在{scenario}方面。",
        "实际应用案例包括{case1}、{case2}和{case3}。",
        "业界普遍使用该技术来解决{problem}。"
    ],
    "对比类": [
        "与{alternative}相比，该方法的优势在于{advantage}。",
        "两种技术的主要区别在于：{difference}。",
        "在{aspect}方面，{method1}优于{method2}。"
    ]
}
