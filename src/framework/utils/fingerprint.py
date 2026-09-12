from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import numpy as np


def canonical_value(value: Any, *, array_content: bool = True) -> Any:
    """Convert supported scientific values to a deterministic JSON value."""
    if is_dataclass(value) and not isinstance(value, type):
        return canonical_value(asdict(value), array_content=array_content)
    if isinstance(value, np.ndarray):
        array = np.ascontiguousarray(value) if array_content else value
        result = {
            "__ndarray__": True,
            "dtype": str(array.dtype),
            "shape": list(array.shape),
        }
        if array_content:
            result["content_sha256"] = hashlib.sha256(array.tobytes()).hexdigest()
        return result
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {
            str(key): canonical_value(item, array_content=array_content)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [canonical_value(item, array_content=array_content) for item in value]
    if isinstance(value, (set, frozenset)):
        normalized = [
            canonical_value(item, array_content=array_content) for item in value
        ]
        return sorted(
            normalized,
            key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True),
        )
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"cannot fingerprint value of type {type(value).__name__}")


def stable_fingerprint(value: Any) -> str:
    payload = json.dumps(
        canonical_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def component_fingerprint(component: Any) -> str:
    """Fingerprint a registered component's implementation source."""
    try:
        source = inspect.getsource(component)
    except (OSError, TypeError):
        source = repr(component)
    module = getattr(component, "__module__", None)
    qualname = getattr(component, "__qualname__", getattr(component, "__name__", None))
    return stable_fingerprint(
        {
            "module": module,
            "qualname": qualname,
            "source": source,
            "declared_dependencies": [
                component_fingerprint(dependency)
                for dependency in getattr(component, "__paper_dependencies__", ())
            ],
        }
    )


def path_content_fingerprint(path: str | Path) -> str:
    resolved = Path(path)
    files = (
        (resolved,)
        if resolved.is_file()
        else tuple(item for item in sorted(resolved.rglob("*")) if item.is_file())
    )
    if not files:
        raise FileNotFoundError(f"checkpoint path has no files: {resolved}")
    digest = hashlib.sha256()
    for file_path in files:
        relative = (
            file_path.name
            if resolved.is_file()
            else str(file_path.relative_to(resolved))
        )
        digest.update(relative.encode("utf-8"))
        with file_path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()


def file_sha256(path: str | Path) -> str:
    """Return the raw SHA-256 checksum of one file."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
