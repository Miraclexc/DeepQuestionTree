"""Method workers preserve trial identities and share only immutable artifacts."""

from dataclasses import replace
from pathlib import Path
import shlex
import subprocess
import yaml
from framework.config import load_study_spec
from framework.contracts import write_json
from framework.runtime.hooks import run_study_hook
from framework.runtime.paths import study_output_dir
from framework.utils.fingerprint import stable_fingerprint


def select_method(spec, method_id):
    methods = tuple(m for m in spec.methods if m.id == method_id)
    experiments = tuple(
        replace(e, method_ids=(method_id,))
        for e in spec.experiments
        if method_id in e.method_ids
    )
    if not methods or not experiments:
        raise ValueError(f"Unknown or unused method: {method_id}")
    return replace(spec, methods=methods, experiments=experiments, reports=())


def _script(command, resources, log, *, finalize=False):
    values = {
        "cpus-per-task": resources.get("cpus_per_task", 1),
        "mem": f"{resources.get('memory_gb', 4)}G",
        "time": resources.get("time_limit", "01:00:00"),
        "output": str(log.resolve()),
    }
    if resources.get("partition"):
        values["partition"] = resources["partition"]
    if resources.get("gres") and not finalize:
        values["gres"] = resources["gres"]
    if any("\n" in str(value) or "\r" in str(value) for value in values.values()):
        raise ValueError("Slurm resource fields cannot contain newlines")
    return "\n".join(
        [
            "#!/bin/bash",
            *[f"#SBATCH --{key}={value}" for key, value in values.items()],
            "set -euo pipefail",
            f"cd {shlex.quote(str(Path.cwd().resolve()))}",
            shlex.join(command),
            "",
        ]
    )


def _submit(path, dependency=None):
    command = ["sbatch", "--parsable"]
    if dependency:
        command.append("--dependency=" + dependency)
    result = subprocess.run(
        [*command, str(path)], check=True, capture_output=True, text=True
    )
    job_id = result.stdout.strip().split(";")[0]
    if not job_id.isdigit():
        raise RuntimeError(f"Invalid sbatch job id: {job_id!r}")
    return job_id


def submit_slurm_study(path, *, dry_run=False):
    spec = load_study_spec(path)
    if spec.runtime.backend != "slurm":
        raise ValueError("submit requires runtime.backend: slurm")
    from framework.runtime.study import prepare_study

    prepare_study(spec)
    if not dry_run:
        run_study_hook(spec, "validate_submit")
    directory = (
        study_output_dir(spec.id) / "slurm" / stable_fingerprint(spec.to_dict())[:16]
    )
    directory.mkdir(parents=True, exist_ok=True)
    frozen = directory / "study.yaml"
    frozen.write_text(
        yaml.safe_dump(spec.to_dict(), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    result = {"dry_run": dry_run, "workers": {}, "finalizer": {}}
    for method in spec.methods:
        if not any(method.id in e.method_ids for e in spec.experiments):
            continue
        script = directory / f"worker-{method.id}.sbatch"
        command = [
            "uv",
            "run",
            "--no-sync",
            "paper",
            "worker",
            str(frozen.resolve()),
            "--method",
            method.id,
            "--progress",
        ]
        script.write_text(
            _script(command, spec.runtime.slurm, directory / f"{method.id}-%j.log"),
            encoding="utf-8",
        )
        result["workers"][method.id] = {
            "script": str(script),
            "job_id": None if dry_run else _submit(script),
        }
        write_json(directory / "submission.json", result)
    final = directory / "finalize.sbatch"
    final.write_text(
        _script(
            [
                "uv",
                "run",
                "--no-sync",
                "paper",
                "finalize",
                str(frozen.resolve()),
                "--progress",
            ],
            spec.runtime.slurm,
            directory / "finalize-%j.log",
            finalize=True,
        ),
        encoding="utf-8",
    )
    dependency = (
        "afterok:" + ":".join(v["job_id"] for v in result["workers"].values())
        if not dry_run
        else None
    )
    result["finalizer"] = {
        "script": str(final),
        "dependency": dependency,
        "job_id": None if dry_run else _submit(final, dependency),
    }
    write_json(directory / "submission.json", result)
    return result
