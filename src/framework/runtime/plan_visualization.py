from __future__ import annotations

import html
import os
import re
import shutil
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping

from graphviz import Digraph

from framework.runtime.dag import NodeStatus, PlannedNode
from framework.runtime.paths import study_output_dir
from framework.utils.fingerprint import stable_fingerprint


VisualizationMode = Literal["overview", "detail", "full"]


@dataclass(frozen=True, slots=True)
class PlanVisualizationResult:
    directory: Path
    index_path: Path
    files: tuple[Path, ...]


_STATUS_COLORS = {
    NodeStatus.RUN: ("#DBEAFE", "#2563EB"),
    NodeStatus.REUSE: ("#DCFCE7", "#16A34A"),
    NodeStatus.STALE: ("#FFEDD5", "#EA580C"),
}
_MIXED_COLOR = ("#F3E8FF", "#9333EA")
_STAGE_STYLES = {
    "group": ("◎", "#475569", "#F1F5F9"),
    "train": ("⚙", "#059669", "#ECFDF5"),
    "predict": ("↗", "#2563EB", "#EFF6FF"),
    "evaluate": ("✓", "#7C3AED", "#F5F3FF"),
    "select": ("◇", "#D97706", "#FFFBEB"),
    "adapt": ("⇄", "#0891B2", "#ECFEFF"),
    "report": ("▥", "#059669", "#ECFDF5"),
    "other": ("•", "#64748B", "#F8FAFC"),
}
_KIND_TITLES = {
    "source_train": "Source train",
    "train": "Train",
    "inner_train": "Inner train",
    "outer_refit": "Outer refit",
    "adapt": "Adapt",
    "predict": "Predict",
    "inner_predict": "Inner predict",
    "outer_predict": "Outer predict",
    "metrics": "Metrics",
    "selection_metric": "Selection metric",
    "outer_metrics": "Outer metrics",
    "oof_metrics": "OOF metrics",
    "select_candidate": "Select model",
    "report": "Report",
}
_METRIC_ABBREVIATIONS = {
    "accuracy": "Acc",
    "balanced_accuracy": "BalAcc",
    "macro_f1": "Macro F1",
    "circular_mae_deg": "cMAE°",
    "circular_median_ae_deg": "cMedAE°",
    "circular_p90_ae_deg": "cP90AE°",
    "circular_bias_abs_deg": "cBias°",
    "circular_mae_skill_vs_uniform": "cSkill",
    "circular_rmse_deg": "cRMSE°",
    "accuracy_within_22_5_deg": "Acc@22.5°",
    "accuracy_within_45_deg": "Acc@45°",
    "endpoint_error": "EPE",
    "endpoint_angle_mae_deg": "EA-MAE°",
    "brier_score": "Brier",
    "negative_log_likelihood": "NLL",
    "expected_calibration_error": "ECE",
}


def render_plan_visualization(
    *,
    study_id: str,
    groups: Mapping[str, tuple[PlannedNode, ...]],
    mode: VisualizationMode,
) -> PlanVisualizationResult:
    if mode not in {"overview", "detail", "full"}:
        raise ValueError(f"unknown plan visualization mode: {mode!r}")
    if shutil.which("dot") is None:
        raise RuntimeError(
            "Graphviz executable 'dot' is required for DAG visualization"
        )

    study_dir = study_output_dir(study_id)
    study_dir.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".plan-", dir=study_dir))
    generated: list[Path] = []
    try:
        overview = _overview_graph(study_id, groups, link_details=mode != "overview")
        generated.extend(_write_graph(overview, temporary / "overview"))

        detail_links: list[tuple[str, Path]] = []
        if mode in {"detail", "full"}:
            detail_dir = temporary / "details"
            detail_dir.mkdir()
            for group, nodes in groups.items():
                relative = Path("details") / _group_stem(group)
                generated.extend(
                    _write_graph(
                        _detail_graph(group, nodes),
                        temporary / relative,
                    )
                )
                detail_links.append((group, relative.with_suffix(".svg")))

        if mode == "full":
            generated.extend(
                _write_graph(_full_graph(study_id, groups), temporary / "full")
            )

        index_path = temporary / "index.html"
        index_path.write_text(
            _index_html(
                study_id=study_id,
                mode=mode,
                detail_links=detail_links,
            ),
            encoding="utf-8",
        )
        generated.append(index_path)

        destination = study_dir / "plan"
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise

    relative_files = tuple(path.relative_to(temporary) for path in generated)
    return PlanVisualizationResult(
        directory=destination,
        index_path=destination / "index.html",
        files=tuple(destination / path for path in relative_files),
    )


