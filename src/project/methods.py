"""Process-isolated adapters around the existing MCTS implementation."""

import math
import os
import subprocess
import sys
from pathlib import Path

import yaml
from dotenv import dotenv_values

from framework.contracts import case_inputs, read_json, write_json

ROOT = Path(__file__).resolve().parents[2]


def credential_environment(name, path=None):
    env = dict(os.environ)
    if name not in env:
        value = dotenv_values(path or ROOT / ".env").get(name)
        if value:
            env[name] = value
    return env


def _settings(llm, mcts):
    from project.dqt.config_loader import LLMConfig, MCTSConfig

    llm, mcts = dict(llm or {}), dict(mcts or {})
    if "api_key" in llm:
        raise ValueError(
            "api_key must be supplied through the credential environment variable"
        )
    for values, model in ((llm, LLMConfig), (mcts, MCTSConfig)):
        unknown = set(values) - set(model.model_fields)
        if unknown:
            raise ValueError(f"Unknown settings: {sorted(unknown)}")
    for key in ("max_depth", "branch_factor", "max_simulations", "parallel_workers"):
        if key in mcts and (type(mcts[key]) is not int or mcts[key] < 1):
            raise ValueError(f"{key} must be a positive integer")
    if "exploration_constant" in mcts and (
        not math.isfinite(mcts["exploration_constant"])
        or mcts["exploration_constant"] < 0
    ):
        raise ValueError("exploration_constant must be finite and nonnegative")
    if mcts.get("parallel_workers", 1) != 1:
        raise ValueError(
            "Use runtime.max_workers for parallel cases; each tree uses one worker"
        )
    if llm.get("timeout", 60) <= 0:
        raise ValueError("LLM timeout must be positive")
    raw = yaml.safe_load((ROOT / "config/settings.yaml").read_text(encoding="utf-8"))
    # All public runtime settings are explicit and fingerprinted. Ambient UI env is ignored.
    resolved_llm = {**raw["llm"], **llm, "api_key": "", "max_retries": 0}
    resolved_mcts = {**raw["mcts"], **mcts, "parallel_workers": 1}
    return {
        "llm": LLMConfig(**resolved_llm).model_dump(exclude={"api_key"}),
        "mcts": MCTSConfig(**resolved_mcts).model_dump(),
        "checker": raw["checker"],
    }


class TreeSearch:
    def __init__(self, *, mock=False, llm=None, mcts=None, api_key_env="LLM__API_KEY"):
        if (
            type(mock) is not bool
            or not isinstance(api_key_env, str)
            or not api_key_env
        ):
            raise ValueError(
                "mock must be boolean and api_key_env must name an environment variable"
            )
        self.options = {
            "mock": mock,
            "settings": _settings(llm, mcts),
            "api_key_env": api_key_env,
        }

    def run(self, case, context):
        limits = dict(context.limits)
        if type(limits.get("max_steps")) is not int or limits["max_steps"] < 1:
            raise ValueError("max_steps must be a positive integer")
        for key in ("time_seconds", "tokens"):
            if key in limits and (
                isinstance(limits[key], bool)
                or not math.isfinite(limits[key])
                or limits[key] <= 0
            ):
                raise ValueError(f"{key} must be finite and positive")
        output = Path(context.output_dir).resolve()
        request_path = output / "request.json"
        write_json(
            request_path,
            {
                "case": case_inputs(case),
                "seed": context.seed,
                "limits": limits,
                "task": context.task,
                **self.options,
            },
        )
        env = {
            **credential_environment(self.options["api_key_env"]),
            "PYTHONUTF8": "1",
            "PYTHONUNBUFFERED": "1",
        }
        with (output / "worker.log").open("w", encoding="utf-8") as log:
            process = subprocess.run(
                [sys.executable, "-m", "project.worker", str(request_path)],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=limits.get("time_seconds", 3600) + 30,
            )
        if process.returncode:
            raise RuntimeError(
                "Tree worker failed; inspect the preserved worker.log and trace.json"
            )
        return read_json(output / "result.json")


def tree_search(mock=False, llm=None, mcts=None, api_key_env="LLM__API_KEY"):
    return TreeSearch(mock=mock, llm=llm, mcts=mcts, api_key_env=api_key_env)


tree_search.__paper_dependencies__ = (
    TreeSearch,
    _settings,
    case_inputs,
    credential_environment,
)
