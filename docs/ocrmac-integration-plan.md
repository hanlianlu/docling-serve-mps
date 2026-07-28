# OCRMac Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the standalone Docling Serve service transparently use Apple Vision OCR in accurate Chinese-English mode and install OCRMac automatically from the locked project environment.

**Architecture:** Keep the LightRAG request contract unchanged and override Docling Serve's built-in `auto` OCR preset through its official `custom_ocr_presets` setting. Declare OCRMac through Docling's official feature extra, and make `service.sh start` repair a missing or incomplete `.venv` with `uv sync --locked` before launching the service.

**Tech Stack:** zsh, uv, PEP 621, Docling Serve 1.28, Docling 2.115, OCRMac 1.x, Apple Vision, Python unittest

## Global Constraints

- Modify only `/Users/hanlianlyu/Github/docling-serve-mps`; DLightRAG and LightRAG remain unchanged.
- Preserve LightRAG's `ocr_preset=auto` and `force_ocr=true` request behavior.
- Resolve `auto` to OCRMac with `framework=vision`, `recognition=accurate`, and languages ordered `zh-Hans,en-US`.
- Do not use Live Text, request rewriting, monkey patches, fallback engines, remote services, or external plugins.
- Existing processed documents and caches are not migrated or reprocessed.
- Use uv only; do not use pip.
- Final state must be committed on `main`, pushed to `origin/main`, and leave a clean worktree.
- Commit and repository text must contain no AI attribution or co-author trailer.

---

### Task 1: Lock Automatic OCRMac Setup

**Files:**
- Create: `tests/test_service.sh`
- Modify: `service.sh`
- Modify: `pyproject.toml`
- Modify: `uv.lock`

**Interfaces:**
- Consumes: `service.sh start|stop|status|logs`, project-local `.venv`, and `uv.lock`.
- Produces: `service.sh prepare`, `environment_ready() -> shell status`, and `ensure_environment() -> shell status`; `start` calls `ensure_environment` before launching.

- [ ] **Step 1: Write the failing shell test**

Create `tests/test_service.sh` with two isolated copies of `service.sh` and `service.env` under a temporary directory. In the first copy, provide executable fake `.venv/bin/python` and `.venv/bin/docling-serve`; assert `./service.sh prepare` succeeds without invoking a fake `uv`. In the second copy, omit `.venv`, provide a fake `uv` that accepts only `sync --locked`, records its arguments, creates both executables, and assert `./service.sh prepare` invokes exactly `sync --locked` and then succeeds.

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
zsh tests/test_service.sh
```

Expected: FAIL because `service.sh` has no `prepare` action and does not repair the environment.

- [ ] **Step 3: Implement locked environment repair**

Add these responsibilities to `service.sh`:

```zsh
PYTHON_BIN="$ROOT/.venv/bin/python"
SERVER_BIN="$ROOT/.venv/bin/docling-serve"

environment_ready() {
  [[ -x "$PYTHON_BIN" && -x "$SERVER_BIN" ]] || return 1
  "$PYTHON_BIN" -c 'import docling_serve, ocrmac' >/dev/null 2>&1
}

ensure_environment() {
  environment_ready && return 0
  command -v uv >/dev/null 2>&1 || {
    print -u2 "uv is required to create the locked service environment."
    return 1
  }
  (cd "$ROOT" && uv sync --locked)
  environment_ready || {
    print -u2 "Locked environment is missing Docling Serve or OCRMac after sync."
    return 1
  }
}
```

Call `ensure_environment` at the start of `start_service`, add `prepare) ensure_environment ;;`, and update usage to `start|stop|status|logs|prepare`. Declare the OCRMac feature through the existing dependency set:

```toml
"docling-slim[feat-ocr-mac]>=2.115.0",
```

Run `uv lock` to update the lockfile.

- [ ] **Step 4: Run focused validation**

Run:

```bash
zsh tests/test_service.sh
zsh -n service.sh
uv lock --check
uv sync --locked
uv run python -c 'import docling_serve, ocrmac; print("ocrmac-ready")'
```

Expected: both setup scenarios pass, shell syntax is valid, the lock is current, and OCRMac imports from the project environment.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock service.sh tests/test_service.sh
git commit -m "Add automatic OCRMac environment setup"
```

### Task 2: Override Docling Auto OCR Preset

**Files:**
- Create: `tests/test_ocr_config.py`
- Modify: `service.env`

**Interfaces:**
- Consumes: Docling Serve setting `DOCLING_SERVE_CUSTOM_OCR_PRESETS` and LightRAG-equivalent `ConvertDocumentsOptions(ocr_preset="auto", force_ocr=True)`.
- Produces: `auto` registry entry backed by `OcrMacOptions` with Vision accurate, `zh-Hans,en-US`, and full-page OCR retained from the request.

- [ ] **Step 1: Write the failing unittest**

Create `tests/test_ocr_config.py` using `unittest`. Construct `DoclingConverterManager` from `docling_serve.orchestrator_factory._build_cm_config()`, assert `manager.ocr_preset_registry["auto"]` is custom, then resolve:

```python
request = ConvertDocumentsOptions(ocr_preset="auto", force_ocr=True)
options = manager._parse_ocr_options(request)
```

Assert:

```python
isinstance(options, OcrMacOptions)
options.framework == "vision"
options.recognition == "accurate"
options.lang == ["zh-Hans", "en-US"]
options.force_full_page_ocr is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
set -a; source service.env; set +a
uv run python -m unittest tests/test_ocr_config.py -v
```

Expected: FAIL because the `auto` registry entry still uses Docling's built-in automatic engine.

