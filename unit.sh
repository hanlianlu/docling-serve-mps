#!/bin/zsh
set -euo pipefail

# macOS launchd unit for a source checkout. `service.sh` deliberately accepts
# exactly `start` and `stop` because it wraps the package's own lifecycle; a
# supervisor owns the lifecycle instead, so its unit is managed here. A systemd
# deployment would add a sibling script rather than widen that contract.

ROOT=${0:A:h}
LABEL=com.orliantra.docling-mps
TEMPLATE="$ROOT/launchd/$LABEL.plist.template"
UNIT_DIR="$HOME/Library/LaunchAgents"
UNIT="$UNIT_DIR/$LABEL.plist"
LOGDIR="$HOME/Library/Logs/artrag"
DOMAIN="gui/$(id -u)"
TAB=$'\t'

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

render_unit() {
  [[ -f "$TEMPLATE" ]] || {
    print -u2 "missing unit template: $TEMPLATE"
    return 1
  }
  local template_text
  template_text=$(<"$TEMPLATE")
  template_text=${template_text//__LABEL__/$LABEL}
  template_text=${template_text//__ROOT__/$ROOT}
  template_text=${template_text//__HOME__/$HOME}
  template_text=${template_text//__LOGDIR__/$LOGDIR}
  mkdir -p "$UNIT_DIR" "$LOGDIR"
  print -r -- "$template_text" >"$UNIT"
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

case "${1:-}" in
  install)
    require_launchctl
    render_unit
    boot_out
    launchctl bootstrap "$DOMAIN" "$UNIT"
    print "installed $UNIT"
    print "launchd starts it at login and restarts it if it exits."
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
      # -k restarts the running job so it reloads the code on disk.
      launchctl kickstart -k "$DOMAIN/$LABEL"
      print "restarted $LABEL"
    else
      [[ -f "$UNIT" ]] || {
        print -u2 "no unit installed at $UNIT; run '$0 install' first"
        return 1
      }
      launchctl bootstrap "$DOMAIN" "$UNIT"
      print "loaded $LABEL"
    fi
    ;;
  status)
    require_launchctl
    if ! is_loaded; then
      print "$LABEL is not loaded"
      exit 1
    fi
    launchctl print "$DOMAIN/$LABEL" |
      grep -E "^${TAB}(state|pid|runs|last exit code) = " |
      sed -E "s/^${TAB}/  /"
    ;;
  *)
    usage
    ;;
esac
