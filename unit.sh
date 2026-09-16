#!/bin/zsh
set -euo pipefail

# Manages the launchd *unit definition* for a source checkout — not the service.
# The supervisor owns the service lifecycle: it starts the job at login, restarts
# it when it exits, and is the only thing that can stop it. This script only
# renders, validates, loads and unloads the unit that describes that job.
#
# `service.sh` deliberately accepts exactly `start` and `stop`, because it wraps
# the package's own lifecycle for an unsupervised process; a supervised one has
# no lifecycle for that wrapper to manage. A systemd deployment would add a
# sibling script rather than widen that contract.

ROOT=${0:A:h}
LABEL=com.orliantra.docling-mps
TEMPLATE="$ROOT/launchd/$LABEL.plist.template"
UNIT_DIR="$HOME/Library/LaunchAgents"
UNIT="$UNIT_DIR/$LABEL.plist"
LOGDIR="$HOME/Library/Logs/artrag"
STATE_DIR="$HOME/Library/Application Support/docling-serve-mps"
PREVIOUS_UNIT="$STATE_DIR/unit-previous.plist"
DOMAIN="gui/$(id -u)"
TAB=$'\t'
# Teardown is asynchronous, and a registration made while launchd is still
# discarding the old job can be dropped without an error, so both halves of a
# reload are polled rather than assumed.
POLL_ATTEMPTS=10
LOAD_ATTEMPTS=3
# Seconds between launchd polls. Overridable so the failure paths can be
# exercised without waiting out the real interval.
POLL_SECONDS=${DOCLING_SERVE_MPS_UNIT_POLL_SECONDS:-1}

usage() {
  print -u2 "Usage: $0 {install|uninstall|restart|status}"
  exit 2
}

require_launchctl() {
  command -v launchctl >/dev/null 2>&1 || {
    print -u2 "launchctl is required: this unit targets the macOS launchd supervisor."
    return 1
  }
}

render_text() {
  [[ -f "$TEMPLATE" ]] || {
    print -u2 "missing unit template: $TEMPLATE"
    return 1
  }
  local text
  text=$(<"$TEMPLATE")
  text=${text//__LABEL__/$LABEL}
  text=${text//__ROOT__/$ROOT}
  text=${text//__HOME__/$HOME}
  text=${text//__LOGDIR__/$LOGDIR}
  local placeholder
  for placeholder in __LABEL__ __ROOT__ __HOME__ __LOGDIR__; do
    [[ "$text" != *"$placeholder"* ]] || {
      print -u2 "unit template still contains $placeholder after rendering"
      return 1
    }
  done
  print -r -- "$text"
}

write_unit() {
  mkdir -p "$UNIT_DIR" "$LOGDIR"
  render_text >"$UNIT" || return 1
  # launchd refuses a malformed property list long after the mistake is made,
  # so the render is checked before it is installed.
  plutil -lint "$UNIT" >/dev/null || {
    print -u2 "rendered unit is not a valid property list: $UNIT"
    return 1
  }
}

is_loaded() {
  launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1
}

boot_out() {
  # Unloading a job that is not loaded is not an error for these commands.
  launchctl bootout "$DOMAIN/$LABEL" >/dev/null 2>&1 || true
}

is_running() {
  launchctl print "$DOMAIN/$LABEL" 2>/dev/null | grep -qE "^${TAB}state = running"
}

wait_unloaded() {
  local attempt
  for attempt in $(seq $POLL_ATTEMPTS); do
    is_loaded || return 0
    sleep "$POLL_SECONDS"
  done
  return 1
}

wait_running() {
  local attempt
  for attempt in $(seq $POLL_ATTEMPTS); do
    is_running && return 0
    sleep "$POLL_SECONDS"
  done
  return 1
}

load_unit() {
  # The unit being loaded must already be unloaded: bootstrap only registers a
  # job, so success is the job running, not bootstrap's exit code.
  local attempt
  for attempt in $(seq $LOAD_ATTEMPTS); do
    launchctl bootstrap "$DOMAIN" "$UNIT" >/dev/null 2>&1 || true
    wait_running && return 0
    boot_out
    wait_unloaded || true
  done
  return 1
}

restore_previous_unit() {
  [[ -f "$PREVIOUS_UNIT" ]] || return 1
  cp "$PREVIOUS_UNIT" "$UNIT"
  boot_out
  wait_unloaded && load_unit
}

state_facts() {
  # Reporting is best-effort: a job that is not answering `print` yet must not
  # turn a completed load into a reported failure.
  launchctl print "$DOMAIN/$LABEL" 2>/dev/null |
    grep -E "^${TAB}(state|pid|runs|last exit code) = " |
    sed -E "s/^${TAB}/  /" || true
}

case "${1:-}" in
  install)
    require_launchctl
    rendered=$(render_text) || exit 1
    if [[ -f "$UNIT" && "$rendered" == "$(<"$UNIT")" ]] && is_loaded; then
      # Reloading an unchanged unit would restart a healthy service for nothing.
      print "$UNIT already matches the template; leaving the running job alone"
      state_facts
      exit 0
    fi
    # Keep the installed unit so a unit launchd refuses can be rolled back
    # instead of leaving the machine with no service loaded at all.
    if [[ -f "$UNIT" ]]; then
      mkdir -p "$STATE_DIR"
      cp "$UNIT" "$PREVIOUS_UNIT"
    fi
    write_unit
    boot_out
    if ! wait_unloaded; then
      print -u2 "the running job did not unload; leaving $UNIT unchanged"
      exit 1
    fi
    if ! load_unit; then
      print -u2 "launchd did not keep $LABEL running after loading $UNIT"
      if restore_previous_unit; then
        print -u2 "restored the previously installed unit; the service is running the old definition"
      else
        print -u2 "recovery failed; load a unit by hand: launchctl bootstrap $DOMAIN $UNIT"
      fi
      exit 1
    fi
    print "installed $UNIT"
    state_facts
    ;;
  uninstall)
    require_launchctl
    boot_out
    rm -f "$UNIT"
    print "removed $UNIT"
    ;;
  restart)
    require_launchctl
    if is_loaded; then
      # -k restarts the running job so it reloads the code on disk. It reuses the
      # definition launchd already has, so a changed plist needs `install`.
      launchctl kickstart -k "$DOMAIN/$LABEL"
    else
      [[ -f "$UNIT" ]] || {
        print -u2 "no unit installed at $UNIT; run '$0 install' first"
        exit 1
      }
      if ! load_unit; then
        print -u2 "launchd did not keep $LABEL running after loading $UNIT"
        exit 1
      fi
      print "loaded $LABEL"
      state_facts
      exit 0
    fi
    if ! wait_running; then
      print -u2 "$LABEL did not come back after a restart"
      exit 1
    fi
    print "restarted $LABEL"
    state_facts
    ;;
  status)
    require_launchctl
    if ! is_loaded; then
      print "$LABEL is not loaded"
      exit 1
    fi
    state_facts
    ;;
  *)
    usage
    ;;
esac
