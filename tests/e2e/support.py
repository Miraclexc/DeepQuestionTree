from __future__ import annotations

import os
import socket
import subprocess
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import httpx


class E2EConfigError(RuntimeError):
    """Raised when E2E runtime configuration is incomplete or invalid."""


@dataclass(frozen=True, slots=True)
class ProviderProfile:
    provider: str
    api_key: str
    base_url: str
    generation_model: str
    decision_model: str
    api_token: str
    timeout_seconds: int
    max_simulations: int


def resolve_provider_profile(
    *,
    provider: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> ProviderProfile:
    env = environ or os.environ
    requested_provider = (provider or env.get("E2E_PROVIDER", "")).strip().lower()
    if not requested_provider:
        raise E2EConfigError(
            "Missing E2E provider. Use --e2e-provider or set E2E_PROVIDER."
        )

    api_token = env.get("E2E_API_TOKEN", "test-token")
    timeout_seconds = _parse_positive_int(
        env.get("E2E_TIMEOUT_SECONDS"),
        default=180,
        variable_name="E2E_TIMEOUT_SECONDS",
    )
    max_simulations = _parse_positive_int(
        env.get("E2E_MAX_SIMULATIONS"),
        default=2,
        variable_name="E2E_MAX_SIMULATIONS",
    )

    if requested_provider == "deepseek":
        api_key = _require_env(env, "E2E_DEEPSEEK_API_KEY")
        base_url = env.get("E2E_DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        generation_model = env.get("E2E_DEEPSEEK_GENERATION_MODEL", "deepseek-chat")
        decision_model = env.get("E2E_DEEPSEEK_DECISION_MODEL", generation_model)
        return ProviderProfile(
            provider=requested_provider,
            api_key=api_key,
            base_url=base_url,
            generation_model=generation_model,
            decision_model=decision_model,
            api_token=api_token,
            timeout_seconds=timeout_seconds,
            max_simulations=max_simulations,
        )

    if requested_provider == "openai-compatible":
        api_key = _require_env(env, "E2E_OPENAI_COMPATIBLE_API_KEY")
        base_url = _require_env(env, "E2E_OPENAI_COMPATIBLE_BASE_URL")
        generation_model = _require_env(env, "E2E_OPENAI_COMPATIBLE_GENERATION_MODEL")
        decision_model = _require_env(env, "E2E_OPENAI_COMPATIBLE_DECISION_MODEL")
        return ProviderProfile(
            provider=requested_provider,
            api_key=api_key,
            base_url=base_url,
            generation_model=generation_model,
            decision_model=decision_model,
            api_token=api_token,
            timeout_seconds=timeout_seconds,
            max_simulations=max_simulations,
        )

    raise E2EConfigError(
        f"Unsupported E2E provider: {requested_provider}. "
        "Supported providers are: openai-compatible, deepseek."
    )


def build_backend_environment(
    *,
    profile: ProviderProfile,
    port: int,
    data_dir: Path,
) -> dict[str, str]:
    sessions_dir = data_dir / "sessions"
    logs_dir = data_dir / "logs"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "APP__DEBUG": "false",
            "APP__MOCK_LLM": "false",
            "APP__ENV": "e2e",
            "APP__API_PORT": str(port),
            "SECURITY__API_TOKEN": profile.api_token,
            "LLM__API_KEY": profile.api_key,
            "LLM__BASE_URL": profile.base_url,
            "LLM__GENERATION_MODEL": profile.generation_model,
            "LLM__DECISION_MODEL": profile.decision_model,
            "STORAGE__DATA_DIR": str(data_dir),
            "STORAGE__SESSIONS_DIR": str(sessions_dir),
            "STORAGE__LOGS_DIR": str(logs_dir),
            "MCTS__PARALLEL_WORKERS": "1",
            "MCTS__MAX_SIMULATIONS": str(profile.max_simulations),
            "EMBEDDING__USE_LOCAL": "true",
            "EMBEDDING__LOCAL_FILES_ONLY": "true",
            "EMBEDDING__FALLBACK_MODE": "hash",
        }
    )
    return env


def allocate_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(sock.getsockname()[1])


