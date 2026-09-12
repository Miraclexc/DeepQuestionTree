"""Offline contract example; replace these factories in your own project."""

from workflows.agent.runner import ListMemory, SingleAgent


def cases():
    return [
        {"id": f"{split}-{i}", "input": text, "reference": text, "split": split}
        for split in ("dev", "test")
        for i, text in enumerate(("alpha", "beta"))
    ]


class ScriptedModel:
    def __init__(self, use_tool=True):
        self.use_tool = use_tool

    def generate(self, messages, *, tools, context):
        if messages[-1]["role"] == "tool":
            return {"content": messages[-1]["content"], "tokens": 1}
        text = next(m["content"] for m in messages if m["role"] == "user")
        return (
            {"tool": "echo", "arguments": {"text": text}, "tokens": 1}
            if self.use_tool
            else {"content": text, "tokens": 1}
        )


class EchoTool:
    schema = {
        "description": "Return the supplied text",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}}},
    }

    def invoke(self, arguments, *, context):
        return arguments["text"]


def scripted_model(use_tool=True):
    return ScriptedModel(use_tool)


def echo_tool():
    return EchoTool()


def runner(use_tool=True):
    return SingleAgent(ScriptedModel(use_tool), {"echo": EchoTool()}, ListMemory())


runner.__paper_dependencies__ = (ScriptedModel, EchoTool, SingleAgent, ListMemory)
scripted_model.__paper_dependencies__ = (ScriptedModel,)
echo_tool.__paper_dependencies__ = (EchoTool,)
