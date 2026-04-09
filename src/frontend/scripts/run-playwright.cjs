const { spawnSync } = require("node:child_process");
const path = require("node:path");
const { Module } = require("node:module");

const frontendRoot = path.resolve(__dirname, "..");
const frontendNodeModules = path.join(frontendRoot, "node_modules");

process.env.NODE_PATH = [process.env.NODE_PATH, frontendNodeModules]
    .filter(Boolean)
    .join(path.delimiter);
Module._initPaths();

const playwrightCli = require.resolve("@playwright/test/cli");
const result = spawnSync(
    process.execPath,
    [playwrightCli, "test", ...process.argv.slice(2)],
    {
        cwd: frontendRoot,
        env: process.env,
        stdio: "inherit",
    },
);

if (typeof result.status === "number") {
    process.exit(result.status);
}

process.exit(1);
