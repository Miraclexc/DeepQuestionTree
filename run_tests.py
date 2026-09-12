"""Research-only local quality and test entry point; all Python tools use UV."""

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def commands(mode):
    quality = [
        [
            "uv",
            "run",
            "python",
            "-m",
            "black",
            "--check",
            "src/project",
            "tests",
            "run_tests.py",
        ],
        [
            "uv",
            "run",
            "python",
            "-m",
            "isort",
            "--check-only",
            "src/project",
            "tests",
            "run_tests.py",
        ],
        ["uv", "run", "python", "-m", "mypy", "src/project/dqt"],
    ]
    suites = {
        "all": [["uv", "run", "pytest", "tests/", "-v"]],
        "unit": [["uv", "run", "pytest", "tests/unit/", "-v"]],
        "integration": [["uv", "run", "pytest", "tests/integration/", "-v"]],
        "e2e": [["uv", "run", "pytest", "tests/e2e/", "-v", "--run-e2e"]],
        "quality": quality,
    }
    suites["ci"] = quality + suites["all"]
    return suites[mode]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode",
        choices=("all", "unit", "integration", "e2e", "quality", "ci"),
        default="all",
        nargs="?",
    )
    args = parser.parse_args(argv)
    for command in commands(args.mode):
        result = subprocess.run(command, cwd=ROOT)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
