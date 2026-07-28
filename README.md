# Docling Serve for Apple Silicon

[![PyPI](https://img.shields.io/pypi/v/docling-serve-mps.svg)](https://pypi.org/project/docling-serve-mps/)
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

Upgrade the installed application, then restart it:

```bash
docling-serve-mps stop
uv tool upgrade docling-serve-mps
docling-serve-mps start
```

For a source checkout, explicitly update and review the lockfile before
restarting:

```bash
./service.sh stop
uv lock --upgrade-package docling-serve \
  --upgrade-package docling-slim \
  --upgrade-package ocrmac
./service.sh start
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