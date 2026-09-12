from __future__ import annotations

from pathlib import Path


def study_output_dir(study_id: str) -> Path:
    if not study_id or study_id in {".", ".."} or "/" in study_id or "\\" in study_id:
        raise ValueError(f"invalid Study id for output path: {study_id!r}")
    return Path("outputs/studies") / study_id


def study_artifact_root(study_id: str) -> Path:
    return study_output_dir(study_id) / "artifacts"
