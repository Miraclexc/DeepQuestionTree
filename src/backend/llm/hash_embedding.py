from __future__ import annotations

import hashlib

DEFAULT_EMBEDDING_DIMENSION = 768


def build_hash_embedding(
    text: str,
    *,
    dimension: int = DEFAULT_EMBEDDING_DIMENSION,
) -> list[float]:
    """Generate a deterministic offline embedding for fallback and tests."""
    if dimension <= 0:
        raise ValueError("dimension must be greater than 0")

    digest = hashlib.md5(text.encode("utf-8")).digest()
    vector: list[float] = []
    while len(vector) < dimension:
        for byte in digest:
            vector.append(byte / 255.0 * 2 - 1)
            if len(vector) == dimension:
                break
    return vector
