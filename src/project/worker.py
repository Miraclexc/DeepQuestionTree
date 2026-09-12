"""One fresh process per case/repeat; all runtime state stays in its artifact."""

import asyncio
import os
import random
import sys
import time
from pathlib import Path

from framework.contracts import read_json, write_json


class BudgetReached(BaseException):
    """Bypasses legacy modules' Exception fallbacks, like cancellation does."""


class ProviderFailed(BaseException):
    """A failed model call must never become a successful research artifact."""


class RecordedClient:
    def __init__(self, client, limits, output):
        self.client, self.limits, self.output = client, limits, output
        self.start = time.monotonic()
        self.events = []
        self.tokens = 0
        self.known_tokens = True

    def check_budget(self):
        if time.monotonic() - self.start >= self.limits.get(
            "time_seconds", float("inf")
        ):
            raise BudgetReached("time_limit")
        if self.tokens >= self.limits.get("tokens", float("inf")):
            raise BudgetReached("token_limit")

    async def chat_completion(self, **kwargs):
        self.check_budget()
        try:
            response = await self.client.chat_completion(**kwargs)
        except Exception as exc:
            self.events.append(
                {"type": "provider_error", "error_type": type(exc).__name__}
            )
            write_json(self.output / "trace.json", self.events)
            raise ProviderFailed(
                "Model request failed; no fallback result was accepted"
            ) from None
        # Legacy clients represent absent usage as zero; treat it as unknown.
        self.known_tokens = self.known_tokens and response.tokens > 0
        self.tokens += response.tokens
        self.events.append(
            {
                "type": "llm",
                "request": kwargs,
                "response": {**response.model_dump(), "cost": None},
                "elapsed_seconds": time.monotonic() - self.start,
            }
        )
        write_json(self.output / "trace.json", self.events)
        if not self.known_tokens and "tokens" in self.limits:
            raise ProviderFailed("Token budget requires reported provider usage")
        self.check_budget()
        return response

    async def get_usage_stats(self):
        return await self.client.get_usage_stats()


async def execute(request, output):
    # Install a private snapshot before importing modules that initialize loggers.
    from project.dqt import config_loader

    raw = request["settings"]
    raw["llm"]["api_key"] = os.environ.get(request["api_key_env"], "")
    if not request["mock"] and not raw["llm"]["api_key"]:
        raise ValueError(
            f"Missing credential environment variable: {request['api_key_env']}"
        )
    raw["storage"] = {"logs_dir": str(output / "logs")}
    raw["logging"] = {"level": "WARNING"}
    config_loader._settings = config_loader.Settings.model_validate(raw)
    settings = config_loader.get_settings()
    random.seed(request["seed"])

    from project.dqt.core.mcts_engine import MCTSEngine
    from project.dqt.core.schema import (
        Node,
        QAInteraction,
        SessionData,
        SessionLlmUsage,
        SessionStatus,
    )
    from project.dqt.llm.llm_client import OpenAICompatibleClient
    from project.dqt.llm.mock_client import MockClient
    from project.dqt.llm.prompt_manager import PromptManager
    from project.dqt.modules.checker import Checker
    from project.dqt.modules.compressor import Compressor
    from project.dqt.modules.integrator import Integrator
    from project.dqt.modules.pruner import Pruner
    from project.dqt.modules.questioner import Questioner

    prompts = PromptManager(
        str(Path(__file__).resolve().parents[2] / "config/prompts.yaml")
    )
    underlying = MockClient() if request["mock"] else OpenAICompatibleClient()
    # Research runs record one attempt per request; no hidden retry in the UI client.
    if not request["mock"]:
        underlying.chat_completion = underlying.chat_completion.__wrapped__.__get__(
            underlying
        )
    client = RecordedClient(underlying, request["limits"], output)
    checker = Checker(client, prompt_manager=prompts)
    questioner = Questioner(client, checker=checker, prompt_manager=prompts)
    compressor = Compressor(client, checker=checker, prompt_manager=prompts)
    pruner = Pruner(client, checker=checker, prompt_manager=prompts)
    session = SessionData(
        global_goal=request["case"]["input"], mcts_config=settings.mcts.model_dump()
    )
    session.add_node(
        Node(
            id=session.root_node_id,
            depth=0,
            interaction=QAInteraction(question=session.global_goal, answer=""),
        )
    )
    engine = MCTSEngine(
        session,
        questioner=questioner,
        pruner=pruner,
        compressor=compressor,
        prompt_manager=prompts,
        settings=settings,
    )
    status, answer, steps = "completed", None, 0
    report = None
    stop_reason = "max_steps"
    try:
        for _ in range(request["limits"]["max_steps"]):
            client.check_budget()
            if engine.should_stop():
                stop_reason = "engine_stopped"
                break
            steps += 1
            await engine.run_step()
        report = await Integrator(client, prompt_manager=prompts).generate_final_report(
            session
        )
        if report.get("error"):
            raise RuntimeError("Answer synthesis failed")
        answer = report.get("full_report")
        if not answer:
            raise RuntimeError("Answer synthesis returned no answer")
    except BudgetReached as exc:
        status = str(exc)
        stop_reason = status
    except BaseException:
        session.status = SessionStatus.ERROR
        session.error_message = (
            "Research execution failed; see trace.json and worker.log"
        )
        raise
    finally:
        if session.status != SessionStatus.ERROR:
            session.status = (
                SessionStatus.COMPLETED
                if status == "completed"
                else SessionStatus.PAUSED
            )
        usage = SessionLlmUsage()
        for event in client.events:
            if event["type"] == "llm":
                response = event["response"]
                usage.record(response["model"], response["tokens"])
        session.llm_usage = usage
        session.total_tokens_used = usage.total_tokens
        if report is not None:
            report["llm_stats"] = usage.to_report_payload()
            write_json(output / "answer_report.json", report)
        write_json(output / "tree.json", session.model_dump(mode="json"))
        write_json(output / "trace.json", client.events)
        if not request["mock"]:
            await underlying.client.close()
    return {
        "status": status,
        "answer": answer,
        "mock": request["mock"],
        "seed": request["seed"],
        "steps": steps,
        "search_stop_reason": stop_reason,
        "simulations": session.total_simulations,
        "tokens": client.tokens if client.known_tokens else None,
        "llm_calls": len([e for e in client.events if e["type"] == "llm"]),
        "cost": None,
        "tool_calls": 0,
        "elapsed_seconds": time.monotonic() - client.start,
        "tree_nodes": len(session.nodes),
        "tree_depth": session.get_tree_depth(),
        "facts": len(session.global_facts),
        "pruned_nodes": sum(n.is_pruned for n in session.nodes.values()),
        "events": client.events,
    }


def main():
    path = Path(sys.argv[1]).resolve()
    try:
        write_json(
            path.parent / "result.json",
            asyncio.run(execute(read_json(path), path.parent)),
        )
    except ProviderFailed as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
