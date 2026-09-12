from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol
import json
from copy import deepcopy
from framework.runtime.dag import ExecutionPlan


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False
        ),
        encoding="utf-8",
    )


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@dataclass(frozen=True)
class RunContext:
    output_dir: Path
    seed: int = 0
    limits: dict[str, Any] = field(default_factory=dict)
    run_id: str | None = None
    task: dict[str, Any] = field(default_factory=dict)
    resources: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkIdentity:
    study_id: str
    experiment_id: str
    method_id: str
    trial_id: str
    case_id: str = "all"
    repeat: int = 0
    stage: str = ""
    dimensions: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResultRecord:
    identity: dict[str, Any]
    status: str
    artifact_path: str
    source_run_id: str | None
    fingerprint: str
    reused: bool


@dataclass(frozen=True)
class MetricRecord:
    study_id: str
    experiment_id: str
    method_id: str
    trial_id: str
    case_id: str
    repeat: int
    metric: str
    value: float | None
    unit_id: str
    split: str = "test"
    dimensions: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompiledWorkflow:
    plan: ExecutionPlan
    identities: dict[str, WorkIdentity]
    metric_nodes: tuple[str, ...]
    manifests: dict[str, Any] = field(default_factory=dict)
    selections: dict[str, tuple[str, str]] = field(default_factory=dict)


class WorkflowCompiler(Protocol):
    def compile(self, study) -> CompiledWorkflow: ...


def case_inputs(row):
    return deepcopy(
        {
            "id": row["id"],
            "input": row["input"],
            "metadata": dict(row.get("metadata", {})),
        }
    )


def validate_cases(rows):
    ids = [row["id"] for row in rows]
    if any(not isinstance(value, str) or not value for value in ids):
        raise ValueError("Case ids must be nonempty strings")
    if len(ids) != len(set(ids)):
        raise ValueError("Case ids must be unique; a case cannot cross splits")
    for row in rows:
        if row.get("split", "test") not in ("train", "dev", "validation", "test"):
            raise ValueError("Case split must be train/dev/validation/test")
        if "input" not in row:
            raise ValueError("Every case needs input")