- [ ] **Step 3: Configure the official custom preset**

Add one shell-safe JSON value to `service.env`:

```dotenv
DOCLING_SERVE_CUSTOM_OCR_PRESETS='{"auto":{"kind":"ocrmac","framework":"vision","recognition":"accurate","lang":["zh-Hans","en-US"]}}'
```

Do not enable custom request config, remote services, or external plugins.

- [ ] **Step 4: Run focused validation**

Run:

```bash
set -a; source service.env; set +a
uv run python -m unittest tests/test_ocr_config.py -v
```

Expected: PASS; the request's `force_ocr=True` survives preset resolution.

- [ ] **Step 5: Commit**

```bash
git add service.env tests/test_ocr_config.py
git commit -m "Configure Chinese English OCRMac preset"
```

### Task 3: Document Zero-Manual Setup

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: `./service.sh prepare` and automatic preparation from `./service.sh start`.
- Produces: one canonical install/start workflow and an explicit effective OCR contract.

- [ ] **Step 1: Update installation and operations documentation**

Document that `./service.sh start` performs `uv sync --locked` only when `.venv` is missing or lacks Docling Serve/OCRMac; `./service.sh prepare` performs the same check without starting. State that the service maps incoming `ocr_preset=auto` to Apple Vision accurate with `zh-Hans,en-US`, preserves caller `force_ocr`, and affects only future Docling parsing.

- [ ] **Step 2: Validate documentation and repository hygiene**

Run:

```bash
git diff --check
! rg -n 'pip install|TBD|TODO|claude|copilot|chatgpt|generated by|co-authored-by' README.md docs service.sh tests pyproject.toml --glob '!docs/ocrmac-integration-plan.md'
zsh tests/test_service.sh
set -a; source service.env; set +a
uv run python -m unittest tests/test_ocr_config.py -v
```

Expected: no stale manual OCRMac command, placeholders, AI attribution, or test failure.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Document automatic OCRMac workflow"
```

### Task 4: Validate the Live Service End to End

**Files:**
- No tracked file changes expected.

**Interfaces:**
- Consumes: `service.sh`, Docling Serve async HTTP API, and the same multipart fields LightRAG sends.
- Produces: runtime evidence that OCRMac handles Chinese-English full-page OCR and the service remains secure and reachable.

- [ ] **Step 1: Restart and verify service endpoints**

Run:

```bash
./service.sh stop
./service.sh start
./service.sh status
curl --fail --silent --output /dev/null --write-out '%{http_code}\n' http://127.0.0.1:5001/ui/
```

Expected: health JSON is `{"status":"ok"}` and UI returns HTTP 200.

- [ ] **Step 2: Generate a bilingual image PDF outside the repository**

Use Pillow from the locked environment and a macOS font supporting Chinese to render a clean image containing both `中文光学字符识别` and `English optical character recognition`, then save it as a one-page PDF under `$TMPDIR`.

- [ ] **Step 3: Submit the LightRAG-equivalent async conversion**

POST the PDF to `/v1/convert/file/async` with:

```text
pipeline=standard
target_type=zip
image_export_mode=referenced
do_ocr=true
force_ocr=true
ocr_engine=auto
ocr_preset=auto
do_formula_enrichment=false
to_formats=json
to_formats=md
```

Poll `/v1/status/poll/{task_id}?wait=5`, download `/v1/result/{task_id}`, and extract under `$TMPDIR`.

- [ ] **Step 4: Verify output and runtime selection**

Assert JSON or Markdown contains recognizable Chinese and English text. Check the service log for OCRMac selection and ensure no RapidOCR selection appears for this conversion. Verify DLightRAG container connectivity remains healthy:

```bash
docker compose exec -T dlightrag-api python -c 'import urllib.request; print(urllib.request.urlopen("http://host.docker.internal:5001/health").read().decode())'
```

Expected: conversion succeeds, both scripts are present, and the container receives `{"status":"ok"}`.

- [ ] **Step 5: Run final gate**

Run:

```bash
zsh tests/test_service.sh
set -a; source service.env; set +a
uv run python -m unittest discover -s tests -v
zsh -n service.sh
uv lock --check
uv sync --locked
git diff --check
! rg -n 'claude|copilot|chatgpt|generated by|co-authored-by' --glob '!.git/**' --glob '!.venv/**' --glob '!run/**' --glob '!docs/ocrmac-integration-plan.md' .
./service.sh status
```

Expected: all commands exit zero and the service is healthy.

- [ ] **Step 6: Commit any validation-only tracked correction**

If validation required no tracked correction, do not create an empty commit. If a focused correction was required, commit only that correction with a plain descriptive message and rerun Step 5.

### Task 5: Publish Main

**Files:**
- No content changes expected.

**Interfaces:**
- Consumes: clean verified local `main`.
- Produces: synchronized public `origin/main` with no extra branches or worktrees.

- [ ] **Step 1: Verify publication state**

```bash
git status --short --branch
git branch --show-current
git --no-pager log --oneline origin/main..HEAD
```

Expected: branch is `main`; only the reviewed OCRMac commits are ahead; worktree is clean.

- [ ] **Step 2: Push main**

```bash
git push origin main
```

- [ ] **Step 3: Verify remote and service**

```bash
git fetch origin main
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
git status --short --branch
gh repo view hanlianlu/docling-serve-mps --json url,visibility,defaultBranchRef
./service.sh status
```

Expected: local and remote HEAD match, the repository is PUBLIC with default branch `main`, the worktree is clean, and Docling Serve remains healthy.
