import path from "node:path";
import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vitest/config";

const frontendRoot = fileURLToPath(new URL("./", import.meta.url));
const repositoryRoot = fileURLToPath(new URL("../..", import.meta.url));
const frontendNodeModules = path.resolve(frontendRoot, "node_modules");
const testingLibraryJestDomPath = path.resolve(
    frontendNodeModules,
    "@testing-library/jest-dom/vitest.js",
);
const testingLibraryReactPath = path.resolve(
    frontendNodeModules,
    "@testing-library/react/dist/index.js",
);
const testingLibraryUserEventPath = path.resolve(
    frontendNodeModules,
    "@testing-library/user-event/dist/esm/index.js",
);
const mswCorePath = path.resolve(frontendNodeModules, "msw/lib/core/index.mjs");
const mswNodePath = path.resolve(frontendNodeModules, "msw/lib/node/index.mjs");
const html2pdfStubPath = path.resolve(
    repositoryRoot,
    "tests/frontend/setup/stubs/html2pdf.ts",
);
const reactPath = path.resolve(frontendNodeModules, "react/index.js");
const reactJsxRuntimePath = path.resolve(frontendNodeModules, "react/jsx-runtime.js");
const reactJsxDevRuntimePath = path.resolve(
    frontendNodeModules,
    "react/jsx-dev-runtime.js",
);
const reactDomPath = path.resolve(frontendNodeModules, "react-dom/index.js");
const reactDomClientPath = path.resolve(frontendNodeModules, "react-dom/client.js");
const reactDomTestUtilsPath = path.resolve(
    frontendNodeModules,
    "react-dom/test-utils.js",
);

export default defineConfig({
    root: frontendRoot,
    oxc: {
        jsx: {
            runtime: "automatic",
        },
    },
    server: {
        fs: {
            allow: [repositoryRoot],
        },
    },
    resolve: {
        tsconfigPaths: true,
        alias: [
            { find: /^@\/(.*)$/, replacement: `${frontendRoot}$1` },
            {
                find: /^@testing-library\/jest-dom\/vitest$/,
                replacement: testingLibraryJestDomPath,
            },
            {
                find: /^@testing-library\/react$/,
                replacement: testingLibraryReactPath,
            },
            {
                find: /^@testing-library\/user-event$/,
                replacement: testingLibraryUserEventPath,
            },
            { find: /^html2pdf\.js$/, replacement: html2pdfStubPath },
            { find: /^msw\/node$/, replacement: mswNodePath },
            { find: /^msw$/, replacement: mswCorePath },
            { find: /^react\/jsx-dev-runtime$/, replacement: reactJsxDevRuntimePath },
            { find: /^react\/jsx-runtime$/, replacement: reactJsxRuntimePath },
            { find: /^react-dom\/test-utils$/, replacement: reactDomTestUtilsPath },
            { find: /^react-dom\/client$/, replacement: reactDomClientPath },
            { find: /^react-dom$/, replacement: reactDomPath },
            { find: /^react$/, replacement: reactPath },
        ],
    },
    test: {
        alias: [
            { find: /^@\/(.*)$/, replacement: `${frontendRoot}$1` },
            {
                find: /^@testing-library\/jest-dom\/vitest$/,
                replacement: testingLibraryJestDomPath,
            },
            {
                find: /^@testing-library\/react$/,
                replacement: testingLibraryReactPath,
            },
            {
                find: /^@testing-library\/user-event$/,
                replacement: testingLibraryUserEventPath,
            },
            { find: /^html2pdf\.js$/, replacement: html2pdfStubPath },
            { find: /^msw\/node$/, replacement: mswNodePath },
            { find: /^msw$/, replacement: mswCorePath },
            { find: /^react\/jsx-dev-runtime$/, replacement: reactJsxDevRuntimePath },
            { find: /^react\/jsx-runtime$/, replacement: reactJsxRuntimePath },
            { find: /^react-dom\/test-utils$/, replacement: reactDomTestUtilsPath },
            { find: /^react-dom\/client$/, replacement: reactDomClientPath },
            { find: /^react-dom$/, replacement: reactDomPath },
            { find: /^react$/, replacement: reactPath },
        ],
        environment: "jsdom",
        globals: true,
        deps: {
            moduleDirectories: ["node_modules", frontendNodeModules],
        },
        setupFiles: [
            fileURLToPath(
                new URL("../../tests/frontend/setup/vitest.setup.ts", import.meta.url),
            ),
        ],
        include: [
            "../../tests/frontend/**/*.test.{ts,tsx}",
            "../../tests/frontend/**/*.spec.{ts,tsx}",
        ],
        exclude: ["../../tests/frontend/e2e/**"],
        coverage: {
            provider: "v8",
            reporter: ["text", "html"],
            reportsDirectory: "./coverage",
        },
    },
});
