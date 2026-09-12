"""Research migration contracts, specified before implementation."""

import json
from pathlib import Path

import pytest

from project.datasets import load_cases
from project.evaluation import response_metrics
from project.methods import tree_search


def test_dataset_preserves_hidden_reference_and_units(tmp_path):
    path = tmp_path / "cases.jsonl"
    row = {"id": "q1", "input": "question", "reference": "secret", "unit_id": "u1"}
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert load_cases(str(path)) == [{**row, "split": "test", "metadata": {}}]


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [{"id": "a", "input": ""}],
        [{"id": "a", "input": "q"}, {"id": "a", "input": "r"}],
        [{"id": "a", "input": "q", "split": "unknown"}],
        [{"id": "a", "input": 3}],
    ],
)
def test_dataset_rejects_invalid_cases(tmp_path, rows):
    path = tmp_path / "cases.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    with pytest.raises(ValueError):
        load_cases(str(path))


def test_scoring_missing_reference_is_unknown_and_limits_are_not_success():
    score = response_metrics()
    result = {"status": "completed", "answer": " Paris ", "tokens": 9, "steps": 2}
    assert score(result, None)["exact_match"] is None
    assert score(result, ["paris", "Paris"])["exact_match"] == 1
    assert score({**result, "status": "token_limit"}, "Paris")["completed"] == 0
    assert score(result, None)["cost"] is None


def test_method_rejects_secrets_unknown_params_and_invalid_budgets():
    with pytest.raises(ValueError, match="api_key"):
        tree_search(llm={"api_key": "do-not-save"})
    with pytest.raises(ValueError):
        tree_search(mcts={"branch_factor": 0})
    with pytest.raises(ValueError):
        tree_search(mcts={"branck_factor": 2})


def test_method_hides_reference_before_worker(tmp_path, monkeypatch):
    from framework.contracts import RunContext
    from project import methods

    observed = []

    def fake_run(command, **kwargs):
        request = json.loads(Path(command[-1]).read_text(encoding="utf-8"))
        observed.append(request)
        (tmp_path / "result.json").write_text(
            '{"status":"completed"}', encoding="utf-8"
        )
        return type("Process", (), {"returncode": 0})()

    monkeypatch.setattr(methods.subprocess, "run", fake_run)
    tree_search(mock=True).run(
        {"id": "a", "input": "q", "reference": "HIDDEN"},
        RunContext(tmp_path, limits={"max_steps": 1}),
    )
    assert "HIDDEN" not in json.dumps(observed)


def test_credentials_read_only_from_env_or_project_dotenv(tmp_path, monkeypatch):
    from project.methods import credential_environment

    path = tmp_path / ".env"
    path.write_text("LLM__API_KEY=local-secret\nAPP__MOCK_LLM=true\n", encoding="utf-8")
    monkeypatch.delenv("LLM__API_KEY", raising=False)
    monkeypatch.delenv("APP__MOCK_LLM", raising=False)
    env = credential_environment("LLM__API_KEY", path)
    assert env["LLM__API_KEY"] == "local-secret"
    assert "APP__MOCK_LLM" not in env
    monkeypatch.setenv("LLM__API_KEY", "process-secret")
    assert (
        credential_environment("LLM__API_KEY", path)["LLM__API_KEY"] == "process-secret"
    )
