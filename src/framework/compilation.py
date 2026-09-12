"""Reusable DAG construction and development-set selection helpers."""

from dataclasses import replace
from statistics import mean
from framework.contracts import CompiledWorkflow, WorkIdentity, read_json, write_json
from framework.runtime.dag import ArtifactNode, ExecutionPlan
from framework.utils.fingerprint import component_fingerprint, stable_fingerprint


class PlanBuilder:
    def __init__(self, study):
        self.study = study
        self.nodes, self.identities, self.metric_nodes, self.manifests = {}, {}, [], {}
        self.selections = {}

    def add(self, ident, config, action, *, dependencies=(), component="", seed=None):
        case_key = stable_fingerprint(ident.case_id)[:12]
        key = f"{ident.experiment_id}:{ident.method_id}:{ident.trial_id}:{case_key}:r{ident.repeat}:{ident.stage}"
        node = ArtifactNode(
            key,
            ident.stage,
            config,
            component or component_fingerprint(action),
            action,
            tuple(dependencies),
            seed=seed,
            runtime_schema="paper-stage-2",
        )
        if key in self.nodes:
            if (
                self.nodes[key].config != config
                or self.nodes[key].dependencies != node.dependencies
                or self.nodes[key].component_fingerprint != node.component_fingerprint
                or self.nodes[key].seed != node.seed
            ):
                raise ValueError(f"Conflicting logical node: {key}")
        else:
            self.nodes[key] = node
            self.identities[key] = ident
        return key

    def finish(self):
        return CompiledWorkflow(
            ExecutionPlan(self.nodes.values()),
            self.identities,
            tuple(dict.fromkeys(self.metric_nodes)),
            self.manifests,
            self.selections,
        )


def selection_node(builder, experiment, method, dependencies):
    metric = experiment.search.get("metric")
    if not metric:
        raise ValueError("Selection requires search.metric")
    direction = experiment.search.get("direction", "maximize")
    ident = WorkIdentity(
        builder.study.id, experiment.id, method.id, "selection", stage="select"
    )

    def select(output, refs):
        grouped = {}
        for key in dependencies:
            for row in read_json(refs[key].path / "metrics.json"):
                if row["metric"] == metric and row.get("value") is not None:
                    if row.get("split") not in ("dev", "validation"):
                        raise ValueError("Selection cannot consume test scores")
                    trial = builder.identities[key].trial_id
                    grouped.setdefault(trial, []).append(row["value"])
        if not grouped:
            raise ValueError(f"No development scores for selection metric {metric}")
        means = {trial: mean(values) for trial, values in grouped.items()}
        chosen = sorted(
            means,
            key=lambda t: ((-means[t] if direction == "maximize" else means[t]), t),
        )[0]
        write_json(
            output / "selection.json",
            {"selected_trial_id": chosen, "metric": metric, "scores": means},
        )

    return builder.add(
        ident,
        {"metric": metric, "direction": direction},
        select,
        dependencies=dependencies,
        component=component_fingerprint(selection_node),
    )


def selected(refs, selection, trial):
    return (
        selection is None
        or read_json(refs[selection].path / "selection.json")["selected_trial_id"]
        == trial
    )


def add_score(
    builder, ident, output_node, reference, evaluator, split, unit_id, dimensions=None
):
    from framework.components import build, identity

    def score(output, refs):
        result = read_json(refs[output_node].path / "result.json")
        rows = []
        if result.get("status") != "not_selected":
            values = build(evaluator)(result, reference)
            for metric, value in values.items():
                rows.append(
                    {
                        "metric": metric,
                        "value": None if value is None else float(value),
                        "case_id": ident.case_id,
                        "unit_id": str(unit_id),
                        "split": split,
                        "dimensions": dimensions or {},
                    }
                )
        write_json(output / "metrics.json", rows)

    key = builder.add(
        replace(ident, stage="evaluate"),
        {
            "reference": reference,
            "evaluator": identity(evaluator),
            "split": split,
            "unit_id": unit_id,
            "dimensions": dimensions or {},
        },
        score,
        dependencies=(output_node,),
        component=stable_fingerprint(
            [component_fingerprint(add_score), identity(evaluator)]
        ),
    )
    builder.metric_nodes.append(key)
    return key
