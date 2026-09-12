import pytest
from pathlib import Path
from framework.config import study_spec_from_mapping
from framework.runtime.study import run_study, prepare_study
from framework.contracts import read_json, RunContext
from framework.runtime.cache import inspect_cache, clean_cache
from framework.runtime.archive import archive_study
from workflows.agent.runner import SingleAgent
from project.agent import runner, ScriptedModel, EchoTool


def test_agent_run_cache_reports_export_archive(config, workspace):
    from framework.runtime.reporting import export_metrics

    spec = study_spec_from_mapping(config("agent"))
    first = run_study(spec)
    second = run_study(spec)
    assert first["executed"] and not second["executed"]
    assert first["run_id"] != second["run_id"]
    assert all(
        a["source_run_id"] == first["run_id"] for a in second["artifacts"].values()
    )
    root = Path("outputs/studies/agent-demo")
    rows = read_json(root / "metrics.json")
    assert all(r["value"] == 1 for r in rows if r["metric"] == "success")
    assert {r["repeat"] for r in rows} == {0, 1}
    export_metrics(root, Path("outputs/comparison.csv"))
    snapshot = archive_study(spec.id)
    assert (snapshot / "latest.json").is_file()
    assert not any(p.is_symlink() for p in root.rglob("*"))
    assert (
        clean_cache(root / "artifacts", apply=True, drop_latest=True).object_count == 0
    )


def test_agent_selection_only_development(config, workspace):
    raw = config("agent")
    raw["experiments"][0]["search"].update(mode="select", metric="success")
    spec = study_spec_from_mapping(raw)
    compiled = prepare_study(spec)
    selection = next(n for n in compiled.plan.nodes.values() if n.kind == "select")
    assert all(
        compiled.plan.nodes[d].config["split"] == "dev" for d in selection.dependencies
    )
    run_study(spec)
    rows = read_json("outputs/studies/agent-demo/metrics.json")
    assert len({r["trial_id"] for r in rows if r["split"] == "test"}) == 1


def test_agent_limits_and_isolation(tmp_path):
    case = {"id": "a", "input": "alpha"}
    assert (
        runner().run(case, RunContext(tmp_path, limits={"max_steps": 1}))["status"]
        == "step_limit"
    )
    assert (
        runner().run(case, RunContext(tmp_path, limits={"max_steps": 3, "tokens": 1}))[
            "status"
        ]
        == "token_limit"
    )
    a = runner().run(case, RunContext(tmp_path, limits={"max_steps": 3}))
    b = runner().run(
        {"id": "b", "input": "beta"}, RunContext(tmp_path, limits={"max_steps": 3})
    )
    assert a["answer"] == "alpha" and b["answer"] == "beta"
    assert "alpha" not in str(b["messages"])


def test_tool_failure_is_not_retried(tmp_path):
    class Broken(EchoTool):
        calls = 0

        def invoke(self, arguments, *, context):
            self.calls += 1
            raise RuntimeError("tool offline")

    tool = Broken()
    with pytest.raises(RuntimeError):
        SingleAgent(ScriptedModel(), {"echo": tool}).run(
            {"id": "a", "input": "a"}, RunContext(tmp_path, limits={"max_steps": 3})
        )
    assert tool.calls == 1


def test_report_change_does_not_run_agent(config, workspace):
    raw = config("agent")
    run_study(study_spec_from_mapping(raw))
    raw["reports"] = [
        {"id": "new-table", "callable": "framework.runtime.reporting:comparison_table"}
    ]
    again = run_study(study_spec_from_mapping(raw))
    assert again["executed"] == ["report:new-table"]
    assert (
        inspect_cache(
            "outputs/studies/agent-demo/artifacts", drop_latest=True
        ).reclaimable_count
        == 0
    )


def test_scoring_and_model_version_invalidation(config, workspace):
    raw = config("agent")
    run_study(study_spec_from_mapping(raw))
    raw["experiments"][0]["evaluation"] = {
        "factory": "framework.scoring:exact_match",
        "version": "2",
    }
    scored = run_study(study_spec_from_mapping(raw))
    assert {
        a["identity"]["stage"]
        for k, a in scored["artifacts"].items()
        if k in scored["executed"]
    } == {"evaluate", "report"}
    raw["methods"][0]["version"] = "2"
    modeled = run_study(study_spec_from_mapping(raw))
    assert any(
        a["identity"]["stage"] == "run"
        for k, a in modeled["artifacts"].items()
        if k in modeled["executed"]
    )
    assert (
        clean_cache(
            "outputs/studies/agent-demo/artifacts", apply=True, drop_latest=True
        ).object_count
        == 0
    )


def test_plan_has_reports_without_running_models(config, workspace, monkeypatch):
    from framework.runtime.study import plan_study

    def forbidden(*args, **kwargs):
        raise AssertionError("planning executed the model")

    monkeypatch.setattr(ScriptedModel, "generate", forbidden)
    planned = plan_study(study_spec_from_mapping(config("agent")))
    assert planned[-1].kind == "report"
    assert not Path("outputs").exists()


def test_worker_finalize_and_result_store(config, workspace):
    from framework.results import ResultStore
    from framework.runtime.slurm import select_method

    raw = config("agent")
    raw["methods"].append({**raw["methods"][0], "id": "second"})
    raw["experiments"][0]["method_ids"].append("second")
    spec = study_spec_from_mapping(raw)
    with pytest.raises(RuntimeError, match="Finalization"):
        run_study(spec, require_cached=True)
    for method in spec.methods:
        run_study(select_method(spec, method.id), publish=False)
    final = run_study(spec, require_cached=True)
    assert final["executed"] == ["report:summary"]
    saved = ResultStore("outputs/studies/agent-demo")
    assert saved.metrics(method_id="second")
    assert (saved.reports()["report:summary"] / "comparison.csv").exists()


def test_reference_hidden_and_time_budget(tmp_path):
    from framework.contracts import case_inputs

    assert case_inputs(
        {"id": "x", "input": "question", "reference": "secret", "split": "test"}
    ) == {"id": "x", "input": "question", "metadata": {}}

    class Slow(ScriptedModel):
        def generate(self, *args, **kwargs):
            import time

            time.sleep(0.02)
            return {"content": "answer", "tokens": 1}

    result = SingleAgent(Slow()).run(
        {"id": "x", "input": "q"},
        RunContext(tmp_path, limits={"max_steps": 2, "time_seconds": 0.005}),
    )
    assert result["status"] == "time_limit" and result["steps"] == 1
