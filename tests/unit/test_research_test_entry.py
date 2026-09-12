import importlib.util
from pathlib import Path


def test_test_entry_has_only_research_commands():
    spec = importlib.util.spec_from_file_location(
        "test_entry", Path(__file__).resolve().parents[2] / "run_tests.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.commands("all") == [["uv", "run", "pytest", "tests/", "-v"]]
    assert "--run-e2e" in module.commands("e2e")[0]
    assert all("npm" not in command for command in module.commands("ci"))
