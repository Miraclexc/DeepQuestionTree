"""Real DeepSeek Flash CLI lifecycle; no mocked model, process or artifact."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.e2e


def test_real_flash_study_cli_lifecycle(tmp_path):
    from project.methods import credential_environment

    if not credential_environment("LLM__API_KEY").get("LLM__API_KEY"):
        pytest.fail(
            "Real E2E requires LLM__API_KEY in project .env or process environment"
        )
    raw = yaml.safe_load(
        (ROOT / "configs/studies/tree-search.yaml").read_text(encoding="utf-8")
    )
    raw["id"] = "dqt-live-acceptance"
    cases = tmp_path / "cases.jsonl"
    cases.write_text(
        json.dumps(
            {
                "id": "live-1",
                "input": "如何用有限计算预算构建可靠的复杂问题搜索树？请简要分析探索与验证。",
                "split": "test",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    raw["datasets"][0]["params"]["path"] = str(cases)
    raw["methods"][0]["code_dependencies"] = [
        str(ROOT / name) for name in raw["methods"][0]["code_dependencies"]
    ]
    raw["experiments"][0]["repeats"] = 1
    raw["experiments"][0]["params"]["limits"] = {
        "max_steps": 1,
        "time_seconds": 600,
        "tokens": 30000,
    }
    study = tmp_path / "live.yaml"
    study.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    cli = str(
        Path(sys.executable).parent / ("paper.exe" if os.name == "nt" else "paper")
    )

    def run(*args):
        process = subprocess.run(
            [cli, *map(str, args)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONUTF8": "1"},
            timeout=660,
        )
        assert process.returncode == 0, process.stdout + process.stderr
        return process.stdout

    assert "valid" in run("validate", study)
    assert "RUN" in run("plan", study)
    assert "completed" in run("run", study)
    root = tmp_path / "outputs/studies" / raw["id"]
    manifest = json.loads((root / "artifact_index.json").read_text(encoding="utf-8"))
    artifact = next(a for a in manifest.values() if a["identity"]["stage"] == "run")
    output = root / artifact["artifact_path"]
    result = json.loads((output / "result.json").read_text(encoding="utf-8"))
    assert result["status"] == "completed" and result["answer"]
    assert result["mock"] is False and result["tokens"] > 0
    assert result["tree_nodes"] >= 1 and result["llm_calls"] > 0
    tree = json.loads((output / "tree.json").read_text(encoding="utf-8"))
    assert tree["status"] == "completed"
    # A real model can legitimately hit the original 50-fact saturation rule.
    # Branch expansion is deterministic only in the offline algorithm tests.
    if result["tree_nodes"] == 1:
        root_node = tree["nodes"][tree["root_node_id"]]
        assert root_node["is_pruned"] and root_node["prune_reason"]
    assert {e["response"]["model"] for e in result["events"]} == {"deepseek-flash"}
    assert (output / "tree.json").is_file() and (
        output / "answer_report.json"
    ).is_file()
    assert "executed=0" in run("run", study)
    exported = tmp_path / "metrics.csv"
    run("export", root, exported)
    assert "completed" in exported.read_text(encoding="utf-8")
    run("archive", raw["id"])
    assert list((tmp_path / "outputs/archives").iterdir())
