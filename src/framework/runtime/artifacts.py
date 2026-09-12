from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    logical_id: str
    fingerprint: str
    path: Path


class ArtifactAlreadyExists(FileExistsError):
    """Another node or worker has already committed this content identity."""


def atomic_replace(source, destination):
    """Retry only Windows sharing/access conflicts, without replaying an action."""
    for attempt in range(6):
        try:
            os.replace(source, destination)
            return
        except PermissionError as exc:
            if getattr(exc, "winerror", None) not in (5, 32, 33) or attempt == 5:
                raise
            time.sleep(0.05 * 2**attempt)


class ArtifactStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        if (
            self.root.is_absolute()
            or not self.root.parts
            or self.root.parts[0] != "outputs"
            or ".." in self.root.parts
        ):
            raise ValueError("artifact storage must be a relative path under outputs/")
        self.artifact_root = self.root / "objects"
        self.failure_root = self.root / "failures"
        self.lock_root = self.root / "locks"
        self.index_path = self.root / "index.json"

    def prepare(self) -> None:
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        self.failure_root.mkdir(parents=True, exist_ok=True)
        self.lock_root.mkdir(parents=True, exist_ok=True)

    def path_for(self, fingerprint: str) -> Path:
        return self.artifact_root / fingerprint[:2] / fingerprint

    def reusable(self, fingerprint: str) -> bool:
        path = self.path_for(fingerprint)
        return path.is_dir() and (path / "SUCCESS").is_file()

    def ref(self, logical_id: str, fingerprint: str) -> ArtifactRef:
        if not self.reusable(fingerprint):
            raise FileNotFoundError(f"artifact {fingerprint} is not reusable")
        return ArtifactRef(
            logical_id=logical_id,
            fingerprint=fingerprint,
            path=self.path_for(fingerprint),
        )

    def latest_fingerprint(self, logical_id: str) -> str | None:
        return self._read_index().get(logical_id)

    def commit_index(self, logical_id: str, fingerprint: str) -> None:
        self.prepare()
        with self._index_lock():
            index = self._read_index()
            index[logical_id] = fingerprint
            self._write_index(index)

    def indexed_fingerprints(self) -> frozenset[str]:
        return frozenset(self._read_index().values())

    def prune_missing_index_entries(
        self,
        *,
        use_lock: bool = True,
    ) -> tuple[str, ...]:
        self.prepare()
        lock = self._index_lock() if use_lock else nullcontext()
        with lock:
            index = self._read_index()
            retained = {
                logical_id: fingerprint
                for logical_id, fingerprint in index.items()
                if self.reusable(fingerprint)
            }
            removed = tuple(sorted(set(index) - set(retained)))
            if removed:
                self._write_index(retained)
            return removed

    @contextmanager
    def build_directory(
        self,
        *,
        logical_id: str,
        fingerprint: str,
        metadata: Mapping[str, Any],
    ) -> Iterator[Path]:
        self.prepare()
        final_path = self.path_for(fingerprint)
        if self.reusable(fingerprint):
            raise ArtifactAlreadyExists(f"artifact {fingerprint} already exists")

        with self._artifact_lock(fingerprint):
            if self.reusable(fingerprint):
                raise ArtifactAlreadyExists(f"artifact {fingerprint} already exists")
            temporary = Path(
                tempfile.mkdtemp(prefix=f"{fingerprint[:12]}-", dir=self.root)
            )
            started_at = time.time()
            try:
                yield temporary
                artifact_metadata = {
                    "logical_id": logical_id,
                    "fingerprint": fingerprint,
                    "created_at_unix": time.time(),
                    "duration_seconds": time.time() - started_at,
                    **dict(metadata),
                }
                (temporary / "artifact.json").write_text(
                    json.dumps(
                        artifact_metadata,
                        ensure_ascii=False,
                        sort_keys=True,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                (temporary / "SUCCESS").write_text("", encoding="utf-8")
                final_path.parent.mkdir(parents=True, exist_ok=True)
                if final_path.exists():
                    if self.reusable(fingerprint):
                        shutil.rmtree(temporary)
                    else:
                        raise FileExistsError(
                            f"non-reusable artifact path already exists: {final_path}"
                        )
                else:
                    atomic_replace(temporary, final_path)
                self.commit_index(logical_id, fingerprint)
            except BaseException as exc:
                if temporary.exists():
                    (temporary / "SUCCESS").unlink(missing_ok=True)
                    (temporary / "FAILED").write_text(
                        f"{type(exc).__name__}: {exc}\n",
                        encoding="utf-8",
                    )
                    failure_path = self.failure_root / (
                        f"{fingerprint}-{time.time_ns()}"
                    )
                    atomic_replace(temporary, failure_path)
                raise

    def _read_index(self) -> dict[str, str]:
        if not self.index_path.exists():
            return {}
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def _write_index(self, index: Mapping[str, str]) -> None:
        temporary = self.root / f".index-{os.getpid()}-{time.time_ns()}.tmp"
        temporary.write_text(
            json.dumps(index, ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        atomic_replace(temporary, self.index_path)

    @contextmanager
    def _artifact_lock(self, fingerprint: str) -> Iterator[None]:
        lock_path = self.lock_root / f"{fingerprint}.lock"
        descriptor = _acquire_lock(lock_path)
        try:
            yield
        finally:
            os.close(descriptor)
            lock_path.unlink(missing_ok=True)

    @contextmanager
    def _index_lock(self) -> Iterator[None]:
        lock_path = self.lock_root / "index.lock"
        descriptor = _acquire_lock(lock_path)
        try:
            yield
        finally:
            os.close(descriptor)
            lock_path.unlink(missing_ok=True)


def _acquire_lock(path: Path, timeout_seconds: float = 30.0) -> int:
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            return os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"timed out waiting for artifact lock: {path}"
                ) from exc
            time.sleep(0.05)