def _overview_graph(
    study_id: str,
    groups: Mapping[str, tuple[PlannedNode, ...]],
    *,
    link_details: bool,
) -> Digraph:
    graph = _new_graph(
        f"Study {_display_name(study_id)} · DAG overview",
        rankdir="TB",
    )
    group_by_logical_id = {
        node.logical_id: group for group, nodes in groups.items() for node in nodes
    }
    group_edges: set[tuple[str, str]] = set()
    for group, nodes in groups.items():
        counts = Counter(node.status for node in nodes)
        _, status_color = _aggregate_color(counts)
        node_id = _graph_id("group", group)
        attributes = {
            "label": _card_label(
                stage="group",
                title=_display_name(group),
                detail=f"{len(nodes)} nodes · {_status_summary(counts)}",
                status_color=status_color,
            ),
            "shape": "box",
            "fillcolor": "#FFFFFF",
            "color": _STAGE_STYLES["group"][1],
            "tooltip": "\n".join(node.logical_id for node in nodes),
        }
        if link_details:
            attributes["URL"] = f"details/{_group_stem(group)}.svg"
            attributes["target"] = "_top"
        graph.node(node_id, **attributes)
        for node in nodes:
            for dependency in (*node.dependencies, *_report_input_ids(node)):
                source_group = group_by_logical_id.get(dependency)
                if source_group is not None and source_group != group:
                    group_edges.add((source_group, group))
    for source, target in sorted(group_edges):
        graph.edge(
            _graph_id("group", source),
            _graph_id("group", target),
            style="dashed",
            tooltip="Report input",
        )
    return graph


def _detail_graph(group: str, nodes: tuple[PlannedNode, ...]) -> Digraph:
    graph = _new_graph(
        f"{_display_name(group)} · collapsed by stage",
        rankdir="LR",
    )
    by_kind: dict[str, list[PlannedNode]] = defaultdict(list)
    by_id = {node.logical_id: node for node in nodes}
    for node in nodes:
        by_kind[node.kind].append(node)

    for kind, kind_nodes in by_kind.items():
        counts = Counter(node.status for node in kind_nodes)
        _, status_color = _aggregate_color(counts)
        stage = _stage_for_kind(kind)
        sample_ids = "\n".join(node.logical_id for node in kind_nodes[:20])
        if len(kind_nodes) > 20:
            sample_ids += f"\n... and {len(kind_nodes) - 20} more"
        detail = _aggregate_node_detail(kind_nodes)
        count_detail = f"× {len(kind_nodes)}"
        if detail:
            count_detail = f"{detail} · {count_detail}"
        graph.node(
            _graph_id("kind", kind),
            label=_card_label(
                stage=stage,
                title=_kind_title(kind),
                detail=count_detail,
                status_color=status_color,
            ),
            shape="box",
            fillcolor="#FFFFFF",
            color=_STAGE_STYLES[stage][1],
            tooltip=sample_ids,
        )

    edges: Counter[tuple[str, str]] = Counter()
    for node in nodes:
        for dependency in node.dependencies:
            dependency_node = by_id.get(dependency)
            if dependency_node is not None:
                edges[(dependency_node.kind, node.kind)] += 1
    for (source, target), count in edges.items():
        graph.edge(
            _graph_id("kind", source),
            _graph_id("kind", target),
            penwidth=str(min(1.0 + count / 4.0, 4.0)),
            tooltip=f"{count} direct dependencies",
        )
    return graph


def _full_graph(
    study_id: str,
    groups: Mapping[str, tuple[PlannedNode, ...]],
) -> Digraph:
    graph = _new_graph(f"Study {_display_name(study_id)} · full DAG", rankdir="LR")
    graph.attr(compound="true", newrank="true")
    node_ids: dict[tuple[str, str], str] = {}
    node_id_by_logical_id: dict[str, str] = {}
    for group, nodes in groups.items():
        with graph.subgraph(name=f"cluster_{_graph_id('cluster', group)}") as cluster:
            cluster.attr(
                label=_display_name(group),
                color="#CBD5E1",
                fontcolor="#334155",
                style="rounded",
            )
            for node in nodes:
                node_id = _graph_id("node", f"{group}\0{node.logical_id}")
                node_ids[(group, node.logical_id)] = node_id
                node_id_by_logical_id[node.logical_id] = node_id
                stage = _stage_for_kind(node.kind)
                _, status_color = _STATUS_COLORS[node.status]
                cluster.node(
                    node_id,
                    label=_card_label(
                        stage=stage,
                        title=_kind_title(node.kind),
                        detail=_node_detail(node),
                        status_color=status_color,
                    ),
                    shape="box",
                    fillcolor="#FFFFFF",
                    color=_STAGE_STYLES[stage][1],
                    tooltip=_node_tooltip(node),
                )

    for group, nodes in groups.items():
        for node in nodes:
            target = node_ids[(group, node.logical_id)]
            for dependency in node.dependencies:
                source = node_id_by_logical_id.get(dependency)
                if source is not None:
                    graph.edge(source, target)
            for dependency in _report_input_ids(node):
                source = node_id_by_logical_id.get(dependency)
                if source is not None:
                    graph.edge(
                        source,
                        target,
                        style="dashed",
                        tooltip="Report input",
                    )
    return graph


