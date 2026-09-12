"""An isolated, bounded agent loop with replaceable model, tools and memory."""

from dataclasses import dataclass, field
from typing import Any, Protocol
import time
from framework.components import configured, build


class Model(Protocol):
    def generate(self, messages: list[dict], *, tools: list[dict], context) -> dict: ...


class Tool(Protocol):
    schema: dict

    def invoke(self, arguments: dict, *, context) -> Any: ...


class Memory(Protocol):
    def read(self) -> list[dict]: ...
    def append(self, message: dict) -> None: ...


@dataclass
class ListMemory:
    messages: list[dict] = field(default_factory=list)

    def read(self):
        return list(self.messages)

    def append(self, message):
        self.messages.append(message)


class SingleAgent:
    def __init__(self, model, tools=None, memory=None, system=""):
        self.model, self.tools, self.memory = model, tools or {}, memory or ListMemory()
        self.system = system

    def run(self, case, context):
        limit = context.limits.get("max_steps")
        if not isinstance(limit, int) or limit < 1:
            raise ValueError("Agent requires positive max_steps")
        start = time.monotonic()
        events, tokens, known_tokens, calls, answer, status, steps = (
            [],
            0,
            True,
            0,
            None,
            "step_limit",
            0,
        )
        cost, known_cost = 0.0, True
        if self.system:
            self.memory.append({"role": "system", "content": self.system})
        self.memory.append({"role": "user", "content": case["input"]})
        for step in range(limit):
            if (
                context.limits.get("time_seconds") is not None
                and time.monotonic() - start >= context.limits["time_seconds"]
            ):
                status = "time_limit"
                break
            response = self.model.generate(
                self.memory.read(),
                tools=[
                    {"name": name, **tool.schema} for name, tool in self.tools.items()
                ],
                context=context,
            )
            steps = step + 1
            usage = response.get("tokens")
            if usage is None:
                known_tokens = False
                if context.limits.get("tokens") is not None:
                    raise ValueError("Token-limited runs require provider token usage")
            else:
                if not isinstance(usage, int) or isinstance(usage, bool) or usage < 0:
                    raise ValueError("Provider tokens must be a nonnegative integer")
                tokens += usage
            if response.get("cost") is None:
                known_cost = False
            else:
                cost += float(response["cost"])
            events.append({"type": "model", "step": step, "response": response})
            self.memory.append({"role": "assistant", **response})
            if (
                context.limits.get("time_seconds") is not None
                and time.monotonic() - start >= context.limits["time_seconds"]
            ):
                status = "time_limit"
                break
            if (
                context.limits.get("tokens") is not None
                and tokens >= context.limits["tokens"]
            ):
                status = "token_limit"
                break
            if response.get("tool"):
                name = response["tool"]
                if name not in self.tools:
                    status = "invalid_tool"
                    break
                calls += 1
                # No automatic retry; an exception remains an execution failure.
                value = self.tools[name].invoke(
                    response.get("arguments", {}), context=context
                )
                event = {"role": "tool", "name": name, "content": value}
                self.memory.append(event)
                events.append({"type": "tool", "step": step, **event})
                if (
                    context.limits.get("time_seconds") is not None
                    and time.monotonic() - start >= context.limits["time_seconds"]
                ):
                    status = "time_limit"
                    break
            else:
                answer, status = response.get("content", ""), "completed"
                break
        return {
            "status": status,
            "answer": answer,
            "events": events,
            "messages": self.memory.read(),
            "steps": steps,
            "tokens": tokens if known_tokens else None,
            "tool_calls": calls,
            "cost": cost if known_cost and steps else None,
            "elapsed_seconds": time.monotonic() - start,
        }


def create_agent(model, tools=None, memory=None, system=""):
    return SingleAgent(
        build(configured(model, default="project.agent:scripted_model")),
        {
            name: build(configured(raw, default="project.agent:echo_tool"))
            for name, raw in (tools or {}).items()
        },
        build(configured(memory, default="workflows.agent.runner:list_memory"))
        if memory
        else ListMemory(),
        system,
    )


def list_memory():
    return ListMemory()


create_agent.__paper_dependencies__ = (SingleAgent, ListMemory)
