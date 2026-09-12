from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from framework.runtime.artifacts import (
    ArtifactAlreadyExists,
    ArtifactRef,
    ArtifactStore,
)
from framework.utils.fingerprint import stable_fingerprint
from framework.version import FRAMEWORK_SCHEMA_VERSION


NodeAction = Callable[[Path, Mapping[str, ArtifactRef]], None]


@dataclass(frozen=True, slots=True)
class ResourceRequest:
    cpus: int = 1
    gpus: int = 0
    memory_gb: float | None = None

    def __post_init__(self) -> None:
        if self.cpus < 1 or self.gpus < 0:
            raise ValueError("resource cpu/gpu counts are invalid")
        if self.memory_gb is not None and self.memory_gb <= 0:
            raise ValueError("memory_gb must be positive when set")


class NodeStatus(StrEnum):
    REUSE = "REUSE"
    RUN = "RUN"
    STALE = "STALE"


class ProgressEventType(StrEnum):
    START = "START"
    REUSE = "REUSE"
    DONE = "DONE"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class ExecutionProgress:
    event: ProgressEventType
    logical_id: str
    kind: str
    completed: int
    total: int
    running: int
    elapsed_seconds: float | None = None
    error: str | None = None


ProgressCallback = Callable[[ExecutionProgress], None]


@dataclass(frozen=True, slots=True)
class ArtifactNode:
    logical_id: str
    kind: str
    config: Mapping[str, Any]
    component_fingerprint: str
    action: NodeAction
    dependencies: tuple[str, ...] = ()
    seed: int | None = None
    runtime_schema: str = "1"
    resources: ResourceRequest = field(default_factory=ResourceRequest)


@dataclass(frozen=True, slots=True)
class PlannedNode:
    logical_id: str
    kind: str
    config: Mapping[str, Any]
    fingerprint: str
    status: NodeStatus
    dependencies: tuple[str, ...]
    resources: ResourceRequest


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    refs: Mapping[str, ArtifactRef]
    executed: tuple[str, ...]
    reused: tuple[str, ...]


class ExecutionPlan:
    def __init__(self, nodes: Iterable[ArtifactNode]) -> None:
        resolved = tuple(nodes)
        self.nodes = {node.logical_id: node for node in resolved}
        if len(self.nodes) != len(resolved):
            raise ValueError("ArtifactNode logical_id values must be unique")
        for node in resolved:
            missing = set(node.dependencies) - set(self.nodes)
            if missing:
                raise ValueError(
                    f"node {node.logical_id!r} has unknown dependencies {sorted(missing)}"
                )
        self._ordered_ids = self._topological_order()

    @property
    def ordered_ids(self) -> tuple[str, ...]:
        return self._ordered_ids

    def _topological_order(self) -> tuple[str, ...]:
        visiting: set[str] = set()
        visited: set[str] = set()
        ordered: list[str] = []

        def visit(logical_id: str) -> None:
            if logical_id in visited:
                return
            if logical_id in visiting:
                raise ValueError(f"execution graph contains a cycle at {logical_id!r}")
            visiting.add(logical_id)
            for dependency in self.nodes[logical_id].dependencies:
                visit(dependency)
            visiting.remove(logical_id)
            visited.add(logical_id)
            ordered.append(logical_id)

        for logical_id in self.nodes:
            visit(logical_id)
        return tuple(ordered)


