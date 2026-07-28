#!/bin/zsh
set -euo pipefail

ROOT=${0:A:h}
ENV_FILE="$ROOT/service.env"
CLI_BIN="$ROOT/.venv/bin/docling-serve-mps"

set -a
source "$ENV_FILE"
set +a

environment_ready() {
  [[ -x "$CLI_BIN" ]] || return 1
  command -v uv >/dev/null 2>&1 || return 1
  (cd "$ROOT" && uv sync --locked --check >/dev/null 2>&1)
}

ensure_environment() {
  environment_ready && return 0
  command -v uv >/dev/null 2>&1 || {
    print -u2 "uv is required to create the locked service environment."
    return 1
  }
  (cd "$ROOT" && uv sync --locked)
  environment_ready || {
    print -u2 "Locked environment is missing docling-serve-mps after sync."
    return 1
  }
}

case "${1:-}" in
  start|stop) command=$1 ;;
  *)
    print "Usage: $0 {start|stop}"
    exit 2
    ;;
esac

ensure_environment
exec "$CLI_BIN" "$command"