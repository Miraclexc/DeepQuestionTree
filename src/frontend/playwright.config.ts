import { mkdirSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

import { defineConfig, devices } from "@playwright/test";

const provider = process.env.PLAYWRIGHT_E2E_PROVIDER ?? "mock";
const frontendPort = Number(process.env.PLAYWRIGHT_FRONTEND_PORT ?? 3100);
const backendPort = Number(process.env.PLAYWRIGHT_BACKEND_PORT ?? 8101);
const apiToken = process.env.PLAYWRIGHT_API_TOKEN ?? "test-token";
const testTimeout = Number(process.env.PLAYWRIGHT_TEST_TIMEOUT_MS ?? 90_000);
const expectTimeout = Number(process.env.PLAYWRIGHT_ASSERT_TIMEOUT_MS ?? 30_000);
const backendTimeout = Number(process.env.PLAYWRIGHT_BACKEND_TIMEOUT_MS ?? 180_000);

const storageRoot = mkdtempSync(path.join(tmpdir(), "dqt-playwright-"));
const dataDir = path.join(storageRoot, "data");
const sessionsDir = path.join(dataDir, "sessions");
const logsDir = path.join(dataDir, "logs");

mkdirSync(sessionsDir, { recursive: true });
mkdirSync(logsDir, { recursive: true });

function requireEnv(name: string): string {
    const value = process.env[name]?.trim();
    if (!value) {
        throw new Error(`Missing required Playwright environment variable: ${name}`);
    }
    return value;
}

function buildBackendEnvironment(): Record<string, string> {
    const env: Record<string, string> = {
        APP__DEBUG: "false",
        APP__API_PORT: String(backendPort),
        APP__FRONTEND_HOST: "http://127.0.0.1",
        APP__FRONTEND_PORT: String(frontendPort),
        MCTS__MAX_SIMULATIONS: "2",
        MCTS__PARALLEL_WORKERS: "1",
        SECURITY__API_TOKEN: apiToken,
        STORAGE__DATA_DIR: process.env.STORAGE__DATA_DIR ?? dataDir,
        STORAGE__SESSIONS_DIR: process.env.STORAGE__SESSIONS_DIR ?? sessionsDir,
        STORAGE__LOGS_DIR: process.env.STORAGE__LOGS_DIR ?? logsDir,
    };

    if (provider === "deepseek") {
        env.APP__MOCK_LLM = process.env.PLAYWRIGHT_BACKEND_MOCK_LLM ?? "false";
        env.MCTS__MAX_SIMULATIONS =
            process.env.PLAYWRIGHT_MCTS_MAX_SIMULATIONS ?? "1";
        env.MCTS__BRANCH_FACTOR =
            process.env.PLAYWRIGHT_MCTS_BRANCH_FACTOR ?? "2";
        env.LLM__API_KEY = requireEnv("PLAYWRIGHT_E2E_DEEPSEEK_API_KEY");
        env.LLM__BASE_URL =
            process.env.PLAYWRIGHT_E2E_DEEPSEEK_BASE_URL ??
            "https://api.deepseek.com";
        env.LLM__GENERATION_MODEL =
            process.env.PLAYWRIGHT_E2E_DEEPSEEK_GENERATION_MODEL ??
            "deepseek-v4-pro";
        env.LLM__DECISION_MODEL =
            process.env.PLAYWRIGHT_E2E_DEEPSEEK_DECISION_MODEL ??
            "deepseek-v4-pro";
        return env;
    }

    if (provider === "mock") {
        env.APP__MOCK_LLM = process.env.PLAYWRIGHT_BACKEND_MOCK_LLM ?? "true";
        return env;
    }

    throw new Error(`Unsupported Playwright E2E provider: ${provider}`);
}

export default defineConfig({
    testDir: "../../tests/frontend/e2e",
    fullyParallel: false,
    workers: 1,
    timeout: testTimeout,
    expect: {
        timeout: expectTimeout,
    },
    retries: 0,
    use: {
        baseURL: `http://127.0.0.1:${frontendPort}`,
        trace: "retain-on-failure",
        screenshot: "only-on-failure",
        video: "retain-on-failure",
    },
    reporter: [["list"]],
    outputDir: "./test-results",
    projects: [
        {
            name: "chromium",
            use: {
                ...devices["Desktop Chrome"],
            },
        },
    ],
    webServer: [
        {
            command: "uv run python -m src.backend.main",
            url: `http://127.0.0.1:${backendPort}/api/status`,
            cwd: path.resolve(__dirname, "..", ".."),
            reuseExistingServer: false,
            timeout: backendTimeout,
            env: buildBackendEnvironment(),
        },
        {
            command: `npm run build && npm run start -- --hostname 127.0.0.1 --port ${frontendPort}`,
            url: `http://127.0.0.1:${frontendPort}`,
            cwd: __dirname,
            reuseExistingServer: false,
            timeout: 180_000,
            env: {
                NEXT_PUBLIC_API_HOST: "http://127.0.0.1",
                NEXT_PUBLIC_API_PORT: String(backendPort),
                NEXT_PUBLIC_API_TOKEN: apiToken,
            },
        },
    ],
});