def _new_graph(label: str, *, rankdir: str) -> Digraph:
    graph = Digraph(engine="dot")
    graph.attr(
        label=label,
        labelloc="t",
        labeljust="l",
        rankdir=rankdir,
        bgcolor="#FBFCFE",
        pad="0.25",
        nodesep="0.35",
        ranksep="0.65",
        splines="ortho",
        fontname="DejaVu Sans",
        fontsize="18",
    )
    graph.attr(
        "node",
        style="rounded,filled",
        fontname="DejaVu Sans",
        fontsize="10",
        margin="0.08,0.05",
        penwidth="1.25",
    )
    graph.attr(
        "edge",
        color="#94A3B8",
        arrowsize="0.7",
        penwidth="1.1",
    )
    return graph


def _write_graph(graph: Digraph, stem: Path) -> tuple[Path, Path]:
    dot_path = stem.with_suffix(".dot")
    svg_path = stem.with_suffix(".svg")
    dot_path.parent.mkdir(parents=True, exist_ok=True)
    dot_path.write_text(graph.source, encoding="utf-8")
    svg_path.write_bytes(graph.pipe(format="svg"))
    return dot_path, svg_path


def _aggregate_color(
    counts: Mapping[NodeStatus, int],
) -> tuple[str, str]:
    present = [status for status in NodeStatus if counts.get(status, 0)]
    if len(present) == 1:
        return _STATUS_COLORS[present[0]]
    return _MIXED_COLOR


def _status_summary(counts: Mapping[NodeStatus, int]) -> str:
    return (
        " · ".join(
            f"{status.value} {counts.get(status, 0)}"
            for status in NodeStatus
            if counts.get(status, 0)
        )
        or "no nodes"
    )


def _card_label(
    *,
    stage: str,
    title: str,
    detail: str,
    status_color: str,
) -> str:
    icon, stage_color, icon_background = _STAGE_STYLES[stage]
    detail_row = (
        f'<BR/><FONT POINT-SIZE="8" COLOR="#64748B">{html.escape(detail)}</FONT>'
        if detail
        else ""
    )
    return (
        '<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" '
        'CELLPADDING="3"><TR>'
        f'<TD FIXEDSIZE="TRUE" WIDTH="30" HEIGHT="30" '
        f'BGCOLOR="{icon_background}"><FONT FACE="DejaVu Sans" '
        f'POINT-SIZE="16" COLOR="{stage_color}">{html.escape(icon)}</FONT></TD>'
        f'<TD WIDTH="8"></TD><TD ALIGN="LEFT"><FONT FACE="DejaVu Sans" '
        f'POINT-SIZE="10" COLOR="#172033"><B>{html.escape(title)}</B></FONT>'
        f'{detail_row}</TD><TD WIDTH="9"></TD>'
        f'<TD><FONT POINT-SIZE="11" COLOR="{status_color}">●</FONT></TD>'
        "</TR></TABLE>>"
    )


def _stage_for_kind(kind: str) -> str:
    if kind == "report":
        return "report"
    if "select_candidate" in kind:
        return "select"
    if "metric" in kind:
        return "evaluate"
    if "predict" in kind:
        return "predict"
    if "adapt" in kind or "calibrat" in kind:
        return "adapt"
    if "train" in kind or "refit" in kind:
        return "train"
    return "other"


def _kind_title(kind: str) -> str:
    return _KIND_TITLES.get(kind, kind.replace("_", " ").title())


def _node_detail(node: PlannedNode) -> str:
    metrics = _node_metrics(node)
    if metrics:
        return " · ".join(_metric_abbreviation(name) for name in metrics[:3])
    if node.kind == "select_candidate":
        candidates = node.config.get("candidates")
        if isinstance(candidates, Mapping):
            return f"{len(candidates)} candidates"
    if node.kind == "report":
        report = node.config.get("report")
        if isinstance(report, Mapping) and report.get("id"):
            return str(report["id"])
    return {
        "source_train": "source domain",
        "inner_train": "candidate fold",
        "inner_predict": "validation",
        "outer_refit": "selected model",
        "outer_predict": "test set",
        "adapt": "target labels",
        "predict": "test set",
    }.get(node.kind, "")


