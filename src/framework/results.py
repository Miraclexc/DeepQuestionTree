"""Structured, portable access to one completed run; no symlink discovery."""

from pathlib import Path
from framework.contracts import MetricRecord, ResultRecord, read_json


class ResultStore:
    def __init__(self, study_dir, run_id=None):
        self.root = Path(study_dir)
        if run_id is None:
            self.run_dir = self.root / read_json(self.root / "latest.json")["path"]
        else:
            from framework.config import identifier

            self.run_dir = self.root / "runs" / identifier(run_id)
        self.manifest = read_json(self.run_dir / "manifest.json")
        if self.manifest["status"] != "completed":
            raise ValueError("ResultStore requires a completed run")

    def metrics(self, **filters):
        return tuple(
            MetricRecord(**row)
            for row in read_json(self.run_dir / "metrics.json")
            if all(row.get(key) == value for key, value in filters.items())
        )

    def artifacts(self):
        return {
            key: ResultRecord(**value)
            for key, value in read_json(self.run_dir / "artifact_index.json").items()
        }

    def artifact_path(self, logical_id):
        return self.root / self.artifacts()[logical_id].artifact_path

    def reports(self):
        return {
            key: self.root / value
            for key, value in read_json(self.run_dir / "report_index.json").items()
        }
