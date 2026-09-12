"""Offline integration of the real tree engine with its existing mock provider."""

import json
from pathlib import Path

import pytest
import yaml

from framework.config import study_spec_from_mapping
from framework.contracts import read_json
from framework.runtime.study import plan_study, run_study

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.integration


def smoke_spec():
    raw = yaml.safe_load(
        (ROOT / "configs/studies/smoke.yaml").read_text(encoding="utf-8")
    )
    raw["datasets"][0]["params"]["path"] = str(ROOT / "datasets/smoke.jsonl")
    raw["methods"][0]["code_dependencies"] = [
        str(ROOT / "src/project/dqt"),
        str(ROOT / "config/prompts.yaml"),
        str(ROOT / "config/settings.yaml"),
    ]
    return raw


def test_tree_artifacts_reuse_and_scoring_report_decoupling(tmp_path, monkeypatch):
    raw = smoke_spec()
    monkeypatch.chdir(tmp_path)
    assert all(
        p.status.value == "RUN" for p in plan_study(study_spec_from_mapping(raw))
    )
    assert not (tmp_path / "outputs").exists()
    first = run_study(study_spec_from_mapping(raw))
    root = tmp_path / "outputs/studies" / raw["id"]
    runs = [a for a in first["artifacts"].values() if a["identity"]["stage"] == "run"]
    assert runs
    for artifact in runs:
        output = root / artifact["artifact_path"]
        result = read_json(output / "result.json")
        assert result["answer"] and result["mock"] is True
        assert result["steps"] <= 1
        assert result["tokens"] > 0 and result["llm_calls"] > 0
        assert (
            read_json(output / "answer_report.json")["llm_stats"]["total_tokens"]
            == result["tokens"]
        )
        tree = read_json(output / "tree.json")
        assert tree["status"] == "completed"
        assert len(tree["nodes"]) >= 2
        assert read_json(output / "trace.json")
        assert "reference" not in read_json(output / "request.json")["case"]
    assert not (tmp_path / "data/sessions").exists()
    assert not run_study(study_spec_from_mapping(raw))["executed"]
    raw["experiments"][0]["evaluation"]["version"] = "rescore"
    scored = run_study(study_spec_from_mapping(raw))
    assert all(
        scored["artifacts"][key]["identity"]["stage"] != "run"
        for key in scored["executed"]
    )
    raw["reports"][0]["params"] = {"title": "Updated table"}
    assert run_study(study_spec_from_mapping(raw))["executed"] == ["report:summary"]
    latest = read_json(root / "latest.json")
    assert (root / latest["path"] / "report_index.json").is_file()


def test_budget_stops_tree_without_leaking_reservations(tmp_path):
    from framework.contracts import RunContext
    from project.methods import tree_search

    result = tree_search(mock=True).run(
        {"id": "limited", "input": "如何设计可靠的复杂问题搜索树？"},
        RunContext(tmp_path, limits={"max_steps": 1, "tokens": 1}),
    )
    assert result["status"] == "token_limit"
    assert result["llm_calls"] == 1
    tree = read_json(tmp_path / "tree.json")
    # Runtime locks are intentionally excluded from the persisted schema.
    from project.dqt.core.schema import SessionData

    restored = SessionData.model_validate(tree)
    assert restored.status.value == "paused"
    assert all(
        not n.is_processing and n.processing_token is None
        for n in restored.nodes.values()
    )


def test_failed_worker_does_not_publish_success_and_can_recover(tmp_path, monkeypatch):
    raw = smoke_spec()
    monkeypatch.chdir(tmp_path)
    raw["methods"][0]["params"]["mock"] = False
    raw["methods"][0]["params"]["api_key_env"] = "DQT_TEST_MISSING_CREDENTIAL"
    monkeypatch.delenv("DQT_TEST_MISSING_CREDENTIAL", raising=False)
    with pytest.raises(RuntimeError, match="worker failed"):
        run_study(study_spec_from_mapping(raw))
    root = tmp_path / "outputs/studies" / raw["id"]
    assert not (root / "latest.json").exists()
    assert list((root / "artifacts/failures").rglob("FAILED"))
    assert not list((root / "artifacts/failures").rglob("SUCCESS"))
    raw["methods"][0]["params"]["mock"] = True
    assert run_study(study_spec_from_mapping(raw))["status"] == "completed"


def test_parallel_repeats_have_isolated_trees_and_references_rescore_only(
    tmp_path, monkeypatch
):
    raw = smoke_spec()
    data = tmp_path / "questions.jsonl"
    row = {"id": "q", "input": "如何设计可靠的复杂问题搜索树？", "reference": "first"}
    data.write_text(json.dumps(row), encoding="utf-8")
    raw["datasets"][0]["params"]["path"] = str(data)
    raw["experiments"][0]["repeats"] = 2
    raw["runtime"]["max_workers"] = 2
    monkeypatch.chdir(tmp_path)
    first = run_study(study_spec_from_mapping(raw))
    root = tmp_path / "outputs/studies" / raw["id"]
    paths = [
        root / a["artifact_path"]
        for a in first["artifacts"].values()
        if a["identity"]["stage"] == "run"
    ]
    assert len({read_json(p / "tree.json")["session_id"] for p in paths}) == 2
    assert {read_json(p / "result.json")["seed"] for p in paths} == {0, 1}
    for p in paths:
        assert "reference" not in read_json(p / "request.json")["case"]
    row["reference"] = "changed-only-reference"
    data.write_text(json.dumps(row), encoding="utf-8")
    scored = run_study(study_spec_from_mapping(raw))
    assert all(
        scored["artifacts"][k]["identity"]["stage"] != "run" for k in scored["executed"]
    )
