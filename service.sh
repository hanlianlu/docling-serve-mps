#!/bin/zsh
set -euo pipefail

ROOT=${0:A:h}
ENV_FILE="$ROOT/service.env"
RUN_DIR="$ROOT/run"
PID_FILE="$RUN_DIR/docling-serve.pid"
LOG_FILE="$RUN_DIR/docling-serve.log"
SCRATCH_DIR="$RUN_DIR/scratch"
PYTHON_BIN="$ROOT/.venv/bin/python"
SERVER_BIN="$ROOT/.venv/bin/docling-serve"

set -a
source "$ENV_FILE"
set +a

mkdir -p "$RUN_DIR" "$SCRATCH_DIR"
export DOCLING_SERVE_SCRATCH_PATH="$SCRATCH_DIR"

environment_ready() {
  [[ -x "$PYTHON_BIN" && -x "$SERVER_BIN" ]] || return 1
  command -v uv >/dev/null 2>&1 || return 1
  (cd "$ROOT" && uv sync --locked --check >/dev/null 2>&1) || return 1
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

running_pid() {
  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid=$(<"$PID_FILE")
    if kill -0 "$pid" 2>/dev/null; then
      print -r -- "$pid"
      return 0
    fi
    rm -f "$PID_FILE"
  fi
  return 1
}

start_service() {
  local pid
  if pid=$(running_pid); then
    print "Docling Serve is already running (PID $pid)."
    return 0
  fi

  ensure_environment
  cd "$ROOT"
  nohup "$SERVER_BIN" run \
    --host "$DOCLING_HOST" \
    --port "$DOCLING_PORT" \
    --workers "$UVICORN_WORKERS" \
    </dev/null >>"$LOG_FILE" 2>&1 &
  pid=$!
  print -r -- "$pid" >"$PID_FILE"
  print "Started Docling Serve in background (PID $pid)."
  print "Health: http://$DOCLING_HOST:$DOCLING_PORT/health"
  print "Log: $LOG_FILE"
}

stop_service() {
  local pid
  if ! pid=$(running_pid); then
    print "Docling Serve is not running."
    return 0
  fi
  kill "$pid"
  rm -f "$PID_FILE"
  print "Sent SIGTERM to Docling Serve (PID $pid)."
}

status_service() {
  local pid
  if ! pid=$(running_pid); then
    print "Docling Serve is not running."
    return 1
  fi
  print "Docling Serve is running (PID $pid)."
  if curl --fail --silent "http://$DOCLING_HOST:$DOCLING_PORT/health"; then
    print
  else
    print "Process is alive but the health endpoint is not ready."
    return 1
  fi
}

case "${1:-}" in
  start) start_service ;;
  prepare) ensure_environment ;;
  stop) stop_service ;;
  status) status_service ;;
  logs) exec tail -f "$LOG_FILE" ;;
  *)
    print "Usage: $0 {prepare|start|stop|status|logs}"
    exit 2
    ;;
esac