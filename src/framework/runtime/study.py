"""Direction-neutral execution and immutable per-run provenance."""

from dataclasses import asdict
from datetime import datetime, timezone
from importlib import import_module, metadata
from threading import Lock
import uuid
from framework.config import StudySpec, load_study_spec
from framework.contracts import ResultRecord, read_json, write_json
from framework.runtime.artifacts import ArtifactRef, ArtifactStore, atomic_replace
from framework.runtime.dag import Executor
from framework.runtime.paths import study_output_dir, study_artifact_root
from framework.runtime.reporting import (
    collect_metrics,
    compile_reports,
    validate_reports,
    summarize,
)
from framework.utils.fingerprint import stable_fingerprint


def prepare_study(spec):
    if not isinstance(spec, StudySpec):
        spec = load_study_spec(spec)
    compiled = import_module(f"workflows.{spec.profile}.compiler").compile(spec)
    validate_reports(spec, compiled)
    return compiled


def plan_study(spec):
    if not isinstance(spec, StudySpec):
        spec = load_study_spec(spec)
    compiled = prepare_study(spec)
    store = ArtifactStore(study_artifact_root(spec.id))
    executor = Executor(store)
    stages = executor.plan(compiled.plan)
    refs = {
        node.logical_id: ArtifactRef(
            node.logical_id, node.fingerprint, store.path_for(node.fingerprint)
        )
        for node in stages
    }
    return stages + executor.plan(compile_reports(spec, compiled, refs, ()))


def run_study(spec, *, force=(), progress=None, publish=True, require_cached=False):
    if not isinstance(spec, StudySpec):
        spec = load_study_spec(spec)
    compiled = prepare_study(spec)
    directory = study_output_dir(spec.id)
    store = ArtifactStore(study_artifact_root(spec.id))
    executor = Executor(store)
    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        + "-"
        + uuid.uuid4().hex[:12]
    )
    forced_nodes = [key for key in force if key in compiled.plan.nodes]
    unknown = (
        set(force)
        - set(compiled.plan.nodes)
        - {f"report:{r['id']}" for r in spec.reports}
        - {"report:summary"}
    )
    if unknown:
        raise ValueError(f"Unknown nodes: {sorted(unknown)}")
    planned = executor.plan(compiled.plan, force=forced_nodes, force_token=run_id)
    if require_cached and any(node.status.value != "REUSE" for node in planned):
        raise RuntimeError(
            "Finalization requires complete worker artifacts for the current configuration"
        )
    run_dir = directory / "runs" / run_id
    run_dir.mkdir(parents=True)
    run = {
        "run_id": run_id,
        "study_id": spec.id,
        "profile": spec.profile,
        "status": "running",
        "artifacts": {},
        "config_fingerprint": stable_fingerprint(spec.to_dict()),
        "executed": [],
        "reused": [],
        "methods": [m.id for m in spec.methods],
    }
    write_json(run_dir / "resolved_study.json", spec.to_dict())
    write_json(
        run_dir / "environment.json",
        {
            "python": __import__("sys").version,
            "packages": {
                d.metadata["Name"]: d.version
                for d in metadata.distributions()
                if d.metadata["Name"]
            },
        },
    )
    write_json(run_dir / "manifest.json", run)
    lock = Lock()
    protected_plans = list(planned)

    def event(value):
        with lock:
            with (run_dir / "events.jsonl").open("a", encoding="utf-8") as stream:
                import json

                stream.write(json.dumps(asdict(value), ensure_ascii=False) + "\n")
        if progress:
            progress(value)

    try:
        execution = executor.run(
            compiled.plan,
            force=forced_nodes,
            force_token=run_id,
            max_workers=spec.runtime.max_workers,
            progress=event,
            run_id=run_id,
        )
        refs = dict(execution.refs)
        run["executed"], run["reused"] = (
            list(execution.executed),
            list(execution.reused),
        )
        metrics = collect_metrics(compiled, refs)
        write_json(run_dir / "metrics.json", metrics)
        write_json(run_dir / "summary.json", summarize(metrics))
        write_json(run_dir / "split_index.json", compiled.manifests)
        report_index = {}
        if publish:
            report_plan = compile_reports(spec, compiled, refs, metrics)
            protected_plans.extend(
                executor.plan(
                    report_plan,
                    force=[key for key in force if key in report_plan.nodes],
                    force_token=run_id,
                )
            )
            reports = executor.run(
                report_plan,
                force=[key for key in force if key in report_plan.nodes],
                force_token=run_id,
                max_workers=spec.runtime.max_workers,
                progress=event,
                run_id=run_id,
            )
            refs.update(reports.refs)
            run["executed"].extend(reports.executed)
            run["reused"].extend(reports.reused)
            report_index = {
                key: str(ref.path.relative_to(directory))
                for key, ref in reports.refs.items()
            }
        for key, ref in refs.items():
            meta = read_json(ref.path / "artifact.json")
            status = (
                read_json(ref.path / "result.json").get("status", "completed")
                if (ref.path / "result.json").exists()
                else "completed"
            )
            ident = (
                asdict(compiled.identities[key])
                if key in compiled.identities
                else {"study_id": spec.id, "stage": "report"}
            )
            if key in compiled.selections:
                selection, field = compiled.selections[key]
                ident["trial_id"] = read_json(refs[selection].path / "selection.json")[
                    field
                ]
            run["artifacts"][key] = asdict(
                ResultRecord(
                    ident,
                    status,
                    str(ref.path.relative_to(directory)),
                    meta.get("source_run_id"),
                    ref.fingerprint,
                    key in run["reused"],
                )
            )
        run["status"] = "completed"
        write_json(run_dir / "artifact_index.json", run["artifacts"])
        write_json(run_dir / "report_index.json", report_index)
        write_json(run_dir / "manifest.json", run)
        if publish:
            for name in (
                "resolved_study.json",
                "metrics.json",
                "summary.json",
                "split_index.json",
                "artifact_index.json",
                "report_index.json",
            ):
                _atomic_json(directory / name, read_json(run_dir / name))
            _atomic_json(
                directory / "latest.json", {"run_id": run_id, "path": f"runs/{run_id}"}
            )
        return run
    except BaseException as exc:
        run["status"], run["error"] = "failed", f"{type(exc).__name__}: {exc}"
        for item in protected_plans:
            if store.reusable(item.fingerprint):
                run["artifacts"][item.logical_id] = {
                    "fingerprint": item.fingerprint,
                    "artifact_path": str(
                        store.path_for(item.fingerprint).relative_to(directory)
                    ),
                }
        write_json(run_dir / "manifest.json", run)
        raise


def _atomic_json(path, value):
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    write_json(temporary, value)
    atomic_replace(temporary, path)
