import pytest
from framework.config import ComponentSpec, study_spec_from_mapping
from framework.search import candidates
from framework.runtime.artifacts import ArtifactStore
from framework.runtime.dag import ArtifactNode, ExecutionPlan, Executor
from framework.contracts import write_json, read_json
from framework.statistics import (
    bootstrap_mean_confidence_interval,
    paired_comparison,
    adjust_comparisons,
)


def test_grid_random_identity():
    method = ComponentSpec("method", "builtins:dict", {"size": 4})
    grid = {
        "strategy": "grid",
        "parameters": {"size": [2, 4, 8], "training.lr": [0.1, 0.01]},
    }
    all_trials = candidates(method, grid)
    assert len(all_trials) == 6 and len({t.id for t in all_trials}) == 6
    random = {**grid, "strategy": "random", "n_trials": 3, "seed": 4}
    assert candidates(method, random) == candidates(method, random)
    assert set(t.id for t in candidates(method, random)) <= set(
        t.id for t in all_trials
    )
    assert (
        candidates(method, {"strategy": "grid", "parameters": {"size": [4]}})[0].id
        == candidates(method, {})[0].id
    )


def test_atomic_failure_recovery_and_force(workspace):
    fail = [True]

    def first(out, refs):
        write_json(out / "value.json", 1)

    def second(out, refs):
        if fail[0]:
            raise RuntimeError("failure")
        write_json(out / "value.json", read_json(refs["a"].path / "value.json") + 1)

    plan = ExecutionPlan(
        [
            ArtifactNode("a", "prepare", {}, "a", first),
            ArtifactNode("b", "run", {}, "b", second, ("a",)),
        ]
    )
    store = ArtifactStore("outputs/artifacts")
    executor = Executor(store)
    with pytest.raises(RuntimeError):
        executor.run(plan, run_id="failed-run")
    assert [p.status.value for p in executor.plan(plan)] == ["REUSE", "RUN"]
    assert list(store.failure_root.glob("*/FAILED"))
    assert not list(store.failure_root.glob("*/SUCCESS"))
    fail[0] = False
    recovered = executor.run(plan, run_id="recovered")
    assert recovered.reused == ("a",)
    assert (
        read_json(recovered.refs["a"].path / "artifact.json")["source_run_id"]
        == "failed-run"
    )
    assert not executor.run(plan).executed
    assert executor.run(plan, force=["a"]).executed == ("a", "b")


def test_no_torch_or_sklearn_import_in_core():
    import subprocess, sys, os
    from pathlib import Path
    ROOT = Path(__file__).resolve().parents[3]

    code = 'import framework.runtime.cli, framework.runtime.study; import sys; assert not any(x in sys.modules for x in ("torch","sklearn","workflows.agent","workflows.rag","workflows.deep_learning"))'
    subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
    )


def test_statistical_units_and_cached_duplicates():
    rows = [
        {
            "experiment_id": "e",
            "method_id": method,
            "trial_id": "t",
            "metric": "success",
            "split": "test",
            "case_id": str(i),
            "repeat": repeat,
            "unit_id": str(i),
            "dimensions": {},
            "value": float(i + (method == "b")),
        }
        for method in ("a", "b")
        for i in range(4)
        for repeat in range(3)
    ]
    kwargs = dict(
        experiment_id="e",
        method_id="a",
        trial_id="t",
        metric="success",
        unit_keys=["unit_id"],
        n_resamples=50,
    )
    assert bootstrap_mean_confidence_interval(
        rows, **kwargs
    ) == bootstrap_mean_confidence_interval(rows + rows, **kwargs)
    result = paired_comparison(
        rows,
        experiment_id="e",
        method_a="a",
        method_b="b",
        trial_a="t",
        trial_b="t",
        metric="success",
        pair_keys=["unit_id"],
        n_resamples=50,
    )
    assert result["n_pairs"] == 4 and result["mean_difference"] == -1
    assert adjust_comparisons([result])[0]["adjusted_p_value"] == result["p_value"]


def test_reject_old_or_mixed_config():
    with pytest.raises(ValueError):
        study_spec_from_mapping({"id": "x", "profile": "agent", "algorithms": []})


@pytest.mark.parametrize("workers", [1, 2])
def test_duplicate_content_nodes_reuse_during_same_run(workspace, workers):
    import time

    calls = []

    def build(out, refs):
        calls.append("built")
        time.sleep(0.1)
        write_json(out / "value.json", 1)

    plan = ExecutionPlan(
        [ArtifactNode(name, "shared", {}, "same", build) for name in ("a", "b")]
    )
    store = ArtifactStore("outputs/artifacts")
    result = Executor(store).run(plan, max_workers=workers, run_id="one")
    assert calls == ["built"]
    assert len(result.executed) == 1 and len(result.reused) == 1
    assert result.refs["a"].fingerprint == result.refs["b"].fingerprint
    assert store.latest_fingerprint("a") == store.latest_fingerprint("b")


def test_windows_commit_conflict_does_not_replay_action(workspace, monkeypatch):
    from framework.runtime import artifacts

    original = artifacts.os.replace
    calls = []
    conflicts = []

    def replace(source, target):
        if str(target).endswith("index.json") or conflicts:
            return original(source, target)
        conflicts.append("locked")
        error = PermissionError("transient Windows sharing conflict")
        error.winerror = 32
        raise error

    monkeypatch.setattr(artifacts.os, "replace", replace)

    def action(out, refs):
        calls.append("ran")
        write_json(out / "value.json", 1)

    store = ArtifactStore("outputs/artifacts")
    result = Executor(store).run(
        ExecutionPlan([ArtifactNode("a", "run", {}, "code", action)])
    )
    assert calls == ["ran"] and conflicts == ["locked"]
    assert store.reusable(result.refs["a"].fingerprint)
