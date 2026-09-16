#!/bin/zsh
set -euo pipefail

# Exercises the launchd unit manager without touching the real launchd session:
# PATH supplies a stateful recording launchctl, and HOME points at a temporary
# directory. The fake tracks loaded state in a marker file, so bootstrap,
# bootout, `print` and the manager's polling behave like the real tool's.

ROOT=${0:A:h:h}
TMP_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/docling-unit-test.XXXXXX")
trap 'rm -rf "$TMP_ROOT"' EXIT

LABEL=com.orliantra.docling-mps
DOMAIN="gui/$(id -u)"
# The manager polls launchd between teardown and load; the failure paths would
# otherwise wait out the real interval.
export DOCLING_SERVE_MPS_UNIT_POLL_SECONDS=0

prepare_fixture() {
  local name=$1
  local test_root="$TMP_ROOT/$name"
  mkdir -p "$test_root/fake-bin" "$test_root/launchd" "$test_root/home"
  cp "$ROOT/unit.sh" "$test_root/"
  cp "$ROOT/launchd/$LABEL.plist.template" "$test_root/launchd/"
  cat >"$test_root/fake-bin/launchctl" <<'EOF'
#!/bin/zsh
set -euo pipefail
print -r -- "$*" >>"$LAUNCHCTL_LOG"
case "$1" in
  bootstrap)
    # Models the teardown race that follows bootout, and a unit launchd refuses.
    if [[ "${FAKE_BOOTSTRAP_ALWAYS_FAIL:-0}" == "1" ]]; then
      print -u2 "Bootstrap failed: 5: Input/output error"
      exit 5
    fi
    if [[ -n "${FAKE_BOOTSTRAP_FAIL_TIMES:-}" ]]; then
      attempts=0
      [[ -f "$FAKE_COUNTER" ]] && attempts=$(<"$FAKE_COUNTER")
      if (( attempts < FAKE_BOOTSTRAP_FAIL_TIMES )); then
        print -r -- "$((attempts + 1))" >"$FAKE_COUNTER"
        print -u2 "Bootstrap failed: 5: Input/output error"
        exit 5
      fi
    fi
    : >"$FAKE_STATE"
    ;;
  bootout)
    rm -f "$FAKE_STATE"
    ;;
  print)
    [[ -f "$FAKE_STATE" ]] || exit 3
    print "\tstate = running"
    print "\tpid = 4242"
    print "\truns = 1"
    print "\tlast exit code = 0"
    # launchctl nests per-endpoint dictionaries, and their inner fields repeat
    # these names at a deeper indent.
    print "\t\tstate = active"
    ;;
esac
exit 0
EOF
  chmod +x "$test_root/fake-bin/launchctl"
  print -r -- "$test_root"
}

run_unit() {
  local test_root=$1 loaded=$2
  shift 2
  FAKE_STATE="$test_root/loaded.marker"
  if [[ "$loaded" == "1" ]]; then
    : >"$FAKE_STATE"
  else
    rm -f "$FAKE_STATE"
  fi
  HOME="$test_root/home" LAUNCHCTL_LOG="$test_root/launchctl.log" FAKE_STATE="$FAKE_STATE" \
    FAKE_BOOTSTRAP_FAIL_TIMES="${FAKE_BOOTSTRAP_FAIL_TIMES:-}" \
    FAKE_BOOTSTRAP_ALWAYS_FAIL="${FAKE_BOOTSTRAP_ALWAYS_FAIL:-0}" \
    FAKE_COUNTER="$test_root/bootstrap.count" \
    PATH="$test_root/fake-bin:$PATH" "$test_root/unit.sh" "$@"
}

# launchctl calls that change state; `print` is a read-only probe that every
# command may issue, and the fake records it like the real tool would.
mutations() {
  grep -v '^print ' "$1" || true
}

# --- install renders a valid unit and loads it ------------------------------
install_root=$(prepare_fixture install)
# unit.sh resolves its own location, so the fixture path is compared resolved:
# on macOS ${0:A} turns /var/folders into /private/var/folders.
resolved_root=${install_root:A}
: >"$install_root/launchctl.log"
run_unit "$install_root" 0 install >/dev/null

unit_path="$install_root/home/Library/LaunchAgents/$LABEL.plist"
[[ -f "$unit_path" ]] || {
  print -u2 "install did not write $unit_path"
  exit 1
}
plutil -lint "$unit_path" >/dev/null || {
  print -u2 "install wrote an invalid property list"
  exit 1
}
rendered=$(<"$unit_path")
[[ "$rendered" == *"$resolved_root/.venv/bin/docling-serve-mps"* ]] || {
  print -u2 "rendered unit does not point at the checkout CLI"
  exit 1
}
[[ "$rendered" == *"<string>$resolved_root</string>"* ]] || {
  print -u2 "rendered unit does not set WorkingDirectory to the checkout"
  exit 1
}
[[ "$rendered" != *"__"* ]] || {
  print -u2 "rendered unit still contains a template placeholder"
  exit 1
}
[[ "$(mutations "$install_root/launchctl.log")" == "$(print -r -- "bootout $DOMAIN/$LABEL
bootstrap $DOMAIN $unit_path")" ]] || {
  print -u2 "install did not boot out then bootstrap the unit"
  exit 1
}
[[ -f "$install_root/loaded.marker" ]] || {
  print -u2 "install did not leave the job loaded"
  exit 1
}

