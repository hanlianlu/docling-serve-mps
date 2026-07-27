# Docling Serve for Apple Silicon

An independent, uv-managed Docling Serve installation tuned for Apple Silicon.
It runs Docling natively on macOS so PyTorch can use Metal Performance Shaders
(MPS), while Dockerized clients connect through `host.docker.internal`.

## Runtime

- Python 3.13 managed by uv
- Native PyTorch MPS with CPU fallback for unsupported operators
- One converter worker to avoid duplicated model memory and MPS contention
- Eight CPU threads for pipeline stages that remain CPU-bound
- Loopback-only listener on port 5001
- Models loaded at startup and cached by Docling/Hugging Face
- Local Docling UI enabled on the same loopback-only service
- External plugins and remote model services disabled

## Requirements

- Apple Silicon Mac
- macOS with PyTorch MPS support
- [uv](https://docs.astral.sh/uv/)

## Install

```bash
git clone https://github.com/hanlianlu/docling-serve-mps.git
cd docling-serve-mps
uv sync
```

Verify MPS before starting the service:

```bash
uv run python -c 'import torch; print(torch.backends.mps.is_available())'
```

The result should be `True`.

## Common Workflow

Start the service in the background:

```bash
cd ~/Github/docling-serve-mps
./service.sh start
```

Check the process and HTTP health endpoint:

```bash
./service.sh status
```

Follow the service log:

```bash
./service.sh logs
```

Press `Ctrl+C` to stop following the log. This does not stop Docling Serve.

Stop the background service:

```bash
./service.sh stop
```

Restart after changing `service.env`:

```bash
./service.sh stop
./service.sh start
./service.sh status
```

The service does not start automatically after a macOS reboot. Run
`./service.sh start` when needed.

Open the local Docling UI after the health check passes:

```text
http://127.0.0.1:5001/ui
```

The UI is not separately authenticated, so the service remains bound to
`127.0.0.1`. Do not change `DOCLING_HOST` to `0.0.0.0` unless an authenticated
reverse proxy protects the service.

## Files

```text
service.env                  Runtime tuning
service.sh                   start/stop/status/logs controller
run/docling-serve.pid        Background process ID
run/docling-serve.log        Persistent service log
run/scratch/                 Docling Serve temporary results
```

`run/` and `.venv/` are ignored by Git.

## DLightRAG Integration

For Dockerized DLightRAG, configure Docling as an external endpoint:

```yaml
parser_sidecars:
  docling:
    endpoint: http://host.docker.internal:5001
```

Remove or comment out the active MinerU block. If both MinerU and Docling are
configured, DLightRAG prioritizes MinerU.

Start DLightRAG normally:

```bash
docker compose up -d
```

Do not enable DLightRAG's CPU Docling Compose profile at the same time. This
native service already owns port 5001 and uses MPS.

Verify connectivity from the DLightRAG container:

```bash
docker compose exec -T dlightrag-api python -c \
  "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:5001/health').read().decode())"
```

## Tuning

The defaults in `service.env` target an M4 Max with 48 GB unified memory while
leaving capacity for DLightRAG and macOS:

```dotenv
DOCLING_DEVICE=mps
PYTORCH_ENABLE_MPS_FALLBACK=1
DOCLING_NUM_THREADS=8
DOCLING_SERVE_ENG_LOC_NUM_WORKERS=1
DOCLING_SERVE_OPTIONS_CACHE_SIZE=2
DOCLING_SERVE_ENABLE_UI=true
```

Keep one converter worker unless benchmarks show a benefit from concurrency.
Multiple workers can duplicate model memory and contend for the same MPS device.

## Upgrade

Stop the service, update dependencies with uv, and restart:

```bash
./service.sh stop
uv lock --upgrade-package docling-serve
uv sync
./service.sh start
./service.sh status
```

The lockfile keeps installations reproducible until an explicit upgrade.

## Troubleshooting

Check health directly:

```bash
curl http://127.0.0.1:5001/health
```

Confirm the runtime selected MPS:

```bash
grep "Accelerator device" run/docling-serve.log | tail
```

Check whether another process owns port 5001:

```bash
lsof -nP -iTCP:5001 -sTCP:LISTEN
```

Initial startup can take longer while model artifacts are downloaded and
loaded. `./service.sh status` may report that the process is alive but health is
not ready during this period; follow `./service.sh logs` for progress.

## License

MIT License. Copyright (c) 2026 Hanlian Lyu. See [LICENSE](LICENSE).