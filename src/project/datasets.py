"""Versioned local question sets; references remain in evaluation nodes."""

import json
from pathlib import Path

from framework.contracts import validate_cases


def load_cases(path):
    rows = []
    for number, line in enumerate(
        Path(path).read_text(encoding="utf-8-sig").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError("expected an object")
            if not isinstance(row.get("input"), str) or not row["input"].strip():
                raise ValueError("input must be a nonempty question string")
            if not isinstance(row.get("metadata", {}), dict):
                raise ValueError("metadata must be an object")
            if not isinstance(row.get("unit_id", row.get("id")), str):
                raise ValueError("unit_id must be a string")
            rows.append({"split": "test", "metadata": {}, **row})
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{path}:{number}: {exc}") from exc
    if not rows:
        raise ValueError("Dataset must contain at least one case")
    try:
        validate_cases(rows)
    except (KeyError, TypeError) as exc:
        raise ValueError("Every case requires a unique string id") from exc
    return rows


load_cases.__paper_dependencies__ = (validate_cases,)