def _aggregate_node_detail(nodes: list[PlannedNode]) -> str:
    metrics = tuple(
        dict.fromkeys(metric for node in nodes for metric in _node_metrics(node))
    )
    if metrics:
        visible = " · ".join(_metric_abbreviation(name) for name in metrics[:3])
        if len(metrics) > 3:
            visible += f" +{len(metrics) - 3}"
        return visible
    first_detail = _node_detail(nodes[0]) if nodes else ""
    return first_detail


def _node_metrics(node: PlannedNode) -> tuple[str, ...]:
    single = node.config.get("metric") or node.config.get("selection_metric")
    if isinstance(single, str):
        return (single,)
    metrics = node.config.get("metrics")
    if isinstance(metrics, (list, tuple)):
        return tuple(str(metric) for metric in metrics)
    return ()


def _metric_abbreviation(name: str) -> str:
    known = _METRIC_ABBREVIATIONS.get(name)
    if known is not None:
        return known
    readable = name.replace("_", " ")
    if len(readable) <= 16:
        return readable
    return "".join(word[0].upper() for word in readable.split() if word)


def _report_input_ids(node: PlannedNode) -> tuple[str, ...]:
    if node.kind != "report":
        return ()
    configured = node.config.get("inputs")
    if not isinstance(configured, Mapping):
        return ()
    return tuple(
        str(item["logical_id"])
        for values in configured.values()
        if isinstance(values, list)
        for item in values
        if isinstance(item, Mapping) and item.get("logical_id")
    )


def _display_name(value: str) -> str:
    return value.replace("_", " ")


def _node_tooltip(node: PlannedNode) -> str:
    memory = (
        "unspecified"
        if node.resources.memory_gb is None
        else f"{node.resources.memory_gb:g} GB"
    )
    return (
        f"id: {node.logical_id}\n"
        f"kind: {node.kind}\n"
        f"status: {node.status.value}\n"
        f"fingerprint: {node.fingerprint[:12]}\n"
        f"resources: cpu={node.resources.cpus}, gpu={node.resources.gpus}, "
        f"memory={memory}"
    )


def _graph_id(prefix: str, value: str) -> str:
    return f"{prefix}_{stable_fingerprint(value)[:16]}"


def _group_stem(group: str) -> str:
    readable = re.sub(r"[^A-Za-z0-9._-]+", "__", group).strip("._-") or "group"
    return f"{readable}--{stable_fingerprint(group)[:8]}"


def _index_html(
    *,
    study_id: str,
    mode: VisualizationMode,
    detail_links: list[tuple[str, Path]],
) -> str:
    details = "".join(
        f'<li><a href="{html.escape(path.as_posix())}">{html.escape(group)}</a></li>'
        for group, path in detail_links
    )
    full_link = (
        '<a class="button" href="full.svg">Open full DAG</a>' if mode == "full" else ""
    )
    detail_section = (
        f"<h2>Collapsed details</h2><ul>{details}</ul>" if detail_links else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(_display_name(study_id))} DAG plan</title>
  <style>
    body {{ color: #0f172a; font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 1200px; padding: 0 1rem; }}
    object {{ border: 1px solid #e2e8f0; border-radius: 12px; height: 70vh; width: 100%; }}
    .legend span {{ border-radius: 999px; display: inline-block; margin-right: .75rem; padding: .3rem .7rem; }}
    .run {{ background: #dbeafe; }} .reuse {{ background: #dcfce7; }} .stale {{ background: #ffedd5; }}
    .stages {{ color: #475569; display: flex; flex-wrap: wrap; gap: .6rem 1rem; margin: .75rem 0 1rem; }}
    .stages span {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: .35rem .65rem; }}
    .button {{ display: inline-block; margin: .5rem 0; }}
  </style>
</head>
<body>
  <h1>{html.escape(_display_name(study_id))} DAG plan</h1>
  <p class="legend"><span class="run">RUN</span><span class="reuse">REUSE</span><span class="stale">STALE</span></p>
  <div class="stages"><span>⚙ Train</span><span>↗ Predict</span><span>✓ Evaluate</span><span>◇ Select</span><span>⇄ Adapt</span><span>▥ Report</span></div>
  <object data="overview.svg" type="image/svg+xml"></object>
  {full_link}
  {detail_section}
</body>
</html>
"""
