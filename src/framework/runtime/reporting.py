"""Artifact reports and scalar result projections."""

from dataclasses import asdict, dataclass
from pathlib import Path
from collections import defaultdict
from statistics import mean
import csv
from framework.components import resolve
from framework.contracts import MetricRecord, read_json
from framework.runtime.dag import ArtifactNode, ExecutionPlan
from framework.utils.fingerprint import (
    component_fingerprint,
    stable_fingerprint,
    path_content_fingerprint,
)


@dataclass(frozen=True)
class ReportArtifact:
    logical_id: str
    kind: str
    identity: dict
    fingerprint: str
    path: Path


@dataclass(frozen=True)
class ReportContext:
    study: object
    report: dict
    output_dir: Path
    inputs: dict
    metrics: tuple


def collect_metrics(compiled, refs):
    result = []
    for key in compiled.metric_nodes:
        ident = compiled.identities[key]
        trial_id = ident.trial_id
        if key in compiled.selections:
            selection, field = compiled.selections[key]
            trial_id = read_json(refs[selection].path / "selection.json")[field]
        for row in read_json(refs[key].path / "metrics.json"):
            dimensions = {**ident.dimensions, **row.get("dimensions", {})}
            for name in ("fold", "level", "n_samples"):
                if name in row:
                    dimensions[name] = row[name]
            case = str(row.get("case_id", ident.case_id))
            local_repeat = int(row.get("repeat", 0))
            repeat = (
                ident.repeat * ident.dimensions.get("cv_repeat_count", 1) + local_repeat
            )
            if "repeat" in row:
                dimensions["cv_repeat"] = local_repeat
            result.append(
                asdict(
                    MetricRecord(
                        ident.study_id,
                        ident.experiment_id,
                        ident.method_id,
                        trial_id,
                        case,
                        repeat,
                        row["metric"],
                        row["value"],
                        str(row.get("unit_id") or case),
                        row.get("split", "test"),
                        dimensions,
                    )
                )
            )
    return result


def summarize(rows):
    grouped = defaultdict(list)
    for row in rows:
        key = (
            row["experiment_id"],
            row["method_id"],
            row["trial_id"],
            row["metric"],
            row.get("split", "test"),
            row.get("dimensions", {}).get("level", "sample"),
        )
        grouped[key].append(row)
    result = []
    for key, values in sorted(grouped.items()):
        units = defaultdict(list)
        for row in values:
            if row["value"] is not None:
                units[row["unit_id"]].append(row["value"])
        result.append(
            dict(
                zip(
                    (
                        "experiment_id",
                        "method_id",
                        "trial_id",
                        "metric",
                        "split",
                        "level",
                    ),
                    key,
                ),
                mean=mean(mean(v) for v in units.values()) if units else None,
                n_units=len(units),
                n_records=len(values),
                n_repeats=len({v["repeat"] for v in values}),
            )
        )
    return result


def comparison_table(context):
    rows = summarize(context.metrics)
    fields = (
        list(rows[0])
        if rows
        else ["experiment_id", "method_id", "trial_id", "metric", "mean", "n_units"]
    )
    with (context.output_dir / "comparison.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    def cell(value):
        return (
            ("" if value is None else str(value)).replace("|", "\\|").replace("\n", " ")
        )

    lines = [
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join(["---"] * len(fields)) + " |",
    ]
    lines += [
        "| " + " | ".join(cell(row.get(f)) for f in fields) + " |" for row in rows
    ]
    (context.output_dir / "comparison.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def _reports(study):
    result = list(study.reports)
    if not any(r["id"] == "summary" for r in result):
        result.insert(
            0,
            {
                "id": "summary",
                "callable": "framework.runtime.reporting:comparison_table",
            },
        )
    return result


comparison_table.__paper_dependencies__ = (summarize,)


def _matches(ident, selector):
    return all(
        not selector.get(plural) or getattr(ident, singular) in selector[plural]
        for plural, singular in [
            ("experiments", "experiment_id"),
            ("methods", "method_id"),
            ("stages", "stage"),
            ("trials", "trial_id"),
        ]
    )


def validate_reports(study, compiled):
    from inspect import signature

    for report in _reports(study):
        function = resolve(report["callable"])
        signature(function).bind(object(), **report.get("params", {}))
        for name, selector in report.get("inputs", {}).items():
            if not any(
                _matches(ident, selector) for ident in compiled.identities.values()
            ):
                raise ValueError(f"Report {report['id']} input {name} matched no nodes")


def compile_reports(study, compiled, refs, metrics):
    nodes = []
    for report in _reports(study):
        selectors = report.get("inputs", {"artifacts": {}})
        inputs = {
            name: tuple(
                ReportArtifact(
                    key,
                    ident.stage,
                    asdict(ident),
                    refs[key].fingerprint,
                    refs[key].path,
                )
                for key, ident in sorted(compiled.identities.items())
                if _matches(ident, selector)
            )
            for name, selector in selectors.items()
        }
        function = resolve(report["callable"])
        selected_ids = {
            (
                a.identity["experiment_id"],
                a.identity["method_id"],
                a.identity["trial_id"],
            )
            for group in inputs.values()
            for a in group
        }
        selected_metrics = tuple(
            row
            for row in metrics
            if any(
                (row["experiment_id"], row["method_id"], trial) in selected_ids
                for trial in (
                    row["trial_id"],
                    row.get("dimensions", {}).get("selection_id"),
                )
            )
        )

        def action(
            output,
            dependencies,
            report=report,
            inputs=inputs,
            function=function,
            selected_metrics=selected_metrics,
        ):
            function(
                ReportContext(study, report, output, inputs, selected_metrics),
                **report.get("params", {}),
            )

        nodes.append(
            ArtifactNode(
                f"report:{report['id']}",
                "report",
                {
                    "report": report,
                    "inputs": {
                        name: [
                            {"id": a.logical_id, "fingerprint": a.fingerprint}
                            for a in group
                        ]
                        for name, group in inputs.items()
                    },
                },
                stable_fingerprint(
                    [
                        component_fingerprint(function),
                        {
                            p: path_content_fingerprint(p)
                            for p in report.get("code_dependencies", [])
                        },
                    ]
                ),
                action,
                runtime_schema="report-2",
            )
        )
    return ExecutionPlan(nodes)


def export_metrics(study_dir, output, *, methods=None, metrics=None, split=None):
    directory, output = Path(study_dir), Path(output)
    pointer = read_json(directory / "latest.json")
    rows = read_json(directory / pointer["path"] / "metrics.json")
    rows = [
        r
        for r in rows
        if (not methods or r["method_id"] in methods)
        and (not metrics or r["metric"] in metrics)
        and (not split or r["split"] == split)
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=list(MetricRecord.__dataclass_fields__)
        )
        writer.writeheader()
        writer.writerows(rows)
    return output
