# AGENTS.md — Coding Agent Operating Protocol

> **Version**: 1.0.0  
> **Last Updated**: 2026-02-18

---

## Table of Contents

1. [Purpose](#1-purpose)
2. [Core Principles](#2-core-principles)
3. [Rule 1 — Clarification-First Communication](#3-rule-1--clarification-first-communication)
4. [Rule 2 — Mandatory Documentation Synchronization](#4-rule-2--mandatory-documentation-synchronization)
5. [Rule 3 — UV Environment Management](#5-rule-3--uv-environment-management)
6. [Rule 4 — Test-Driven Development (TDD)](#6-rule-4--test-driven-development-tdd)
7. [Violation Handling](#7-violation-handling)

---

## 1. Purpose

This document defines the operating protocol for any AI Coding Agent working on this project. Every agent **MUST** read and follow this document before performing any task. These rules are **non-negotiable** and take priority over general agent defaults.

---

## 2. Core Principles

| # | Principle | Summary |
|---|-----------|---------|
| 1 | **Ask, don't assume** | When instructions are unclear, always ask the user for clarification before starting work. |
| 2 | **Docs follow code** | Every code change must be accompanied by corresponding documentation updates. |
| 3 | **Read before write** | Always read existing documentation in the `doc/` folder before making any modifications. |
| 4 | **UV only** | All Python projects use UV as the sole package and environment manager. Never use pip, conda, or virtualenv directly. |
| 5 | **Test first** | Strictly follow the TDD cycle. No functional code may be written until a test exists and fails. |

---

## 3. Rule 1 — Clarification-First Communication

### 3.1 When to Ask

The agent **MUST** ask the user for clarification before starting any task if **any** of the following conditions are true:

- **Ambiguous scope**: The user's instruction could reasonably be interpreted in more than one way.
- **Missing target**: The user does not specify which file(s), component(s), or section(s) to modify.
- **Conflicting requirements**: The instruction contradicts existing code, documentation, or prior instructions.
- **Undefined terms**: The user uses project-specific terms or abbreviations that are not documented in `doc/`.
- **Risky operations**: The change involves deleting files, restructuring directories, modifying `_config.yml`, or altering the build/deploy pipeline.
- **Design decisions**: The task requires making architectural or design choices not covered by existing documentation.

### 3.2 How to Ask

When asking for clarification, the agent must:

1. **State what was understood**: Summarize the interpretation of the user's instruction.
2. **Identify ambiguity**: Clearly describe what is unclear or missing.
3. **Propose options**: Offer 2–3 concrete options or interpretations for the user to choose from, when possible.
4. **Keep it concise**: Do not over-explain. Use bullet points.

### 3.3 Example

```
USER: "Update the blog styling"

AGENT RESPONSE (correct):
I'd like to clarify before proceeding:
- **Which aspect of styling?**
  (a) Blog post content typography (headings, paragraphs, code blocks)
  (b) Blog list page layout
  (c) Blog navigation or sidebar
  (d) All of the above
- **Is there a specific design reference** (screenshot, URL, or description)?
- **Should this affect the main portfolio styling** as well, or only the blog section?

AGENT RESPONSE (incorrect):
[Immediately starts modifying assets/css/style.css without asking]
```

### 3.4 Exceptions — When Clarification is NOT Required

The agent may proceed without asking if:

- The instruction is explicit, complete, and unambiguous.
- The change is a direct bug-fix with an obvious single correct solution.
- The user explicitly says "just do it" or "no need to ask" for this specific task.

---

## 4. Rule 2 — Mandatory Documentation Synchronization

### 4.1 The Read-Then-Write Rule

**Before making ANY modification to the project**, the agent MUST:

1. **Read** all relevant documents in the `doc/` folder.
2. **Identify** which documents will be affected by the planned change.
3. **Make** the code/content changes.
4. **Update** the affected documentation to reflect the changes.

> **A code change without a corresponding doc update is considered INCOMPLETE.** The agent must not report a task as "done" unless the documentation has also been updated.

### 4.2 What Counts as a "Change"

Any modification that alters the project's behavior, structure, or conventions, including but not limited to:

| Change Type | Documentation Impact |
|-------------|---------------------|
| New blog post created | Update `doc/blog-conventions.md` if new patterns are introduced |
| File/folder added or renamed | Update `doc/project-structure.md` |
| `_config.yml` modified | Update `doc/configuration.md` |
| Layout or include file changed | Update `doc/layouts-and-includes.md` |
| CSS/JS changes | Update `doc/frontend-guide.md` |
| New feature added | Create or update relevant doc in `doc/` |
| Build/deploy process changed | Update `doc/deployment.md` |


### 4.3 Documentation Quality Standards

When updating documentation, the agent must:

- **Be specific**: Include file paths, code snippets, and configuration values where relevant.
- **Be current**: Remove outdated information; do not leave stale docs.
- **Be structured**: Use headings, tables, and code blocks for readability.
- **Date changes**: Note the date of the last update at the top of each doc file.
- **Cross-reference**: Link to related documents within the `doc/` folder when appropriate.

### 4.4 Creating New Documentation

If a change introduces something that no existing document covers, the agent must:

1. Create a new `.md` file in `doc/` with a descriptive filename (kebab-case, English).
2. Add a reference to the new document in `doc/README.md` (the documentation index).

---

## 5. Rule 3 — UV Environment Management

### 5.1 Policy

**UV is the sole package and environment management tool** for all Python projects in this workspace. The agent **MUST NOT** use `pip`, `conda`, `virtualenv`, `venv`, or `poetry` directly. All dependency and environment operations must go through `uv`.

### 5.2 Common Commands

| Task | Command | Notes |
|------|---------|-------|
| Initialize a new project | `uv init` | Creates `pyproject.toml` and project scaffolding |
| Create virtual environment | `uv venv` | Creates `.venv/` in the project root |
| Activate virtual environment | `.venv\Scripts\activate` (Windows) | Activate before running project code |
| Add a dependency | `uv add <package>` | Adds to `pyproject.toml` and installs |
| Add a dev dependency | `uv add --dev <package>` | For test/lint/dev-only packages |
| Remove a dependency | `uv remove <package>` | Removes from `pyproject.toml` and uninstalls |
| Install all dependencies | `uv sync` | Installs everything from lock file |
| Update lock file | `uv lock` | Regenerates `uv.lock` from `pyproject.toml` |
| Run a command in the env | `uv run <command>` | Runs within the managed environment without manual activation |
| Show installed packages | `uv pip list` | Lists packages in the current environment |

### 5.3 Key Files

| File | Purpose | Version Control |
|------|---------|-----------------|
| `pyproject.toml` | Project metadata and dependency declarations | **Must be committed** |
| `uv.lock` | Deterministic lock file with exact resolved versions | **Must be committed** |
| `.venv/` | Local virtual environment directory | **Must be in `.gitignore`** |
| `.python-version` | Pinned Python version for the project (optional) | Commit if present |

### 5.4 Critical Rules

1. **Never run `pip install` directly.** Always use `uv add` or `uv sync`.
2. **Never modify `uv.lock` manually.** It is auto-generated by `uv lock` or `uv add`.
3. **Always commit both `pyproject.toml` and `uv.lock`** when dependencies change.
4. **Use `uv run`** to execute scripts and tools to ensure the correct environment is used.
5. If the project does not yet have a `pyproject.toml`, run `uv init` before adding dependencies.

---

## 6. Rule 4 — Test-Driven Development (TDD)

### 6.1 TDD Mandate

The agent **MUST** strictly follow the TDD cycle. **No functional code may be written until a test exists and fails.** This is the core mechanism to prevent "hallucination coding" — producing code that looks correct but does not actually run.

### 6.2 Workflow: Red-Green-Refactor

Every feature must be developed following these steps strictly:

1. **Analyze** — Understand the user's requirement and define expected behavior.
2. **Write test** — Create a test case in `tests/` that asserts the expected behavior.
3. **Verify failure (RED)** — Run the test via `uv run pytest`. It **MUST fail** (proving the feature is not yet implemented).
4. **Implement** — Write the **minimal** code to make the test pass.
5. **Verify success (GREEN)** — Run the test again. It **MUST pass**.
6. **Refactor** — Clean up and optimize code while ensuring tests still pass.

> Skipping steps 2–3 (writing functional code before tests) is **strictly prohibited**.

### 6.3 Test Pyramid: Layered Testing Strategy

The agent must write tests at different levels depending on the scope of the change:

#### A. Unit Tests — The Foundation

- **Target**: Individual functions, classes, and logic blocks.
- **Tool**: `pytest`
- **Requirement**: Every complex logic (data parsing algorithms, mathematical models, business rules) must have unit tests covering edge cases (empty inputs, invalid types, extreme values).
- **Location**: `tests/unit/`

#### B. Integration Tests — The Connections

- **Target**: Interaction between modules (e.g., File I/O + Data Parser, or Database + Business Logic).
- **Requirement**: Use `pytest` fixtures to set up temporary environments (e.g., creating a dummy CSV file) and clean them up after the test.
- **Purpose**: Prevent mismatches between module A's output and module B's input (e.g., A outputs a string, B expects a number).
- **Location**: `tests/integration/`

#### C. System / CLI Tests (E2E) — The Black Box

- **Target**: The full application execution flow, from CLI input to final output. **It MUST cover the complete system lifecycle**, simulating real user interactions from the entry point (Frontend UI or CLI arguments) to the final artifacts. Partial testing is insufficient; if no frontend exists, the test must execute the complete backend logic chain.
- **Method**: Invoke the script via `subprocess` or shell commands within the test.
- **Verification**:
    - Check exit codes (0 = success)
    - Check `stdout`/`stderr` for specific output strings
    - Check the file system for generated artifacts (logs, reports, result files)
- **Location**: `tests/e2e/`
- **Time Consumption**: E2E tests integrating real APIs often take a significant amount of time. The agent receives authorization to reserve sufficient time for these tests and should wait patiently for completion.

### 6.4 Mocking Strategy: External Dependencies and E2E Exemptions

- **Default Rule**: For most Unit and Integration tests (Class A & B), tests **MUST NEVER** depend on live external systems (real API calls, real large dataset downloads, paid services). `unittest.mock` or `pytest-mock` **MUST** be used to simulate external responses.
    - **Rationale**: Ensures tests are fast (millisecond-level), stable (unaffected by network fluctuations), and free (no paid quota consumption).
- **Exemptions**: For unit tests specifically designed to verify the connectivity or correctness of external API environments, it is **ALLOWED** to bypass mocks and consume real APIs.
- **E2E Mandatory Rule (Class C)**: For Class C System/E2E Level tests, the Mocking strategy is **STRICTLY PROHIBITED**.
    - **MUST** consume real APIs.
    - **ALLOWED** to use any external dependencies.
    - **Goal**: Perform a comprehensive real-world execution for E2E testing and full system troubleshooting.

### 6.5 Test Directory Structure

```
tests/
├── conftest.py            # Shared fixtures and test configuration
├── unit/                  # Unit tests
│   ├── test_parser.py
│   └── test_models.py
├── integration/           # Integration tests
│   ├── test_pipeline.py
│   └── test_database.py
└── e2e/                   # End-to-end / system tests
    └── test_cli.py
```

### 6.6 Test Verification Protocol

Before marking a task as "complete", the agent **MUST** run the full test suite:

```bash
uv run pytest tests/ -v
```

- If any test **fails**, the agent is in the **debugging phase** and must fix the issue before running again.
- **The agent must not report task completion while any test is failing.**
- To check code coverage, run: `uv run pytest --cov=src tests/`

### 6.7 Diagnosing Test Failures: Code Bug vs Test Bug

> **Core awareness: Tests themselves are AI-generated and may contain errors.**

When a test fails, there are **two possible causes**. The agent must diagnose before fixing:

| Cause | Description | Action |
|-------|-------------|--------|
| **A. Functional code does not meet requirements** | The code has a bug or does not implement the expected behavior | Fix the functional code, re-run tests |
| **B. The test itself does not correctly reflect requirements** | The test's assertions, assumptions, or mock setup are wrong and do not match the original design intent | Fix the test case, re-run tests |

**Diagnosis process:**

1. **Revisit the requirement** — Re-read the user's original requirement and related documentation. Clarify what the "correct behavior" should be.
2. **Review the test** — Check whether the test's assertions accurately reflect the requirement. Ask: "Is the behavior this test asserts what the user actually wants?"
3. **Review the code** — Check whether the functional code's logic matches the requirement.
4. **Determine the fault** — Decide whether the code, the test, or both need to be modified.
5. **Fix and document** — After fixing, note in the commit message or comments whether the code or the test was corrected, and why.

> **No blind fixes**: The agent must NOT simply modify code to make a test pass, or modify a test to make it stop failing, without understanding the root cause. Every fix must be grounded in a correct understanding of the requirements.

### 6.8 When Tests Are Required

| Scenario | Requirement |
|----------|-------------|
| New feature | Must write tests first (TDD) |
| Bug fix | Must write a test that reproduces the bug first, then fix |
| Code refactoring | Ensure existing tests pass; add tests if needed |
| Config/doc changes | No tests required |

---

## 7. Violation Handling

If the agent realizes it has violated any rule in this document (e.g., started work without asking for clarification, or made a code change without updating docs), it must:

1. **Stop** the current task immediately.
2. **Acknowledge** the violation to the user.
3. **Correct** the violation before continuing.

---


