"""Deterministic candidate search independent of workflow semantics."""

from dataclasses import dataclass, replace
from itertools import product
import copy
import random
from framework.components import parameters
from framework.config import ComponentSpec
from framework.utils.fingerprint import stable_fingerprint


@dataclass(frozen=True)
class Trial:
    id: str
    component: ComponentSpec


def candidates(method, search, seed=0):
    strategy, mode = search.get("strategy", "none"), search.get("mode", "compare")
    if strategy not in ("none", "grid", "random") or mode not in ("compare", "select"):
        raise ValueError("Search strategy: none/grid/random; mode: compare/select")
    if search.get("direction", "maximize") not in ("maximize", "minimize"):
        raise ValueError("Search direction must be maximize/minimize")
    space = search.get("parameters", {})
    if strategy == "none" and space:
        raise ValueError("Search parameters require grid or random")
    if any(not isinstance(v, list) or not v for v in space.values()):
        raise ValueError("Search parameters must be nonempty explicit lists")
    names, base, trials = sorted(space), parameters(method), {}
    for values in product(*(space[name] for name in names)):
        params = copy.deepcopy(base)
        for name, value in zip(names, values):
            target, parts = params, name.split(".")
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = value
        trial_id = "t-" + stable_fingerprint(params)[:16]
        trials[trial_id] = Trial(
            trial_id, replace(method, params=params, hydra_config=None)
        )
    result = list(trials.values())
    if strategy == "random":
        count = search.get("n_trials", 1)
        if not isinstance(count, int) or not 1 <= count <= len(result):
            raise ValueError("n_trials must fit the unique candidate space")
        result = random.Random(search.get("seed", seed)).sample(result, count)
    return tuple(result)
