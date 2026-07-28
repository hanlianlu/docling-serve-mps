#!/bin/zsh
set -euo pipefail

ROOT=${0:A:h:h}
TMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/docling-service-test.XXXXXX")
trap 'rm -rf "$TMP_ROOT"' EXIT

write_ready_environment() {
  local test_root=$1
  mkdir -p "$test_root/.venv/bin"
  cat >"$test_root/.venv/bin/python" <<'EOF'
#!/bin/zsh
exit 0
EOF
  cat >"$test_root/.venv/bin/docling-serve" <<'EOF'
#!/bin/zsh
print -r -- "$*" >>"$LEGACY_LOG"
exit 0
EOF
  cat >"$test_root/.venv/bin/docling-serve-mps" <<'EOF'
#!/bin/zsh
print -r -- "$*" >>"$CLI_LOG"
EOF
  chmod +x "$test_root/.venv/bin/python" \
    "$test_root/.venv/bin/docling-serve" \
    "$test_root/.venv/bin/docling-serve-mps"
}

prepare_fixture() {
  local name=$1
  local test_root="$TMP_ROOT/$name"
  mkdir -p "$test_root/fake-bin"
  cp "$ROOT/service.sh" "$ROOT/service.env" "$test_root/"
  print -r -- "$test_root"
}

ready_root=$(prepare_fixture ready)
ready_uv_log="$ready_root/uv.log"
ready_cli_log="$ready_root/cli.log"
ready_legacy_log="$ready_root/legacy.log"
: >"$ready_uv_log"
: >"$ready_cli_log"
: >"$ready_legacy_log"
cat >"$ready_root/fake-bin/uv" <<'EOF'
#!/bin/zsh
set -euo pipefail
print -r -- "$*" >>"$UV_LOG"
[[ "$#" -eq 3 && "$1" == "sync" && "$2" == "--locked" && "$3" == "--check" ]]
EOF
chmod +x "$ready_root/fake-bin/uv"
write_ready_environment "$ready_root"
UV_LOG="$ready_uv_log" CLI_LOG="$ready_cli_log" LEGACY_LOG="$ready_legacy_log" \
  PATH="$ready_root/fake-bin:$PATH" "$ready_root/service.sh" start
UV_LOG="$ready_uv_log" CLI_LOG="$ready_cli_log" LEGACY_LOG="$ready_legacy_log" \
  PATH="$ready_root/fake-bin:$PATH" "$ready_root/service.sh" stop
[[ "$(<"$ready_cli_log")" == $'start\nstop' ]] || {
  print -u2 "start and stop were not delegated to docling-serve-mps"
  exit 1
}
[[ "$(<"$ready_uv_log")" == $'sync --locked --check\nsync --locked --check' ]] || {
  print -u2 "delegation did not verify the locked environment"
  exit 1
}
[[ ! -s "$ready_legacy_log" ]] || {
  print -u2 "wrapper launched Docling Serve directly instead of using the CLI"
  exit 1
}

missing_root=$(prepare_fixture missing)
missing_uv_log="$missing_root/uv.log"
missing_cli_log="$missing_root/cli.log"
: >"$missing_uv_log"
: >"$missing_cli_log"
cat >"$missing_root/fake-bin/uv" <<'EOF'
#!/bin/zsh
set -euo pipefail
print -r -- "$*" >>"$UV_LOG"
if [[ "$#" -eq 3 && "$1" == "sync" && "$2" == "--locked" && "$3" == "--check" ]]; then
  [[ -x .venv/bin/docling-serve-mps ]]
  exit
fi
[[ "$#" -eq 2 && "$1" == "sync" && "$2" == "--locked" ]]
mkdir -p .venv/bin
cat >.venv/bin/docling-serve-mps <<'CLI'
#!/bin/zsh
print -r -- "$*" >>"$CLI_LOG"
CLI
chmod +x .venv/bin/docling-serve-mps
EOF
chmod +x "$missing_root/fake-bin/uv"
UV_LOG="$missing_uv_log" CLI_LOG="$missing_cli_log" \
  PATH="$missing_root/fake-bin:$PATH" "$missing_root/service.sh" start
[[ "$(<"$missing_uv_log")" == $'sync --locked\nsync --locked --check' ]] || {
  print -u2 "start did not repair and verify the locked environment"
  exit 1
}
[[ "$(<"$missing_cli_log")" == "start" ]] || {
  print -u2 "start was not delegated after environment repair"
  exit 1
}

for unsupported_command in prepare status logs run ''; do
  arguments=()
  [[ -n "$unsupported_command" ]] && arguments=("$unsupported_command")
  set +e
  UV_LOG="$ready_uv_log" CLI_LOG="$ready_cli_log" LEGACY_LOG="$ready_legacy_log" \
    PATH="$ready_root/fake-bin:$PATH" \
    "$ready_root/service.sh" "${arguments[@]}" >/dev/null 2>&1
  exit_code=$?
  set -e
  if [[ "$exit_code" -ne 2 ]]; then
    print -u2 "unsupported command '${unsupported_command:-<empty>}' returned $exit_code"
    exit 1
  fi
done

print "service wrapper tests passed"