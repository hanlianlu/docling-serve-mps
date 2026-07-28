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
exit 0
EOF
  chmod +x "$test_root/.venv/bin/python" "$test_root/.venv/bin/docling-serve"
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
cat >"$ready_root/fake-bin/uv" <<'EOF'
#!/bin/zsh
print -r -- "$*" >>"$UV_LOG"
exit 99
EOF
chmod +x "$ready_root/fake-bin/uv"
write_ready_environment "$ready_root"
UV_LOG="$ready_uv_log" PATH="$ready_root/fake-bin:$PATH" \
  "$ready_root/service.sh" prepare
[[ ! -e "$ready_uv_log" ]] || {
  print -u2 "prepare invoked uv for an already complete environment"
  exit 1
}

missing_root=$(prepare_fixture missing)
missing_uv_log="$missing_root/uv.log"
cat >"$missing_root/fake-bin/uv" <<'EOF'
#!/bin/zsh
set -euo pipefail
print -r -- "$*" >>"$UV_LOG"
[[ "$#" -eq 2 && "$1" == "sync" && "$2" == "--locked" ]]
mkdir -p .venv/bin
cat >.venv/bin/python <<'PYTHON'
#!/bin/zsh
exit 0
PYTHON
cat >.venv/bin/docling-serve <<'SERVER'
#!/bin/zsh
exit 0
SERVER
chmod +x .venv/bin/python .venv/bin/docling-serve
EOF
chmod +x "$missing_root/fake-bin/uv"
UV_LOG="$missing_uv_log" PATH="$missing_root/fake-bin:$PATH" \
  "$missing_root/service.sh" prepare
[[ "$(<"$missing_uv_log")" == "sync --locked" ]] || {
  print -u2 "prepare did not invoke exactly: uv sync --locked"
  exit 1
}

print "service environment tests passed"