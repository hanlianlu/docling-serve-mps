# PyPI Release Design

## Goal

Publish `docling-serve-mps` as a useful macOS application package rather than a
metadata-only dependency bundle. A user installs it with uv and manages the
background sidecar through two commands:

```bash
uv tool install docling-serve-mps
docling-serve-mps start
docling-serve-mps stop
```

## Public CLI

Only `start` and `stop` are public.

`start` owns the complete startup intent:

1. Reject unsupported hosts with a clear macOS/Apple Silicon error.
2. Verify Docling Serve, OCRMac, and PyTorch MPS are available.
3. Apply the package's M4 Max, loopback, security, UI, and bilingual OCR
   defaults while honoring explicit environment overrides.
4. Detect an existing managed process. If healthy, report it and exit
   successfully; if still starting, wait for health instead of launching a
   duplicate.
5. Remove stale state, launch Docling Serve in the background, and wait for its
   health endpoint.
6. Print the API URL, UI URL, PID, and log path.

`stop` sends `SIGTERM` to the managed process, waits for it to exit, and removes
stale state. It must not kill an unrelated process after PID reuse.

There is no public `prepare`, `run`, `status`, or `logs` command. Installation
is the package manager's job; startup subsumes preparation and status; logs are
read from the path printed by `start`.

## Runtime Ownership

The wheel contains a real `docling_serve_mps` Python package and one console
entry point. Runtime state lives under the macOS user application-support
directory, not the tool environment:

```text
~/Library/Application Support/docling-serve-mps/
  docling-serve.pid
  docling-serve.log
  scratch/
  lifecycle.lock
```

The PID record includes the process ID and expected command identity. Before
signaling a recorded PID, the CLI verifies that the live command still belongs
to Docling Serve.

The child process uses the same Python executable as the installed CLI:

```text
python -m docling_serve run --host ... --port ... --workers ...
```

This avoids relying on PATH lookup inside isolated uv tool environments.

## Defaults And Overrides

The Python package owns the defaults currently documented in `service.env`,
including:

- PyTorch-backed Docling stages on MPS with CPU fallback.
- Apple Vision accurate OCR with `zh-Hans,en-US`.
- One local converter worker and one Uvicorn worker.
- Eight CPU threads.
- Loopback `127.0.0.1:5001`.
- Local UI enabled.
- Remote services and external plugins disabled.

Existing environment variable names remain valid overrides. The package does
not accept a second configuration format in the first release.

## Source Checkout Compatibility

`service.sh` remains for clone-based use, but no longer owns background process
logic. It checks/synchronizes the locked `.venv` when necessary, then delegates
`start` or `stop` to `.venv/bin/docling-serve-mps`. This keeps one lifecycle
implementation.

## Packaging

Use a `src/` package layout and an explicit build backend. The wheel must
contain the Python modules and console entry point; the source distribution must
also contain the README, license, tests, service wrapper, and lockfile.

Metadata declares the package as macOS-oriented, Python 3.13+, MIT licensed,
and links to the public repository, issues, and changelog/release page. Version
`0.1.0` is the first release.

## Testing

Tests cover:

- Platform validation and default environment construction.
- `start` idempotency, stale PID handling, health waiting, and process identity.
- `stop` graceful termination and refusal to signal unrelated processes.
- `service.sh` locked-environment synchronization and CLI delegation.
- Wheel metadata, console entry point, and non-empty package contents.
- Installation into an isolated uv tool directory.
- A live start/health/stop smoke test from the built wheel on macOS.

The existing bilingual OCR HTTP smoke remains the runtime evidence for the
Docling configuration.

## Publishing

Use GitHub Actions and PyPI Trusted Publishing, without stored API tokens. The
workflow builds and validates distributions, uploads them as a workflow
artifact, and publishes only for a GitHub release whose `vX.Y.Z` tag matches
the package version. The publishing job uses the `pypi` GitHub environment and
job-scoped `id-token: write` permission.

For the pending PyPI publisher, register exactly:

```text
PyPI project: docling-serve-mps
GitHub owner: hanlianlu
Repository: docling-serve-mps
Workflow: publish.yml
Environment: pypi
```

After the workflow publishes `0.1.0`, verify PyPI JSON metadata, wheel contents,
Trusted Publisher status, and a fresh `uv tool install docling-serve-mps`.

## Non-Goals

- No DLightRAG or LightRAG changes.
- No foreground/debug public command.
- No launchd installer in the PyPI package.
- No TestPyPI project unless main PyPI Trusted Publishing cannot be configured.
- No API token, password, or other credential stored in GitHub.