# Docling Serve for Apple Silicon

[![PyPI](https://img.shields.io/pypi/v/docling-serve-mps.svg?cacheSeconds=300)](https://pypi.org/project/docling-serve-mps/)
[![CI](https://github.com/hanlianlu/docling-serve-mps/actions/workflows/ci.yml/badge.svg)](https://github.com/hanlianlu/docling-serve-mps/actions/workflows/ci.yml)

A native, background Docling Serve sidecar for Apple Silicon. PyTorch-backed
Docling pipeline stages use Metal Performance Shaders (MPS), OCR uses Apple's
Vision framework through OCRMac, and Dockerized clients connect through
`host.docker.internal`.

## Runtime

- PyTorch-backed Docling stages use MPS with CPU fallback for unsupported operators
- OCRMac uses Apple Vision directly; it does not run through PyTorch or MPS
- Native accurate OCR for Simplified Chinese with English companion recognition
- One converter worker to avoid duplicated model memory and MPS contention
- Eight CPU threads for pipeline stages that remain CPU-bound
- Loopback-only API and UI on port 5001
- Remote model services and external plugins disabled

## Requirements

- Apple Silicon Mac
- macOS with PyTorch MPS support
- [uv](https://docs.astral.sh/uv/)

## Install

Install the application from PyPI:

```bash
uv tool install docling-serve-mps
```

Start the background sidecar:

```bash
docling-serve-mps start
```

`start` validates Apple Silicon and MPS support, starts Docling Serve when
needed, waits for the health endpoint, and prints the API, UI, and log
locations. Repeating it is safe and reports the existing managed process.

Open the local UI at:

```text
http://127.0.0.1:5001/ui/
```

Stop the sidecar:

```bash
docling-serve-mps stop
```

The service does not start automatically after a macOS reboot. Run `start`
when needed.

## Source Checkout

For development or locked source deployment:

```bash
git clone https://github.com/hanlianlu/docling-serve-mps.git
cd docling-serve-mps
./service.sh start
```

The wrapper checks `.venv` against `uv.lock`, repairs it with
`uv sync --locked` only when necessary, and delegates to the same packaged
CLI. Its accepted commands are also exactly `start` and `stop`:

```bash
./service.sh stop
```

For a supervised deployment, `unit.sh` manages the launchd unit instead — see
[Process supervisors](#process-supervisors).

## Process supervisors

`start` daemonizes, so it does not fit launchd — a supervisor wants the service
in the foreground and owns its lifecycle itself. Use `run`:

```bash
docling-serve-mps run
```

`run` applies the same packaged defaults and execs Docling Serve in place. It
takes no lifecycle lock and writes no pid record, so `stop` is not the way to
stop a supervised service (the supervisor would restart it) — unload the unit
instead.

### launchd (macOS)

The package targets Apple Silicon, and `run` is the command its supervisor uses,
so launchd is the only supervisor this repository ships a unit for. The unit
lives in `launchd/com.orliantra.docling-mps.plist.template` and `unit.sh`
manages it, rendering that template against this checkout, validating the
result, and loading it. Logs land in `~/Library/Logs/docling-serve-mps/`.

```bash
./unit.sh install     # render, install, and load; RunAtLoad starts it now
./unit.sh status      # state, pid, run count, last exit code
./unit.sh restart     # make the running service pick up the code on disk
./unit.sh uninstall   # unload and remove the unit
```

The unit execs this checkout's own `.venv`, so it belongs to the source-checkout
path. `install` reconciles the installed unit with the template: when the
rendered unit already matches and the job is loaded, it leaves the running
service alone, because restarting a healthy service to reinstall an identical
definition is pure downtime. It reloads only when the definition changed, and
then it waits for the old job to unload, confirms the new one is running, and
rolls back to the previous unit if launchd refuses it.

`unit.sh` manages that unit *file* — not the service. `launchd` runs the
service, exactly as it would for any other job. In the unsupervised shape the
equivalent control is `service.env`, which `service.sh` reads. `service.sh` keeps
accepting exactly `start` and `stop` because the lifecycle it would manage
belongs to the supervisor here.

launchd starts a process from the code on disk and never re-reads it. `KeepAlive`
restarts a process that *exits*; it does not react to files changing underneath a
running one. After pulling new code, run `./unit.sh restart` — otherwise the
service keeps serving the old build until it happens to die.

## Configuration

The built-in defaults target an M4 Max with 48 GB unified memory while leaving
capacity for DLightRAG and macOS:

```dotenv
DOCLING_DEVICE=mps
PYTORCH_ENABLE_MPS_FALLBACK=1
DOCLING_NUM_THREADS=8
DOCLING_SERVE_ENG_LOC_NUM_WORKERS=1
DOCLING_SERVE_OPTIONS_CACHE_SIZE=2
DOCLING_HOST=127.0.0.1
DOCLING_PORT=5001
DOCLING_SERVE_ENABLE_UI=true
DOCLING_SERVE_ENABLE_REMOTE_SERVICES=false
DOCLING_SERVE_ALLOW_EXTERNAL_PLUGINS=false
DOCLINGCORE_MAX_IMAGE_DECODED_SIZE=67108864
DOCLING_SERVE_CUSTOM_OCR_PRESETS='{"auto":{"kind":"ocrmac","framework":"vision","recognition":"accurate","lang":["zh-Hans","en-US"]}}'
```

Set an environment variable before `start` to override a default. Source
checkouts can place overrides in `service.env`; installed tools can export
them in the calling shell. For example:

```bash
export DOCLING_PORT=5101
docling-serve-mps start
```

Use `DOCLING_SERVE_MPS_STATE_DIR` to override the state directory. The default
is:

```text
~/Library/Application Support/docling-serve-mps/
```

It contains the lifecycle lock, PID record, persistent log, and Docling scratch
directory. The PID record is atomic, and `stop` verifies process identity
before sending SIGTERM.

Keep the service on `127.0.0.1`. The UI is not separately authenticated, so do
not bind to `0.0.0.0` unless an authenticated reverse proxy protects it.

## OCR

The service replaces Docling Serve's built-in `auto` OCR preset through its
official custom preset registry. Clients can keep sending `ocr_preset=auto`;
the effective configuration is:

```text
engine: OCRMac
framework: Apple Vision
recognition: accurate
languages: zh-Hans, en-US
```

The language order prioritizes Simplified Chinese, with English as Apple's
supported companion language. The caller's `force_ocr` value remains
authoritative. LightRAG currently sends `force_ocr=true`, so its conversions
continue to use full-page OCR.

This service-side setting applies only when a document reaches Docling for a
new parse. It does not migrate or reprocess existing DLightRAG documents,
chunks, vectors, knowledge graphs, or parser caches.

## DLightRAG Integration

For Dockerized DLightRAG, configure Docling as an external endpoint:

```yaml
parser_sidecars:
  docling:
    endpoint: http://host.docker.internal:5001
```

Remove or comment out the active MinerU block. If both MinerU and Docling are
configured, DLightRAG prioritizes MinerU. Do not enable DLightRAG's CPU Docling
Compose profile at the same time because this native service already owns port
5001.

Verify connectivity from the DLightRAG container:

```bash
docker compose exec -T dlightrag-api python -c \
  "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:5001/health').read().decode())"
```

## Upgrade

Updating means two separate things, and only the second one changes what you
observe: **replace the code**, then **make the running process load it**. A
service holds its code in memory from start time, so nothing restarts it just
because files changed. How you do the second step depends on what supervises it.

### Supervised by launchd

```bash
cd /path/to/docling-serve-mps
git pull
uv sync --locked
./unit.sh restart
```

Use `uv lock --upgrade` instead of the plain sync when you intend to move the
pinned Docling Serve version, and review the lockfile diff before syncing:

```bash
uv lock --upgrade
uv sync --locked
./unit.sh restart
```

Skipping the restart is the common mistake: `./unit.sh status` will still report
`state = running`, because the old process never exited.

### Unsupervised source checkout

```bash
./service.sh stop
uv lock --upgrade
uv sync --locked
./service.sh start
```

### Unsupervised `uv tool` install

```bash
uv tool upgrade docling-serve-mps
```

The tool's own lifecycle commands still own it, so restart the same way you
started it:

```bash
docling-serve-mps stop
docling-serve-mps start
```

## Troubleshooting

Check health directly:

```bash
curl http://127.0.0.1:5001/health
```

Check whether another process owns port 5001:

```bash
lsof -nP -iTCP:5001 -sTCP:LISTEN
```

The `start` output prints the persistent log path. Initial startup can take
longer while model artifacts are downloaded and loaded. Docling logs the
selected accelerator as `mps`; OCRMac delegates recognition to Apple Vision
independently.

## Release

Maintainers publish by creating a GitHub Release whose tag exactly matches the
`pyproject.toml` version with a `v` prefix, for example `v0.1.0`. The release
workflow rebuilds and tests the artifacts, then publishes through PyPI Trusted
Publishing with GitHub OIDC. No PyPI API token is stored in GitHub.

## License

MIT License. Copyright (c) 2026 Hanlian Lyu. See [LICENSE](LICENSE).