"""便捷测试入口。所有 pytest 调用统一通过 uv 执行。"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
FRONTEND_ROOT = PROJECT_ROOT / "src" / "frontend"
RUNTIME_ARTIFACT_DIRS = [Path("data/sessions"), Path("data/logs")]


def run_command(
    command: list[str], *, cwd: Path, env: dict[str, str] | None = None
) -> int:
    result = subprocess.run(command, cwd=cwd, env=env)
    return result.returncode


def run_pytest(args: list[str], env: dict[str, str] | None = None) -> int:
    return run_command(["uv", "run", "pytest", *args], cwd=PROJECT_ROOT, env=env)


def run_frontend_command(args: list[str], env: dict[str, str] | None = None) -> int:
    npm_executable = "npm.cmd" if os.name == "nt" else "npm"
    return run_command([npm_executable, *args], cwd=FRONTEND_ROOT, env=env)


def capture_runtime_artifact_state(
    project_root: Path,
    artifact_dirs: list[Path],
) -> dict[str, set[str]]:
    snapshot: dict[str, set[str]] = {}
    for relative_dir in artifact_dirs:
        absolute_dir = project_root / relative_dir
        if not absolute_dir.exists():
            snapshot[relative_dir.as_posix()] = set()
            continue

        files = {
            path.relative_to(absolute_dir).as_posix()
            for path in absolute_dir.rglob("*")
            if path.is_file()
        }
        snapshot[relative_dir.as_posix()] = files

    return snapshot


def assert_runtime_artifact_state_unchanged(
    project_root: Path,
    artifact_dirs: list[Path],
    before_snapshot: dict[str, set[str]],
) -> None:
    after_snapshot = capture_runtime_artifact_state(project_root, artifact_dirs)
    changes: list[str] = []

    for relative_dir in artifact_dirs:
        key = relative_dir.as_posix()
        before_files = before_snapshot.get(key, set())
        after_files = after_snapshot.get(key, set())
        added = sorted(after_files - before_files)
        removed = sorted(before_files - after_files)
        if added or removed:
            change_parts: list[str] = []
            if added:
                change_parts.append(f"added={added}")
            if removed:
                change_parts.append(f"removed={removed}")
            changes.append(f"{key}: {'; '.join(change_parts)}")

    if changes:
        raise RuntimeError(
            "Runtime artifact directories changed during CI run: " + " | ".join(changes)
        )


def build_ci_environment(
    runtime_root: Path,
    base_env: dict[str, str] | None = None,
) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    sessions_dir = runtime_root / "sessions"
    logs_dir = runtime_root / "logs"

    runtime_root.mkdir(parents=True, exist_ok=True)
    sessions_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    env["STORAGE__DATA_DIR"] = str(runtime_root)
    env["STORAGE__SESSIONS_DIR"] = str(sessions_dir)
    env["STORAGE__LOGS_DIR"] = str(logs_dir)
    env["COVERAGE_FILE"] = str(runtime_root / ".coverage")

    return env


def build_backend_test_environment(
    runtime_root: Path,
    base_env: dict[str, str] | None = None,
) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    logs_dir = runtime_root / "logs"

    runtime_root.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    env["STORAGE__LOGS_DIR"] = str(logs_dir)
    env["COVERAGE_FILE"] = str(runtime_root / ".coverage")

    return env


def build_frontend_e2e_environment(
    runtime_root: Path,
    *,
    provider: str | None = None,
    base_env: dict[str, str] | None = None,
) -> dict[str, str]:
    env = build_ci_environment(runtime_root, base_env=base_env)
    selected_provider = (provider or "mock").strip().lower() or "mock"
    api_token = env.get("E2E_API_TOKEN", "test-token")

    env["PLAYWRIGHT_API_TOKEN"] = api_token
    env["PLAYWRIGHT_E2E_PROVIDER"] = selected_provider

    if selected_provider == "mock":
        env["PLAYWRIGHT_BACKEND_MOCK_LLM"] = "true"
        env["EMBEDDING__USE_LOCAL"] = "false"
        env["PLAYWRIGHT_ASSERT_TIMEOUT_MS"] = "30000"
        env["PLAYWRIGHT_TEST_TIMEOUT_MS"] = "90000"
        env["PLAYWRIGHT_BACKEND_TIMEOUT_MS"] = "180000"
        return env

    if selected_provider == "deepseek":
        api_key = env.get("E2E_DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "Missing E2E_DEEPSEEK_API_KEY for frontend-e2e deepseek."
            )

        env["PLAYWRIGHT_BACKEND_MOCK_LLM"] = "false"
        env["PLAYWRIGHT_E2E_DEEPSEEK_API_KEY"] = api_key
        env["PLAYWRIGHT_E2E_DEEPSEEK_BASE_URL"] = env.get(
            "E2E_DEEPSEEK_BASE_URL",
            "https://api.deepseek.com/v1",
        )
        env["PLAYWRIGHT_E2E_DEEPSEEK_GENERATION_MODEL"] = env.get(
            "E2E_DEEPSEEK_GENERATION_MODEL",
            "deepseek-chat",
        )
        env["PLAYWRIGHT_E2E_DEEPSEEK_DECISION_MODEL"] = env.get(
            "E2E_DEEPSEEK_DECISION_MODEL",
            env["PLAYWRIGHT_E2E_DEEPSEEK_GENERATION_MODEL"],
        )
        env["EMBEDDING__USE_LOCAL"] = "true"
        env["EMBEDDING__LOCAL_FILES_ONLY"] = "true"
        env["EMBEDDING__FALLBACK_MODE"] = "hash"
        env["PLAYWRIGHT_ASSERT_TIMEOUT_MS"] = "120000"
        env["PLAYWRIGHT_TEST_TIMEOUT_MS"] = "300000"
        env["PLAYWRIGHT_BACKEND_TIMEOUT_MS"] = "300000"
        return env

    raise RuntimeError(f"Unsupported frontend E2E provider: {selected_provider}")


def run_all_tests() -> int:
    print("运行所有后端测试...")
    backend_code = run_pytest(["tests/", "-v"])
    if backend_code != 0:
        return backend_code

    print("运行所有前端测试...")
    return run_frontend_command(["run", "test:ci"])


def run_quality_checks() -> int:
    print("运行格式、导入顺序和类型检查...")
    quality_commands = [
        ["uv", "run", "black", "--check", "src", "tests", "run_tests.py"],
        ["uv", "run", "isort", "--check-only", "src", "tests", "run_tests.py"],
        ["uv", "run", "mypy", "src/backend"],
    ]

    for command in quality_commands:
        result = run_command(command, cwd=PROJECT_ROOT)
        if result != 0:
            return result

    return 0


def run_ci_checks() -> int:
    before_snapshot = capture_runtime_artifact_state(
        PROJECT_ROOT, RUNTIME_ARTIFACT_DIRS
    )

    quality_code = run_quality_checks()
    if quality_code != 0:
        return quality_code

    with tempfile.TemporaryDirectory(prefix="dqt-ci-runtime-") as runtime_dir:
        runtime_root = Path(runtime_dir)
        backend_env = build_backend_test_environment(runtime_root / "backend")
        frontend_env = build_ci_environment(runtime_root / "frontend")

        backend_code = run_pytest(
            ["tests/", "-v", "--cov-fail-under=80"],
            env=backend_env,
        )
        if backend_code != 0:
            return backend_code

        frontend_code = run_frontend_command(["run", "test:ci"], env=frontend_env)
        if frontend_code != 0:
            return frontend_code

    try:
        assert_runtime_artifact_state_unchanged(
            PROJECT_ROOT,
            RUNTIME_ARTIFACT_DIRS,
            before_snapshot,
        )
    except RuntimeError as exc:
        print(str(exc))
        return 1

    return 0


def run_unit_tests() -> int:
    print("运行单元测试...")
    return run_pytest(["tests/unit/", "-v", "-m", "unit"])


def run_integration_tests() -> int:
    print("运行集成测试...")
    return run_pytest(["tests/integration/", "-v", "-m", "integration"])


def run_e2e_tests(provider: str | None = None) -> int:
    print("运行真实 API E2E 测试...")
    args = ["tests/e2e/", "-v", "--run-e2e"]
    if provider:
        args.extend(["--e2e-provider", provider])
    return run_pytest(args)


def run_with_coverage() -> int:
    print("运行测试并生成覆盖率报告...")
    return run_pytest(
        [
            "tests/",
            "--cov=src/backend",
            "--cov-report=html",
            "--cov-report=term-missing",
            "-v",
        ]
    )


def run_frontend_tests() -> int:
    print("运行前端单元/组件测试...")
    test_code = run_frontend_command(["run", "test", "--", "--run"])
    if test_code != 0:
        return test_code

    print("运行前端构建验证...")
    return run_frontend_command(["run", "build"])


def run_frontend_e2e_tests(provider: str | None = None) -> int:
    provider_label = (provider or "mock").strip().lower() or "mock"
    print(f"运行前端浏览器 Smoke 测试... provider={provider_label}")
    try:
        with tempfile.TemporaryDirectory(prefix="dqt-frontend-e2e-") as runtime_dir:
            env = build_frontend_e2e_environment(
                Path(runtime_dir),
                provider=provider_label,
            )
            return run_frontend_command(["run", "test:e2e"], env=env)
    except RuntimeError as exc:
        print(str(exc))
        return 1


def run_frontend_coverage() -> int:
    print("运行前端测试并生成覆盖率报告...")
    return run_frontend_command(["run", "test:coverage"])


def run_specific_test(test_path: str) -> int:
    print(f"运行测试: {test_path}")
    return run_pytest([test_path, "-v"])


if __name__ == "__main__":
    if len(sys.argv) <= 1:
        sys.exit(run_all_tests())

    command = sys.argv[1]

    if command == "all":
        sys.exit(run_all_tests())
    if command == "unit":
        sys.exit(run_unit_tests())
    if command == "integration":
        sys.exit(run_integration_tests())
    if command == "e2e":
        provider = sys.argv[2] if len(sys.argv) > 2 else None
        sys.exit(run_e2e_tests(provider))
    if command == "frontend":
        sys.exit(run_frontend_tests())
    if command == "frontend-e2e":
        provider = sys.argv[2] if len(sys.argv) > 2 else None
        sys.exit(run_frontend_e2e_tests(provider))
    if command == "frontend-coverage":
        sys.exit(run_frontend_coverage())
    if command == "quality":
        sys.exit(run_quality_checks())
    if command == "ci":
        sys.exit(run_ci_checks())
    if command == "coverage":
        sys.exit(run_with_coverage())
    if command.startswith("tests/") or command.startswith("tests\\"):
        sys.exit(run_specific_test(command))

    print(f"未知命令: {command}")
    print()
    print("可用命令:")
    print("  all          - 运行所有测试")
    print("  unit         - 仅运行单元测试")
    print("  integration  - 仅运行集成测试")
    print("  e2e [provider] - 运行真实 API E2E 测试")
    print("  frontend     - 运行前端 Vitest + 构建验证")
    print("  frontend-e2e [provider] - 运行前端 Playwright Smoke 测试")
    print("  frontend-coverage - 运行前端覆盖率")
    print("  quality      - 运行格式、导入顺序和类型检查")
    print("  ci           - 运行本地 CI 验收并校验工作区不被污染")
    print("  coverage     - 运行测试并生成覆盖率报告")
    print("  tests/...    - 运行特定测试文件")
    sys.exit(1)
