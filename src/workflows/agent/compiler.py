from framework.components import build, configured, identity
from framework.contracts import (
    RunContext,
    WorkIdentity,
    case_inputs,
    validate_cases,
    write_json,
)
from framework.compilation import PlanBuilder, selection_node, selected, add_score
from framework.search import candidates
from framework.utils.fingerprint import stable_fingerprint, component_fingerprint


def compile(study):
    builder = PlanBuilder(study)
    datasets = {spec.id: build(spec) for spec in study.datasets}
    data_identities = {spec.id: identity(spec) for spec in study.datasets}
    methods = {spec.id: spec for spec in study.methods}
    tasks = {spec.id: spec for spec in study.tasks}
    for exp in study.experiments:
        if exp.flow != "evaluate":
            raise ValueError("Agent flow must be evaluate")
        rows = [row for dataset in exp.dataset_ids for row in datasets[dataset]]
        origins = {
            row["id"]: data_identities[key]
            for key in exp.dataset_ids
            for row in datasets[key]
        }
        validate_cases(rows)
        builder.manifests[exp.id] = [
            {"id": r["id"], "split": r.get("split", "test")} for r in rows
        ]
        limits = exp.params.get("limits", {})
        if not isinstance(limits.get("max_steps"), int) or limits["max_steps"] < 1:
            raise ValueError("Agent experiments require params.limits.max_steps")
        for key in ("time_seconds", "tokens"):
            if key in limits and limits[key] <= 0:
                raise ValueError(f"{key} must be positive")
        evaluator = configured(exp.evaluation, default="framework.scoring:exact_match")
        for method_id in exp.method_ids:
            method = methods[method_id]
            trials = candidates(method, exp.search, study.runtime.seed)
            selecting = exp.search.get("mode") == "select"
            dev = [r for r in rows if r.get("split") in ("dev", "validation")]
            test = [r for r in rows if r.get("split", "test") == "test"]
            if selecting and not dev:
                raise ValueError("Selection requires development cases")
            if not test:
                raise ValueError("Agent evaluation requires test cases")
            selection = None
            for phase, phase_rows in (
                ([("dev", dev), ("test", test)]) if selecting else [("test", test)]
            ):
                score_nodes = []
                for trial in trials:
                    for repeat in range(exp.repeats):
                        for row in phase_rows:
                            ident = WorkIdentity(
                                study.id,
                                exp.id,
                                method.id,
                                trial.id,
                                str(row["id"]),
                                repeat,
                                "run",
                            )
                            inputs = case_inputs(row)
                            seed = study.runtime.seed + repeat

                            def run(
                                output,
                                refs,
                                inputs=inputs,
                                trial=trial,
                                selection=selection,
                                seed=seed,
                                limits=limits,
                                task=tasks[exp.task_id].params,
                            ):
                                if not selected(refs, selection, trial.id):
                                    write_json(
                                        output / "result.json",
                                        {"status": "not_selected"},
                                    )
                                    return
                                runner = build(trial.component)
                                result = runner.run(
                                    inputs,
                                    RunContext(
                                        output,
                                        seed,
                                        dict(limits),
                                        task=dict(task),
                                        resources={"device": study.runtime.device},
                                    ),
                                )
                                write_json(output / "result.json", result)
                                write_json(
                                    output / "trace.json", result.get("events", [])
                                )

                            key = builder.add(
                                ident,
                                {
                                    "input": inputs,
                                    "method": identity(trial.component),
                                    "limits": limits,
                                    "task": tasks[exp.task_id].params,
                                    "dataset": origins[row["id"]],
                                    "device": study.runtime.device,
                                    "repeat": repeat,
                                },
                                run,
                                dependencies=(
                                    () if selection is None else (selection,)
                                ),
                                seed=seed,
                                component=stable_fingerprint(
                                    [
                                        component_fingerprint(compile),
                                        identity(trial.component),
                                    ]
                                ),
                            )
                            score_nodes.append(
                                add_score(
                                    builder,
                                    ident,
                                    key,
                                    row.get("reference"),
                                    evaluator,
                                    phase,
                                    row.get("unit_id", row["id"]),
                                    row.get("metadata", {}),
                                )
                            )
                if phase == "dev":
                    selection = selection_node(builder, exp, method, score_nodes)
    return builder.finish()