# --- reinstalling an unchanged unit must not disturb a running service ------
: >"$install_root/launchctl.log"
run_unit "$install_root" 1 install >/dev/null
[[ -z "$(mutations "$install_root/launchctl.log")" ]] || {
  print -u2 "install reloaded an unchanged unit and restarted a healthy service"
  exit 1
}

# --- restart reloads a loaded job, or loads an installed one ---------------
: >"$install_root/launchctl.log"
run_unit "$install_root" 1 restart >/dev/null
[[ "$(mutations "$install_root/launchctl.log")" == "kickstart -k $DOMAIN/$LABEL" ]] || {
  print -u2 "restart did not kickstart the loaded job"
  exit 1
}

: >"$install_root/launchctl.log"
run_unit "$install_root" 0 restart >/dev/null
[[ "$(mutations "$install_root/launchctl.log")" == "bootstrap $DOMAIN $unit_path" ]] || {
  print -u2 "restart did not load an installed but unloaded job"
  exit 1
}

# --- restart fails closed when nothing is installed ------------------------
unloaded_root=$(prepare_fixture unloaded)
set +e
run_unit "$unloaded_root" 0 restart >/dev/null 2>&1
restart_code=$?
set -e
[[ "$restart_code" -ne 0 ]] || {
  print -u2 "restart succeeded without an installed unit"
  exit 1
}

# --- status reports launchd facts, and fails when unloaded -----------------
set +e
status_output=$(run_unit "$install_root" 1 status)
status_code=$?
set -e
[[ "$status_code" -eq 0 ]] || {
  print -u2 "status failed on a loaded job"
  exit 1
}
[[ "$status_output" == *"state = running"* && "$status_output" == *"runs = 1"* ]] || {
  print -u2 "status did not report the launchd state: $status_output"
  exit 1
}
[[ "$status_output" != *"active"* ]] || {
  print -u2 "status reported a nested dictionary's inner state: $status_output"
  exit 1
}

set +e
run_unit "$install_root" 0 status >/dev/null 2>&1
status_unloaded_code=$?
set -e
[[ "$status_unloaded_code" -ne 0 ]] || {
  print -u2 "status succeeded on an unloaded job"
  exit 1
}

# --- a transient bootstrap failure is retried, not reported -----------------
retry_root=$(prepare_fixture retry)
: >"$retry_root/launchctl.log"
FAKE_BOOTSTRAP_FAIL_TIMES=2
FAKE_BOOTSTRAP_ALWAYS_FAIL=0
run_unit "$retry_root" 0 install >/dev/null
FAKE_BOOTSTRAP_FAIL_TIMES=
[[ "$(grep -c '^bootstrap ' "$retry_root/launchctl.log")" -eq 3 ]] || {
  print -u2 "install did not retry the transient bootstrap failure"
  exit 1
}
[[ -f "$retry_root/loaded.marker" ]] || {
  print -u2 "install did not leave the job loaded after retrying"
  exit 1
}

# --- a unit launchd keeps refusing restores the previous install ------------
rollback_root=$(prepare_fixture rollback)
rollback_unit="$rollback_root/home/Library/LaunchAgents/$LABEL.plist"
mkdir -p "${rollback_unit:h}"
print -r -- "previously installed unit" >"$rollback_unit"
: >"$rollback_root/launchctl.log"
FAKE_BOOTSTRAP_FAIL_TIMES=
FAKE_BOOTSTRAP_ALWAYS_FAIL=1
set +e
run_unit "$rollback_root" 0 install >/dev/null 2>&1
rollback_code=$?
set -e
FAKE_BOOTSTRAP_ALWAYS_FAIL=0
[[ "$rollback_code" -ne 0 ]] || {
  print -u2 "install reported success while every bootstrap failed"
  exit 1
}
[[ "$(<"$rollback_unit")" == "previously installed unit" ]] || {
  print -u2 "install did not restore the previously installed unit"
  exit 1
}
[[ "$(grep -c '^bootstrap ' "$rollback_root/launchctl.log")" -gt 5 ]] || {
  print -u2 "install did not retry the restored unit"
  exit 1
}

# --- uninstall unloads and removes the unit --------------------------------
: >"$install_root/launchctl.log"
run_unit "$install_root" 1 uninstall >/dev/null
[[ ! -f "$unit_path" ]] || {
  print -u2 "uninstall left $unit_path in place"
  exit 1
}
[[ "$(mutations "$install_root/launchctl.log")" == "bootout $DOMAIN/$LABEL" ]] || {
  print -u2 "uninstall did not boot out the unit"
  exit 1
}

# --- unsupported commands are rejected ------------------------------------
for unsupported_command in start stop run prepare '' ; do
  arguments=()
  [[ -n "$unsupported_command" ]] && arguments=("$unsupported_command")
  set +e
  run_unit "$install_root" 0 "${arguments[@]}" >/dev/null 2>&1
  exit_code=$?
  set -e
  if [[ "$exit_code" -ne 2 ]]; then
    print -u2 "unsupported command '${unsupported_command:-<empty>}' returned $exit_code"
    exit 1
  fi
done

print "unit manager tests passed"
