from pathlib import Path
import subprocess
import yaml
from framework.config import study_spec_from_mapping
from framework.runtime import slurm


def test_script_generation_and_mock_submission(workspace, monkeypatch):
    raw = {
        "schema_version": 2,
        "id": "scheduled",
        "profile": "agent",
        "datasets": [{"id": "data", "factory": "builtins:list"}],
        "tasks": [{"id": "task"}],
        "methods": [{"id": name, "factory": "builtins:dict"} for name in ("a", "b")],
        "experiments": [
            {
                "id": "e",
                "dataset_ids": ["data"],
                "task_id": "task",
                "method_ids": ["a", "b"],
                "flow": "evaluate",
            }
        ],
        "runtime": {"backend": "slurm", "slurm": {"gres": "gpu:1"}},
    }
    Path("study.yaml").write_text(yaml.safe_dump(raw), encoding="utf-8")
    monkeypatch.setattr("framework.runtime.study.prepare_study", lambda spec: None)
    calls = []

    def submit(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(
            command, 0, stdout=str(100 + len(calls)) + ";cluster\n"
        )

    monkeypatch.setattr(slurm.subprocess, "run", submit)
    dry = slurm.submit_slurm_study("study.yaml", dry_run=True)
    assert not calls
    worker = Path(dry["workers"]["a"]["script"]).read_text(encoding="utf-8")
    assert (
        "--method a" in worker
        and "--gres=gpu:1" in worker
        and "--partition" not in worker
    )
    assert "--gres" not in Path(dry["finalizer"]["script"]).read_text(encoding="utf-8")
    live = slurm.submit_slurm_study("study.yaml")
    assert len(calls) == 3 and "--dependency=afterok:101:102" in calls[-1]
    assert live["finalizer"]["job_id"] == "103"
    one = slurm.select_method(study_spec_from_mapping(raw), "a")
    assert [m.id for m in one.methods] == ["a"] and one.experiments[0].method_ids == (
        "a",
    )


def test_slurm_rejects_resource_newlines(workspace):
    import pytest

    with pytest.raises(ValueError):
        slurm._script(
            ["paper", "run", "study.yaml"], {"partition": "cpu\ncommand"}, Path("out")
        )
