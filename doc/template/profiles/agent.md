# Agent 方向

> Last Updated: 2026-09-12; imported from PaperTemplate (Agent profile).

流程为任务清单 → 独立 Agent 循环 → 结果/轨迹 → 独立评分。每个 case/repeat 都通过方法工厂创建新执行器、工具实例和记忆。没有自动重放工具调用或隐式重试。

数据工厂返回列表：

```python
[{"id": "q1", "input": "Question", "split": "test",
  "reference": "Answer", "unit_id": "q1", "metadata": {"category": "lookup"}}]
```

id 必须唯一，split 为 train/dev/validation/test。单个 Agent 只接收 id、input、公开 metadata 和 RunContext。reference 留在评分阶段；不要把隐藏答案放入公开 metadata。

```yaml
methods:
  - id: baseline
    factory: workflows.agent.runner:create_agent
    params:
      model:
        factory: project.agent:scripted_model
      tools:
        echo: {factory: project.agent:echo_tool}
      memory: {factory: workflows.agent.runner:list_memory}
      system: "Solve the current task."
```

接口位于 `workflows.agent.runner`：

- Model.generate(messages, *, tools, context) 返回 `{content, tokens?}` 或 `{tool, arguments, tokens?}`。
- Tool 提供 schema 和 invoke(arguments, *, context)。
- Memory 提供 read()、append(message)。
- 自定义方法工厂可返回任意具有 run(case, context) 方法的执行器，替换默认 SingleAgent。

`flow: evaluate` 必须配置 `params.limits.max_steps`。可选 time_seconds 和 tokens 都应为正。时间预算在模型调用前后检查，不能强行中止正在阻塞的任意 Python/网络调用，具体服务仍应实现请求超时；工具耗时在下一轮边界检查。token 上限也在收到模型使用量后检查，服务适配器可利用 context.limits 在请求端限制输出。

业务状态包括 completed、step_limit、time_limit、token_limit、invalid_tool；达到预算不会被错误标记为执行故障。未知 token 数记录 null；要求 token 预算但模型不返回用量时会报错。工具抛异常属于执行故障，保存失败记录且不重试。

默认评分 exact_match 输出 success 及执行消耗。真实任务可替换评分工厂，单独读取 reference。搜索 select 模式要求 dev/validation 问题，再对被选候选运行测试。离线示例见 `src/project/agent.py` 与 `configs/studies/agent.yaml`。
