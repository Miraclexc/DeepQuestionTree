"""Versioned, direction-neutral Study configuration."""

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import re
import yaml

PROFILES = ("deep_learning", "agent", "rag")


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9_][A-Za-z0-9_.-]*", value
    ):
        raise ValueError(f"Invalid identifier: {value!r}")
    return value


@dataclass(frozen=True)
class ComponentSpec:
    id: str
    factory: str
    params: dict[str, Any] = field(default_factory=dict)
    version: str = "1"
    code_dependencies: tuple[str, ...] = ()
    hydra_config: str | None = None

    def __post_init__(self):
        identifier(self.id)
        if ":" not in self.factory:
            raise ValueError("Component factory must be module:callable")


@dataclass(frozen=True)
class TaskSpec:
    id: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExperimentSpec:
    id: str
    dataset_ids: tuple[str, ...]
    task_id: str
    method_ids: tuple[str, ...]
    flow: str
    params: dict[str, Any] = field(default_factory=dict)
    evaluation: dict[str, Any] = field(default_factory=dict)
    search: dict[str, Any] = field(default_factory=dict)
    repeats: int = 1

    def __post_init__(self):
        identifier(self.id)
        if self.repeats < 1 or not self.dataset_ids or not self.method_ids:
            raise ValueError(
                "Experiments require datasets, methods and positive repeats"
            )


@dataclass(frozen=True)
class RuntimeSpec:
    seed: int = 0
    device: str = "cpu"
    max_workers: int = 1
    backend: str = "local"
    slurm: dict[str, Any] = field(default_factory=dict)
    hooks: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if self.max_workers < 1 or self.backend not in ("local", "slurm"):
            raise ValueError(
                "Runtime requires positive max_workers and local/slurm backend"
            )


@dataclass(frozen=True)
class StudySpec:
    id: str
    profile: str
    datasets: tuple[ComponentSpec, ...]
    tasks: tuple[TaskSpec, ...]
    methods: tuple[ComponentSpec, ...]
    experiments: tuple[ExperimentSpec, ...]
    reports: tuple[dict[str, Any], ...] = ()
    runtime: RuntimeSpec = field(default_factory=RuntimeSpec)
    schema_version: int = 2

    def __post_init__(self):
        identifier(self.id)
        if self.schema_version != 2 or self.profile not in PROFILES:
            raise ValueError("Expected schema_version: 2 and a supported profile")
        for group in (self.datasets, self.tasks, self.methods, self.experiments):
            names = [identifier(item.id) for item in group]
            if len(names) != len(set(names)):
                raise ValueError("Duplicate component or experiment id")
        report_ids = [identifier(item["id"]) for item in self.reports]
        if len(report_ids) != len(set(report_ids)):
            raise ValueError("Duplicate report id")
        datasets, tasks, methods = (
            {item.id for item in group}
            for group in (self.datasets, self.tasks, self.methods)
        )
        if not self.experiments:
            raise ValueError("A Study requires at least one experiment")
        for exp in self.experiments:
            if (
                set(exp.dataset_ids) - datasets
                or exp.task_id not in tasks
                or set(exp.method_ids) - methods
            ):
                raise ValueError(f"Unknown dataset/task/method in {exp.id}")

    def to_dict(self):
        return asdict(self)


def study_spec_from_mapping(raw):
    allowed = {
        "schema_version",
        "id",
        "profile",
        "datasets",
        "tasks",
        "methods",
        "experiments",
        "reports",
        "runtime",
    }
    if set(raw) - allowed:
        raise ValueError(f"Unknown Study fields: {sorted(set(raw) - allowed)}")
    try:
        return StudySpec(
            id=raw["id"],
            profile=raw["profile"],
            schema_version=raw.get("schema_version", 2),
            datasets=tuple(ComponentSpec(**item) for item in raw.get("datasets", [])),
            tasks=tuple(TaskSpec(**item) for item in raw.get("tasks", [])),
            methods=tuple(ComponentSpec(**item) for item in raw.get("methods", [])),
            experiments=tuple(
                ExperimentSpec(
                    **{
                        **item,
                        "dataset_ids": tuple(item["dataset_ids"]),
                        "method_ids": tuple(item["method_ids"]),
                    }
                )
                for item in raw.get("experiments", [])
            ),
            reports=tuple(raw.get("reports", [])),
            runtime=RuntimeSpec(**raw.get("runtime", {})),
        )
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Invalid Study configuration: {exc}") from exc


def load_study_spec(path):
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Study YAML must be a mapping")
    return study_spec_from_mapping(raw)
