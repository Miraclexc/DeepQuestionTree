from pathlib import Path

import pytest
import run_tests


def test_capture_runtime_artifact_state_records_relative_files(tmp_path):
    sessions_dir = tmp_path / "data" / "sessions"
    logs_dir = tmp_path / "data" / "logs"
    sessions_dir.mkdir(parents=True)
    logs_dir.mkdir(parents=True)

    (sessions_dir / ".gitkeep").write_text("", encoding="utf-8")
    (sessions_dir / "session.json").write_text("{}", encoding="utf-8")
    (logs_dir / "backend.log").write_text("log", encoding="utf-8")

    snapshot = run_tests.capture_runtime_artifact_state(
        tmp_path,
        [Path("data/sessions"), Path("data/logs")],
    )

    assert snapshot["data/sessions"] == {".gitkeep", "session.json"}
    assert snapshot["data/logs"] == {"backend.log"}


def test_assert_runtime_artifact_state_unchanged_detects_new_files(tmp_path):
    sessions_dir = tmp_path / "data" / "sessions"
    logs_dir = tmp_path / "data" / "logs"
    sessions_dir.mkdir(parents=True)
    logs_dir.mkdir(parents=True)
    (sessions_dir / ".gitkeep").write_text("", encoding="utf-8")

    snapshot = run_tests.capture_runtime_artifact_state(
        tmp_path,
        [Path("data/sessions"), Path("data/logs")],
    )

    (sessions_dir / "new-session.json").write_text("{}", encoding="utf-8")

    with pytest.raises(RuntimeError, match="data/sessions"):
        run_tests.assert_runtime_artifact_state_unchanged(
            tmp_path,
            [Path("data/sessions"), Path("data/logs")],
            snapshot,
        )


def test_build_ci_environment_redirects_runtime_artifacts(tmp_path):
    env = run_tests.build_ci_environment(
        tmp_path / "ci-runtime",
        base_env={"PATH": "test-path", "EXTRA_FLAG": "1"},
    )

    assert env["PATH"] == "test-path"
    assert env["EXTRA_FLAG"] == "1"
    assert env["STORAGE__DATA_DIR"] == str(tmp_path / "ci-runtime")
    assert env["STORAGE__SESSIONS_DIR"] == str(tmp_path / "ci-runtime" / "sessions")
    assert env["STORAGE__SESSION_DB_PATH"] == str(
        tmp_path / "ci-runtime" / "sessions" / "deepquestiontree.sqlite3"
    )
    assert env["STORAGE__LOGS_DIR"] == str(tmp_path / "ci-runtime" / "logs")


def test_build_backend_test_environment_redirects_sqlite_and_logs(tmp_path):
    env = run_tests.build_backend_test_environment(
        tmp_path / "backend-runtime",
        base_env={"PATH": "test-path"},
    )

    assert env["PATH"] == "test-path"
    assert "STORAGE__DATA_DIR" not in env
    assert env["STORAGE__SESSIONS_DIR"] == str(
        tmp_path / "backend-runtime" / "sessions"
    )
    assert env["STORAGE__SESSION_DB_PATH"] == str(
        tmp_path / "backend-runtime" / "sessions" / "deepquestiontree.sqlite3"
    )
    assert env["STORAGE__LOGS_DIR"] == str(tmp_path / "backend-runtime" / "logs")
    assert env["COVERAGE_FILE"] == str(tmp_path / "backend-runtime" / ".coverage")


def test_run_ci_checks_uses_isolated_runtime_environment(monkeypatch, tmp_path):
    captured_frontend_envs: list[dict[str, str]] = []
    captured_pytest_envs: list[dict[str, str]] = []

    monkeypatch.setattr(run_tests, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        run_tests, "capture_runtime_artifact_state", lambda *args, **kwargs: {}
    )
    monkeypatch.setattr(
        run_tests,
        "assert_runtime_artifact_state_unchanged",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(run_tests, "run_quality_checks", lambda: 0)

    def fake_run_pytest(args, env=None):
        captured_pytest_envs.append(env)
        return 0

    def fake_run_frontend_command(args, env=None):
        captured_frontend_envs.append(env)
        return 0

    monkeypatch.setattr(run_tests, "run_pytest", fake_run_pytest)
    monkeypatch.setattr(run_tests, "run_frontend_command", fake_run_frontend_command)

    assert run_tests.run_ci_checks() == 0
    assert len(captured_pytest_envs) == 1
    assert "STORAGE__DATA_DIR" not in captured_pytest_envs[0]
    assert captured_pytest_envs[0]["STORAGE__SESSIONS_DIR"].endswith("sessions")
    assert captured_pytest_envs[0]["STORAGE__SESSION_DB_PATH"].endswith(
        "sessions\\deepquestiontree.sqlite3"
    )
    assert captured_pytest_envs[0]["STORAGE__LOGS_DIR"].endswith("logs")
    assert len(captured_frontend_envs) == 1
    assert captured_frontend_envs[0]["STORAGE__DATA_DIR"] != str(tmp_path / "data")
    assert captured_frontend_envs[0]["STORAGE__SESSIONS_DIR"].endswith("sessions")
    assert captured_frontend_envs[0]["STORAGE__SESSION_DB_PATH"].endswith(
        "sessions\\deepquestiontree.sqlite3"
    )
    assert captured_frontend_envs[0]["STORAGE__LOGS_DIR"].endswith("logs")


def test_build_frontend_e2e_environment_defaults_to_mock_backend(tmp_path):
    env = run_tests.build_frontend_e2e_environment(
        tmp_path / "frontend-runtime",
        provider=None,
        base_env={"PATH": "test-path"},
    )

    assert env["PATH"] == "test-path"
    assert env["PLAYWRIGHT_E2E_PROVIDER"] == "mock"
    assert env["PLAYWRIGHT_BACKEND_MOCK_LLM"] == "true"
    assert "EMBEDDING__USE_LOCAL" not in env


def test_build_frontend_e2e_environment_maps_deepseek_provider(tmp_path):
    env = run_tests.build_frontend_e2e_environment(
        tmp_path / "frontend-runtime",
        provider="deepseek",
        base_env={
            "PATH": "test-path",
            "E2E_DEEPSEEK_API_KEY": "sk-deepseek",
        },
    )

    assert env["PLAYWRIGHT_E2E_PROVIDER"] == "deepseek"
    assert env["PLAYWRIGHT_BACKEND_MOCK_LLM"] == "false"
    assert env["PLAYWRIGHT_E2E_DEEPSEEK_API_KEY"] == "sk-deepseek"
    assert env["PLAYWRIGHT_E2E_DEEPSEEK_BASE_URL"] == "https://api.deepseek.com/v1"
    assert env["PLAYWRIGHT_E2E_DEEPSEEK_GENERATION_MODEL"] == "deepseek-chat"
    assert env["PLAYWRIGHT_E2E_DEEPSEEK_DECISION_MODEL"] == "deepseek-chat"
    assert "EMBEDDING__USE_LOCAL" not in env
    assert "EMBEDDING__LOCAL_FILES_ONLY" not in env
    assert "EMBEDDING__FALLBACK_MODE" not in env
