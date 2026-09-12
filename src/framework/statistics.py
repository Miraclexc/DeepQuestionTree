"""Inference over explicitly selected scientific units, never cached run counts."""

from dataclasses import asdict, is_dataclass
from collections import defaultdict
import numpy as np


def _value(row, key):
    value = row
    for part in key.split("."):
        value = value[part]
    return value


def _units(
    rows, *, experiment_id, method_id, trial_id, metric, unit_keys, split="test"
):
    if not unit_keys:
        raise ValueError("Explicit statistical unit keys are required")
    grouped = defaultdict(dict)
    for original in rows:
        row = asdict(original) if is_dataclass(original) else original
        if (
            row["experiment_id"],
            row["method_id"],
            row["trial_id"],
            row["metric"],
            row["split"],
        ) != (experiment_id, method_id, trial_id, metric, split):
            continue
        if row["value"] is None:
            continue
        key = tuple(_value(row, k) for k in unit_keys)
        if any(v is None for v in key):
            raise ValueError("Statistical units cannot be missing")
        observation = (row["case_id"], row["repeat"], str(row.get("dimensions", {})))
        previous = grouped[key].get(observation)
        if previous is not None and previous != row["value"]:
            raise ValueError("Conflicting duplicate observation")
        grouped[key][observation] = row["value"]
    return {
        key: float(np.mean(list(values.values()))) for key, values in grouped.items()
    }


def bootstrap_mean_confidence_interval(
    rows,
    *,
    experiment_id,
    method_id,
    trial_id,
    metric,
    unit_keys,
    split="test",
    confidence=0.95,
    n_resamples=10000,
    seed=0,
):
    if not 0 < confidence < 1 or n_resamples < 1:
        raise ValueError("Invalid confidence or resample count")
    values = np.array(
        list(
            _units(
                rows,
                experiment_id=experiment_id,
                method_id=method_id,
                trial_id=trial_id,
                metric=metric,
                unit_keys=unit_keys,
                split=split,
            ).values()
        )
    )
    if len(values) < 2:
        raise ValueError("At least two independent units are required")
    sampled = (
        np.random.default_rng(seed)
        .choice(values, size=(n_resamples, len(values)), replace=True)
        .mean(axis=1)
    )
    lower, upper = np.quantile(sampled, [(1 - confidence) / 2, (1 + confidence) / 2])
    return {
        "estimate": float(values.mean()),
        "lower": float(lower),
        "upper": float(upper),
        "confidence": confidence,
        "n_independent_units": len(values),
    }


def paired_comparison(
    rows,
    *,
    experiment_id,
    method_a,
    trial_a,
    method_b,
    trial_b,
    metric,
    pair_keys,
    split="test",
    n_resamples=10000,
    seed=0,
):
    if n_resamples < 1:
        raise ValueError("n_resamples must be positive")
    rows = list(rows)
    a = _units(
        rows,
        experiment_id=experiment_id,
        method_id=method_a,
        trial_id=trial_a,
        metric=metric,
        unit_keys=pair_keys,
        split=split,
    )
    b = _units(
        rows,
        experiment_id=experiment_id,
        method_id=method_b,
        trial_id=trial_b,
        metric=metric,
        unit_keys=pair_keys,
        split=split,
    )
    shared = sorted(a.keys() & b.keys(), key=str)
    if len(shared) < 2:
        raise ValueError("At least two matched independent units are required")
    differences = np.array([a[k] - b[k] for k in shared])
    observed = float(differences.mean())
    signs = np.random.default_rng(seed).choice([-1, 1], size=(n_resamples, len(shared)))
    null = (signs * differences).mean(axis=1)
    return {
        "method_a": method_a,
        "method_b": method_b,
        "trial_a": trial_a,
        "trial_b": trial_b,
        "mean_difference": observed,
        "p_value": float(
            (1 + (np.abs(null) >= abs(observed)).sum()) / (n_resamples + 1)
        ),
        "n_pairs": len(shared),
        "unmatched_a": len(a) - len(shared),
        "unmatched_b": len(b) - len(shared),
    }


def adjust_comparisons(comparisons, method="holm"):
    rows = list(comparisons)
    if not rows:
        return []
    p = np.array([r["p_value"] for r in rows])
    order = np.argsort(p)
    if method == "holm":
        values = np.maximum.accumulate(
            [(len(rows) - rank) * p[i] for rank, i in enumerate(order)]
        )
    elif method == "benjamini-hochberg":
        values = np.minimum.accumulate(
            np.array([p[i] * len(rows) / (rank + 1) for rank, i in enumerate(order)])[
                ::-1
            ]
        )[::-1]
    else:
        raise ValueError("Correction must be holm or benjamini-hochberg")
    adjusted = np.empty_like(values)
    adjusted[order] = np.clip(values, 0, 1)
    return [
        {**row, "adjusted_p_value": float(adjusted[i])} for i, row in enumerate(rows)
    ]
