from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from framework.runtime.artifacts import ArtifactStore


@dataclass(frozen=True, slots=True)
class CacheStatus:
    artifact_root: Path
    object_count: int
    object_bytes: int
    study_referenced_count: int
    latest_indexed_count: int
    reclaimable_count: int
    reclaimable_bytes: int
    failure_count: int
    failure_bytes: int
    unindexed_study_count: int


@dataclass(frozen=True, slots=True)
class CacheCleanupResult:
    applied: bool
    object_count: int
    failure_count: int
    reclaimed_bytes: int
    unindexed_study_count: int = 0
    pruned_index_entries: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _CacheEntry:
    fingerprint: str
    path: Path
    size_bytes: int


def inspect_cache(
    artifact_root: str | Path,
    *,
    drop_latest: bool = False,
) -> CacheStatus:
    store = ArtifactStore(artifact_root)
    objects = _object_entries(store)
    failures = _failure_entries(store)
    study_references, unindexed_studies = _study_references(store)
    latest_references = store.indexed_fingerprints()
    protected = set(study_references)
    if not drop_latest:
        protected.update(latest_references)
    reclaimable = tuple(
        entry for entry in objects if entry.fingerprint not in protected
    )
    return CacheStatus(
        artifact_root=store.root,
        object_count=len(objects),
        object_bytes=sum(entry.size_bytes for entry in objects),
        study_referenced_count=len(
            set(entry.fingerprint for entry in objects) & set(study_references)
        ),
        latest_indexed_count=len(
            set(entry.fingerprint for entry in objects) & set(latest_references)
        ),
        reclaimable_count=len(reclaimable),
        reclaimable_bytes=sum(entry.size_bytes for entry in reclaimable),
        failure_count=len(failures),
        failure_bytes=sum(entry.size_bytes for entry in failures),
        unindexed_study_count=len(unindexed_studies),
    )


def clean_cache(
    artifact_root: str | Path,
    *,
    apply: bool = False,
    drop_latest: bool = False,
    include_failures: bool = False,
    ignore_unindexed_studies: bool = False,
    force: bool = False,
) -> CacheCleanupResult:
    store = ArtifactStore(artifact_root)
    objects = _object_entries(store)
    study_references, unindexed_studies = _study_references(store)
    protected = set(study_references)
    if not drop_latest:
        protected.update(store.indexed_fingerprints())
    reclaimable = tuple(
        entry for entry in objects if entry.fingerprint not in protected
    )
    failures = _failure_entries(store) if include_failures else ()
    reclaimed_bytes = sum(entry.size_bytes for entry in (*reclaimable, *failures))
    if not apply:
        return CacheCleanupResult(
            applied=False,
            object_count=len(reclaimable),
            failure_count=len(failures),
            reclaimed_bytes=reclaimed_bytes,
            unindexed_study_count=len(unindexed_studies),
        )

    if unindexed_studies and not (ignore_unindexed_studies or force):
        raise RuntimeError(
            "cache cleanup cannot prove references for the Study without "
            "artifact_index.json: "
            f"{list(unindexed_studies)}; rerun it or explicitly ignore "
            "the unindexed Study"
        )
    if not force:
        _ensure_cache_is_idle(store)
    for entry in reclaimable:
        _remove_cache_directory(entry.path, store.artifact_root)
    for entry in failures:
        _remove_cache_directory(entry.path, store.failure_root)
    _remove_empty_prefix_directories(store.artifact_root)
    pruned = store.prune_missing_index_entries(use_lock=not force)
    return CacheCleanupResult(
        applied=True,
        object_count=len(reclaimable),
        failure_count=len(failures),
        reclaimed_bytes=reclaimed_bytes,
        unindexed_study_count=len(unindexed_studies),
        pruned_index_entries=pruned,
    )