class ManagedE2EServer:
    def __init__(
        self,
        *,
        project_root: Path,
        profile: ProviderProfile,
        data_dir: Path,
        port: int,
        process: subprocess.Popen[str],
        output_path: Path,
        output_handle,
    ) -> None:
        self.project_root = project_root
        self.profile = profile
        self.data_dir = data_dir
        self.port = port
        self.process = process
        self.output_path = output_path
        self._output_handle = output_handle
        self.base_url = f"http://127.0.0.1:{port}"
        self.sessions_dir = data_dir / "sessions"

    @classmethod
    def start(
        cls,
        *,
        project_root: Path,
        profile: ProviderProfile,
        data_dir: Path,
    ) -> "ManagedE2EServer":
        port = allocate_free_port()
        output_path = data_dir / "server-output.log"
        data_dir.mkdir(parents=True, exist_ok=True)
        output_handle = output_path.open("w", encoding="utf-8")
        process = subprocess.Popen(
            ["uv", "run", "python", "-m", "src.backend.main"],
            cwd=project_root,
            env=build_backend_environment(
                profile=profile, port=port, data_dir=data_dir
            ),
            stdout=output_handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
        return cls(
            project_root=project_root,
            profile=profile,
            data_dir=data_dir,
            port=port,
            process=process,
            output_path=output_path,
            output_handle=output_handle,
        )

    @asynccontextmanager
    async def create_client(self):
        timeout = httpx.Timeout(self.profile.timeout_seconds)
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers={"Authorization": f"Bearer {self.profile.api_token}"},
        ) as client:
            yield client

    async def wait_until_ready(self) -> None:
        deadline = time.monotonic() + min(self.profile.timeout_seconds, 60)
        last_error: str | None = None
        while time.monotonic() < deadline:
            self._raise_if_process_exited()
            try:
                async with self.create_client() as client:
                    response = await client.get("/api/status")
                if response.status_code == 200:
                    return
                last_error = f"status_code={response.status_code}"
            except httpx.HTTPError as exc:
                last_error = str(exc)
            await _sleep_briefly()

        details = last_error or "server did not become ready"
        raise TimeoutError(
            f"E2E backend was not ready in time: {details}\n{self.read_output_tail()}"
        )

    async def wait_for_session_completion(self, session_id: str) -> dict:
        deadline = time.monotonic() + self.profile.timeout_seconds
        last_payload: dict | None = None
        while time.monotonic() < deadline:
            self._raise_if_process_exited()
            async with self.create_client() as client:
                response = await client.get(f"/api/sessions/{session_id}")
            if response.status_code == 200:
                last_payload = response.json()
                if last_payload.get("status") != "running":
                    return last_payload
            await _sleep_briefly()

        raise TimeoutError(
            f"Session {session_id} did not complete within {self.profile.timeout_seconds} seconds.\n"
            f"Last payload: {last_payload}\n"
            f"{self.read_output_tail()}"
        )

    def session_file(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.json"

    def read_output_tail(self, max_lines: int = 60) -> str:
        try:
            self._output_handle.flush()
        except ValueError:
            pass
        if not self.output_path.exists():
            return "No server output captured."
        lines = self.output_path.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()
        tail = "\n".join(lines[-max_lines:])
        return f"Server output tail:\n{tail}" if tail else "Server output is empty."

    async def stop(self) -> None:
        try:
            self._output_handle.flush()
        except ValueError:
            pass
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=15)
        self._output_handle.close()

    def _raise_if_process_exited(self) -> None:
        return_code = self.process.poll()
        if return_code is None:
            return
        raise RuntimeError(
            f"E2E backend exited early with code {return_code}.\n{self.read_output_tail()}"
        )


async def _sleep_briefly() -> None:
    import asyncio

    await asyncio.sleep(0.5)


def _require_env(environ: Mapping[str, str], name: str) -> str:
    value = environ.get(name, "").strip()
    if value:
        return value
    raise E2EConfigError(f"Missing required E2E environment variable: {name}")


def _parse_positive_int(
    value: str | None,
    *,
    default: int,
    variable_name: str,
) -> int:
    if value in (None, ""):
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise E2EConfigError(
            f"{variable_name} must be an integer, got: {value}"
        ) from exc
    if parsed <= 0:
        raise E2EConfigError(f"{variable_name} must be greater than 0")
    return parsed
