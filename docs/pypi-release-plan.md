# PyPI Application Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a non-empty `docling-serve-mps` 0.1.0 wheel with a minimal background-service CLI and secretless PyPI release automation.

**Architecture:** A single `docling_serve_mps.cli` module owns defaults and the start/stop lifecycle. The source-checkout shell script only prepares the locked uv environment and delegates to that CLI. GitHub Actions builds and verifies the same wheel before publishing through PyPI Trusted Publishing.

**Tech Stack:** Python 3.13, argparse, subprocess, fcntl, urllib, uv, hatchling, unittest, GitHub Actions, PyPI Trusted Publishing

## Global Constraints

- Public CLI commands are exactly `start` and `stop`.
- `start` launches a background process and subsumes preparation, status, configuration, and health waiting.
- Runtime defaults preserve MPS for PyTorch-backed Docling stages and Apple Vision accurate OCR with `zh-Hans,en-US`.
- Bind to `127.0.0.1:5001`; keep remote services and external plugins disabled.
- Do not modify DLightRAG or LightRAG.
- Do not add API tokens, passwords, AI attribution, or co-author trailers.
- Version `0.1.0` is published from public repository `hanlianlu/docling-serve-mps` on `main`.

---

### Task 1: Build The Minimal Lifecycle CLI

**Files:**
- Create: `src/docling_serve_mps/__init__.py`
- Create: `src/docling_serve_mps/cli.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Console entry point: `docling-serve-mps = docling_serve_mps.cli:main`
- Public commands: `main(["start"])`, `main(["stop"])`
- Internal state override for tests/operators: `DOCLING_SERVE_MPS_STATE_DIR`

- [ ] Write failing tests for two-command parsing, default child environment, unsupported platform rejection, idempotent start, stale PID cleanup, unrelated PID refusal on stop, and graceful stop.
- [ ] Run `uv run python -m unittest tests/test_cli.py -v`; verify failures are caused by the missing package.
- [ ] Implement the minimal CLI with standard-library process/file/HTTP APIs, a lifecycle lock, atomic JSON PID records, process identity checking through `ps`, background `python -m docling_serve run`, and bounded health/termination waits.
- [ ] Run the focused tests and editor diagnostics until clean.
- [ ] Commit with message `Add minimal background service CLI`.

### Task 2: Package And Delegate

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `.gitignore`
- Modify: `service.sh`
- Modify: `service.env`
- Modify: `tests/test_service.sh`
- Create: `tests/test_dist.py`

**Interfaces:**
- Build backend: hatchling with `src/docling_serve_mps` wheel package.
- Source wrapper: `./service.sh start|stop` only; it delegates to `.venv/bin/docling-serve-mps`.

- [ ] Write failing shell assertions that only `start|stop` are accepted and both delegate to the packaged CLI after a locked-environment check.
- [ ] Write a failing distribution test requiring Python modules and `entry_points.txt` in the wheel.
- [ ] Add explicit build metadata, console script, macOS classifiers, build ignores, and source-wrapper delegation; remove duplicated runtime defaults from `service.env` except documented environment overrides.
- [ ] Run `uv lock`, lifecycle/unit tests, `uv build`, distribution tests, and `uvx twine check dist/*`.
- [ ] Install the wheel into isolated `UV_TOOL_DIR`/`UV_TOOL_BIN_DIR`; verify `docling-serve-mps --help` exposes only `start` and `stop`.
- [ ] Commit with message `Package the Docling Serve MPS CLI`.

### Task 3: Documentation And Live Wheel Smoke

**Files:**
- Modify: `README.md`
- Create: `CHANGELOG.md`

**Interfaces:**
- Canonical PyPI install: `uv tool install docling-serve-mps`.
- Canonical lifecycle: `docling-serve-mps start|stop`.

- [ ] Update README to distinguish PyPI installation from source checkout and remove public prepare/status/logs/run instructions.
- [ ] Add concise 0.1.0 changelog.
- [ ] Stop the current source service, install the built wheel into an isolated uv tool directory, start on an alternate loopback port/state directory, verify health/UI, then stop and verify PID cleanup.
- [ ] Restart the canonical source service and verify DLightRAG container connectivity.
- [ ] Run repository hygiene and all tests; commit with message `Document the PyPI service workflow`.

### Task 4: CI And Trusted Publishing

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/publish.yml`
- Modify: `README.md`

**Interfaces:**
- CI runs tests/build/metadata checks on pushes and pull requests.
- Publish runs only for a published GitHub release, validates `vX.Y.Z` against project version, and uses environment `pypi` with job-scoped `id-token: write`.

- [ ] Add CI using `actions/checkout@v4`, `astral-sh/setup-uv@v7`, locked sync, unittest, build, distribution checks, and twine check.
- [ ] Add release workflow using build artifact handoff and `pypa/gh-action-pypi-publish@release/v1` without secrets.
- [ ] Validate YAML, run the equivalent local commands, and add PyPI/CI badges and release instructions.
- [ ] Create GitHub environment `pypi`; commit and push main.
- [ ] Verify GitHub Actions CI succeeds; fix and rerun if needed.

### Task 5: Register And Publish 0.1.0

**Files:**
- No tracked changes expected after a green release candidate.

**Interfaces:**
- Pending publisher identity:
  - Project: `docling-serve-mps`
  - Owner: `hanlianlu`
  - Repository: `docling-serve-mps`
  - Workflow: `publish.yml`
  - Environment: `pypi`

- [ ] Register the pending publisher on PyPI. If authentication is required, the user enters credentials directly in the browser; never route secrets through chat.
- [ ] Reconfirm the PyPI name still returns 404, local/remote main match, worktree is clean, and all release gates pass.
- [ ] Create and push annotated tag `v0.1.0`, then publish a GitHub release from that tag.
- [ ] Watch the publish workflow to completion and inspect failed logs if it does not succeed.
- [ ] Verify `https://pypi.org/pypi/docling-serve-mps/json` reports version 0.1.0, project URLs and dependencies are correct, and both wheel and sdist are available.
- [ ] Fresh-install from PyPI into an isolated uv tool directory, verify the two-command help surface, run start/health/stop on an alternate port, and remove the temporary tool environment.
- [ ] Confirm `main == origin/main`, tag/release exist remotely, service health is restored, and no untracked artifacts remain.