def format_bytes(value: int) -> str:
    amount = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if amount < 1024.0 or unit == "TiB":
            return f"{amount:.1f} {unit}"
        amount /= 1024.0
    raise AssertionError("unreachable byte unit")


def _object_entries(store: ArtifactStore) -> tuple[_CacheEntry, ...]:
    if not store.artifact_root.exists():
        return ()
    return tuple(
        _CacheEntry(
            fingerprint=path.name,
            path=path,
            size_bytes=_directory_size(path),
        )
        for prefix in sorted(store.artifact_root.iterdir())
        if prefix.is_dir()
        for path in sorted(prefix.iterdir())
        if path.is_dir()
    )


def _failure_entries(store: ArtifactStore) -> tuple[_CacheEntry, ...]:
    if not store.failure_root.exists():
        return ()
    return tuple(
        _CacheEntry(
            fingerprint=path.name,
            path=path,
            size_bytes=_directory_size(path),
        )
        for path in sorted(store.failure_root.iterdir())
        if path.is_dir()
    )


def _study_references(
    store: ArtifactStore,
) -> tuple[frozenset[str], tuple[str, ...]]:
    study_root = Path("outputs/studies")
    if not study_root.exists():
        return frozenset(), ()
    references: set[str] = set()
    unindexed: list[str] = []
    store_path = store.root.resolve()
    study_root_path = study_root.resolve()
    try:
        relative_store = store_path.relative_to(study_root_path)
    except ValueError:
        study_dirs = sorted(path for path in study_root.iterdir() if path.is_dir())
    else:
        if len(relative_store.parts) != 2 or relative_store.parts[1] != "artifacts":
            study_dirs = sorted(path for path in study_root.iterdir() if path.is_dir())
        else:
            study_dirs = (study_root / relative_store.parts[0],)
    for study_dir in study_dirs:
        run_manifests = tuple((study_dir / "runs").glob("*/manifest.json"))
        if run_manifests:
            for manifest in run_manifests:
                payload = json.loads(manifest.read_text(encoding="utf-8"))
                if payload.get("status") == "running":
                    unindexed.append(str(manifest))
                for record in payload.get("artifacts", {}).values():
                    references.add(record["fingerprint"])
            continue
        index_path = study_dir / "artifact_index.json"
        if not index_path.is_file():
            unindexed.append(study_dir.name)
            continue
        try:
            payload = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot read Study artifact index {index_path}") from exc
        indexed_root = Path(str(payload.get("artifact_root", "")))
        if payload.get("schema_version") == 2 and not indexed_root.is_absolute():
            indexed_root = index_path.parent / indexed_root
        if indexed_root.resolve() != store_path:
            continue
        artifacts = payload.get("artifacts")
        if not isinstance(artifacts, dict):
            raise ValueError(f"invalid Study artifact index {index_path}")
        for record in artifacts.values():
            if not isinstance(record, dict) or not isinstance(
                record.get("fingerprint"), str
            ):
                raise ValueError(f"invalid Study artifact index {index_path}")
            references.add(record["fingerprint"])
    return frozenset(references), tuple(unindexed)


def _directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _ensure_cache_is_idle(store: ArtifactStore) -> None:
    if not store.lock_root.exists():
        return
    locks = tuple(path for path in store.lock_root.glob("*.lock") if path.is_file())
    if locks:
        raise RuntimeError(
            "cache cleanup cannot run while artifact locks are active: "
            f"{[path.name for path in locks]}"
        )


def _remove_cache_directory(path: Path, expected_root: Path) -> None:
    resolved_path = path.resolve()
    resolved_root = expected_root.resolve()
    if resolved_root not in resolved_path.parents or resolved_path == resolved_root:
        raise ValueError(f"refusing to remove path outside cache root: {path}")
    shutil.rmtree(path)


def _remove_empty_prefix_directories(artifact_root: Path) -> None:
    if not artifact_root.exists():
        return
    for path in artifact_root.iterdir():
        if path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass
