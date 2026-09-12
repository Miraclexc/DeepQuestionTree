from pathlib import Path
import shutil
import uuid
from framework.contracts import read_json, write_json
from framework.runtime.paths import study_output_dir
from framework.runtime.artifacts import atomic_replace


def _native(path):
    import os

    resolved = str(path.resolve())
    if os.name == "nt" and not resolved.startswith("\\\\?\\"):
        return Path(
            "\\\\?\\UNC\\" + resolved[2:]
            if resolved.startswith("\\\\")
            else "\\\\?\\" + resolved
        )
    return Path(resolved)


def archive_study(study_id):
    source = study_output_dir(study_id)
    latest = read_json(source / "latest.json")

    def active():
        return list((source / "artifacts/locks").glob("*.lock")) or any(
            read_json(path).get("status") == "running"
            for path in (source / "runs").glob("*/manifest.json")
        )

    if active():
        raise RuntimeError("Cannot archive active artifact writers")
    target = Path("outputs/archives") / f"{study_id}-{latest['run_id']}"
    if target.exists():
        raise FileExistsError(target)
    temporary = target.with_name(".archive-" + uuid.uuid4().hex[:12])
    temporary.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(_native(source), _native(temporary))
    if read_json(source / "latest.json") != latest or active():
        raise RuntimeError(
            f"Study changed during archive; incomplete snapshot retained at {temporary}"
        )
    write_json(
        temporary / "archive.json",
        {"study_id": study_id, "run_id": latest["run_id"], "schema_version": 2},
    )
    atomic_replace(_native(temporary), _native(target))
    return target
