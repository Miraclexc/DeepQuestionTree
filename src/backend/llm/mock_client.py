"""
Mock LLM 客户端
用于在不消耗 Token 的情况下开发和测试 MCTS 逻辑
"""
import json
import random
from typing import Dict, List, Any, Optional

from .client_interface import BaseLLMClient, CompletionResponse


class MockClient(BaseLLMClient):
    """
    Mock 客户端，根据输入关键词返回预设的虚假数据
    """

    def __init__(self):
        """初始化 Mock 客户端"""
        self.total_tokens_used = 0
        self.total_cost = 0.0
        self.request_count = 0

        # 预设的 Mock 响应库
        self.mock_questions = [
            "这个技术的底层原理是什么？",
            "它有哪些潜在的风险和挑战？",
            "在实际应用中有哪些成功案例？",
            "未来的发展趋势如何？",
            "与现有方案相比有什么优势？",
            "实施成本大概是多少？",
            "法律和合规方面需要考虑什么？",
            "对行业会产生什么影响？"
        ]

        self.mock_facts = [
            "该技术采用分布式架构",
            "处理速度比传统方法快3倍",
            "已经过大规模测试验证",
            "成本可降低40%以上",
            "支持多语言和多平台",
            "符合GDPR等数据保护法规",
            "有完善的文档和社区支持",
            "可扩展到百万级用户"
        ]

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        json_mode: bool = False
    ) -> CompletionResponse:
        """
        Mock 聊天完成
        """
        self.request_count += 1
        tokens = random.randint(100, 500)
        self.total_tokens_used += tokens

        # 获取最后一条消息
        last_msg = messages[-1]["content"] if messages else ""
        content = ""

        # 根据消息内容返回相应的 Mock 数据
        if "提出" in last_msg or "candidates" in last_msg or "候选" in last_msg or "question" in last_msg.lower():
            # 生成候选问题
            num_questions = min(
                max(3, random.randint(2, 5)),
                len(self.mock_questions)
            )
            selected_questions = random.sample(
                self.mock_questions,
                num_questions
            )
            content = json.dumps(selected_questions, ensure_ascii=False)

        elif "评估" in last_msg or "score" in last_msg or "信息增益" in last_msg:
            # 评估问题价值
            score = random.randint(1, 10)
            reasons = [
                "可能揭示新的技术细节",
                "有助于了解应用场景",
                "可能发现潜在风险",
                "能够补充关键信息",
                "探索性较强"
            ]
            content = json.dumps({
                "score": score,
                "reason": random.choice(reasons)
            }, ensure_ascii=False)

        elif (("提取" in last_msg and "事实" in last_msg) or "extract facts" in last_msg.lower()) and json_mode:
            # 提取事实
            num_facts = random.randint(2, 4)  # 至少返回2个事实
            selected_facts = random.sample(
                self.mock_facts,
                min(num_facts, len(self.mock_facts))
            )
            facts_list = [
                {
                    "content": fact,
                    "confidence": round(random.uniform(0.7, 1.0), 2)
                }
                for fact in selected_facts
            ]
            content = json.dumps(facts_list, ensure_ascii=False)

        elif "概括" in last_msg or "summarize" in last_msg or "总结" in last_msg:
            # 路径概括
            summaries = [
                "该路径主要探讨了技术原理",
                "发现了多个关键应用场景",
                "识别出重要风险因素",
                "确认了商业价值",
                "明确了技术优势"
            ]
            num_points = random.randint(2, 4)
            selected = random.sample(summaries, num_points)
            content = "\n".join([f"{i+1}. {s}" for i, s in enumerate(selected)])

        else:
            # 默认回答
            answer_templates = [
                "基于当前信息，{topic}是一个值得深入研究的方向。初步分析表明它具有{advantage}的特点。",
                "关于{topic}，我们的分析显示它在{aspect}方面表现突出，但还需要考虑{challenge}。",
                "{topic}的发展前景看好，特别是在{field}领域。不过实施时需要注意{consideration}。"
            ]

            topic = "这个问题"
            advantage = random.choice(["创新性", "高效性", "可靠性", "经济性"])
            aspect = random.choice(["性能", "易用性", "扩展性", "安全性"])
            challenge = random.choice(["技术难点", "成本问题", "用户接受度", "合规要求"])
            field = random.choice(["企业应用", "消费市场", "科研", "公共服务"])
            consideration = random.choice(["渐进式推进", "充分测试", "团队培训", "风险管控"])

            template = random.choice(answer_templates)
            answer = template.format(
                topic=topic,
                advantage=advantage,
                aspect=aspect,
                challenge=challenge,
                field=field,
                consideration=consideration
            )

            # 添加一些事实
            fact = random.choice(self.mock_facts)
            answer += f"\n\n关键信息：{fact}"

            content = answer
            
        return CompletionResponse(
            content=content,
            model="mock-model",
            tokens=tokens,
            cost=0.0
        )

    async def get_embedding(self, text: str) -> List[float]:
        """
        Mock 嵌入向量生成
        """
        self.request_count += 1
        self.total_tokens_used += len(text) // 4  # 粗略估算

        # 生成基于文本哈希的伪随机向量
        import hashlib
        hash_obj = hashlib.md5(text.encode())
        hash_hex = hash_obj.hexdigest()

        # 转换为 768 维向量（常见维度）
        vector = []
        for i in range(0, len(hash_hex), 2):
            # 将每对十六进制字符转换为 -1 到 1 之间的浮点数
            val = int(hash_hex[i:i+2], 16) / 255.0 * 2 - 1
            vector.append(val)

        # 补齐到 768 维
        while len(vector) < 768:
            vector.append(random.uniform(-1, 1))

        return vector[:768]

    async def get_usage_stats(self) -> Dict[str, Any]:
        """获取使用统计"""
        return {
            "total_tokens_used": self.total_tokens_used,
            "total_cost_usd": 0.0,  # Mock 客户端免费
            "total_requests": self.request_count,
            "average_tokens_per_request": self.total_tokens_used / max(self.request_count, 1),
            "note": "这是 Mock 客户端，没有真实的 Token 消耗"
        }

    async def reset_usage_stats(self) -> None:
        """重置使用统计"""
        self.total_tokens_used = 0
        self.total_cost = 0.0
        self.request_count = 0