class Executor:
    def __init__(self, store: ArtifactStore) -> None:
        self.store = store

    def plan(
        self,
        execution_plan: ExecutionPlan,
        *,
        force: Iterable[str] = (),
        force_token: str | None = None,
    ) -> tuple[PlannedNode, ...]:
        fingerprints = self._resolve_fingerprints(
            execution_plan,
            force=set(force),
            force_token=force_token,
        )
        planned: list[PlannedNode] = []
        for logical_id in execution_plan.ordered_ids:
            fingerprint = fingerprints[logical_id]
            if self.store.reusable(fingerprint):
                status = NodeStatus.REUSE
            elif self.store.latest_fingerprint(logical_id) is not None:
                status = NodeStatus.STALE
            else:
                status = NodeStatus.RUN
            planned.append(
                PlannedNode(
                    logical_id=logical_id,
                    kind=execution_plan.nodes[logical_id].kind,
                    config=execution_plan.nodes[logical_id].config,
                    fingerprint=fingerprint,
                    status=status,
                    dependencies=execution_plan.nodes[logical_id].dependencies,
                    resources=execution_plan.nodes[logical_id].resources,
                )
            )
        return tuple(planned)

    def run(
        self,
        execution_plan: ExecutionPlan,
        *,
        force: Iterable[str] = (),
        force_token: str | None = None,
        max_workers: int = 1,
        progress: ProgressCallback | None = None,
        run_id: str | None = None,
    ) -> ExecutionResult:
        if max_workers < 1:
            raise ValueError("max_workers must be positive")
        forced = set(force)
        unknown_forced = forced - set(execution_plan.nodes)
        if unknown_forced:
            raise ValueError(f"unknown forced nodes: {sorted(unknown_forced)}")
        if forced and force_token is None:
            force_token = f"force-{time.time_ns()}"
        planned = self.plan(
            execution_plan,
            force=forced,
            force_token=force_token,
        )
        planned_by_id = {item.logical_id: item for item in planned}
        refs: dict[str, ArtifactRef] = {}
        outcomes: dict[str, bool] = {}
        pending = list(execution_plan.ordered_ids)
        running: dict[Future[tuple[ArtifactRef, bool]], str] = {}
        started_at: dict[str, float] = {}
        completed_count = 0

        def emit(
            event: ProgressEventType,
            logical_id: str,
            *,
            elapsed_seconds: float | None = None,
            error: str | None = None,
        ) -> None:
            if progress is None:
                return
            progress(
                ExecutionProgress(
                    event=event,
                    logical_id=logical_id,
                    kind=execution_plan.nodes[logical_id].kind,
                    completed=completed_count,
                    total=len(execution_plan.nodes),
                    running=len(running),
                    elapsed_seconds=elapsed_seconds,
                    error=error,
                )
            )

        def execute_node(logical_id: str) -> tuple[ArtifactRef, bool]:
            node = execution_plan.nodes[logical_id]
            item = planned_by_id[logical_id]
            dependency_refs = {
                dependency: refs[dependency] for dependency in node.dependencies
            }
            directory = self.store.build_directory(
                logical_id=logical_id,
                fingerprint=item.fingerprint,
                metadata={
                    "kind": node.kind,
                    "source_run_id": run_id,
                    "dependencies": {
                        name: ref.fingerprint for name, ref in dependency_refs.items()
                    },
                    "config": dict(node.config),
                    "component_fingerprint": node.component_fingerprint,
                    "seed": node.seed,
                    "runtime_schema": node.runtime_schema,
                    "framework_schema_version": FRAMEWORK_SCHEMA_VERSION,
                    "resources": asdict(node.resources),
                },
            )
            entered = False
            try:
                with directory as output_dir:
                    entered = True
                    node.action(output_dir, dependency_refs)
            except ArtifactAlreadyExists:
                if entered:
                    raise
                self.store.commit_index(logical_id, item.fingerprint)
                return self.store.ref(logical_id, item.fingerprint), False
            return self.store.ref(logical_id, item.fingerprint), True

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            while pending or running:
                made_progress = True
                while made_progress and len(running) < max_workers:
                    made_progress = False
                    for logical_id in tuple(pending):
                        node = execution_plan.nodes[logical_id]
                        if not all(
                            dependency in refs for dependency in node.dependencies
                        ):
                            continue
                        pending.remove(logical_id)
                        item = planned_by_id[logical_id]
                        if item.status == NodeStatus.REUSE:
                            refs[logical_id] = self.store.ref(
                                logical_id,
                                item.fingerprint,
                            )
                            outcomes[logical_id] = False
                            completed_count += 1
                            emit(ProgressEventType.REUSE, logical_id)
                        else:
                            started_at[logical_id] = time.monotonic()
                            future = pool.submit(execute_node, logical_id)
                            running[future] = logical_id
                            emit(ProgressEventType.START, logical_id)
                        made_progress = True
                        if len(running) >= max_workers:
                            break
                if running:
                    completed, _ = wait(running, return_when=FIRST_COMPLETED)
                    for future in completed:
                        logical_id = running.pop(future)
                        elapsed = time.monotonic() - started_at.pop(logical_id)
                        try:
                            refs[logical_id], outcomes[logical_id] = future.result()
                        except BaseException as exc:
                            emit(
                                ProgressEventType.FAILED,
                                logical_id,
                                elapsed_seconds=elapsed,
                                error=f"{type(exc).__name__}: {exc}",
                            )
                            raise
                        completed_count += 1
                        emit(
                            ProgressEventType.DONE
                            if outcomes[logical_id]
                            else ProgressEventType.REUSE,
                            logical_id,
                            elapsed_seconds=elapsed,
                        )
                elif pending:
                    raise RuntimeError("execution scheduler made no progress")

        executed = [
            logical_id
            for logical_id in execution_plan.ordered_ids
            if outcomes[logical_id]
        ]
        reused = [
            logical_id
            for logical_id in execution_plan.ordered_ids
            if not outcomes[logical_id]
        ]

        return ExecutionResult(
            refs=refs,
            executed=tuple(executed),
            reused=tuple(reused),
        )

    def _resolve_fingerprints(
        self,
        execution_plan: ExecutionPlan,
        *,
        force: set[str],
        force_token: str | None,
    ) -> dict[str, str]:
        unknown_forced = force - set(execution_plan.nodes)
        if unknown_forced:
            raise ValueError(f"unknown forced nodes: {sorted(unknown_forced)}")
        fingerprints: dict[str, str] = {}
        for logical_id in execution_plan.ordered_ids:
            node = execution_plan.nodes[logical_id]
            payload: dict[str, Any] = {
                "kind": node.kind,
                "config": dict(node.config),
                "component_fingerprint": node.component_fingerprint,
                "dependencies": {
                    dependency: fingerprints[dependency]
                    for dependency in node.dependencies
                },
                "seed": node.seed,
                "runtime_schema": node.runtime_schema,
                "framework_schema_version": FRAMEWORK_SCHEMA_VERSION,
                "resources": asdict(node.resources),
            }
            if logical_id in force:
                payload["force_token"] = force_token
            fingerprints[logical_id] = stable_fingerprint(payload)
        return fingerprints
