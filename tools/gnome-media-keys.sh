#!/usr/bin/env bash
# Give the keyboard's media keys to Conductor on GNOME, or give them back.
#
#   tools/gnome-media-keys.sh install     # media keys call `conductor key <name>`
#   tools/gnome-media-keys.sh uninstall   # GNOME's own media keys come back
#
# GNOME's static media-key bindings are emptied so the keys are free, then bound to
# custom shortcuts. Play and pause both mean the play/pause toggle: keyboards with a
# single toggle key send one or the other.
set -euo pipefail

schema=org.gnome.settings-daemon.plugins.media-keys
base=/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings
checkout=$(cd "$(dirname "$0")/.." && pwd)
conductor=$checkout/.venv/bin/conductor

# id  keysym  conductor key
bindings=(
  "play  XF86AudioPlay  play-pause"
  "pause XF86AudioPause play-pause"
  "stop  XF86AudioStop  stop"
  "next  XF86AudioNext  next"
  "prev  XF86AudioPrev  previous"
)
static_keys=(play-static pause-static stop-static next-static previous-static)

custom_list() { gsettings get $schema custom-keybindings | sed 's/^@as //'; }

set_list() {
  # $@: paths; prints a GVariant string array
  local out="[" sep=""
  for p in "$@"; do out+="$sep'$p'"; sep=", "; done
  gsettings set $schema custom-keybindings "$out]"
}

current_paths() { custom_list | tr -d "[]'," | xargs -n1 2>/dev/null || true; }

install() {
  [[ -x $conductor ]] || { echo "no $conductor: install the package first" >&2; exit 1; }
  for key in "${static_keys[@]}"; do gsettings set $schema "$key" "[]"; done
  local paths=()
  for p in $(current_paths); do [[ $p == $base/conductor-* ]] || paths+=("$p"); done
  for entry in "${bindings[@]}"; do
    read -r id keysym name <<<"$entry"
    local path=$base/conductor-$id/
    local s=$schema.custom-keybinding:$path
    gsettings set "$s" name "Conductor: $name"
    gsettings set "$s" command "$conductor key $name"
    gsettings set "$s" binding "$keysym"
    paths+=("$path")
  done
  set_list "${paths[@]}"
  echo "media keys now call $conductor key <name>"
}

uninstall() {
  local paths=()
  for p in $(current_paths); do
    if [[ $p == $base/conductor-* ]]; then
      gsettings reset-recursively "$schema.custom-keybinding:$p"
    else
      paths+=("$p")
    fi
  done
  set_list "${paths[@]}"
  for key in "${static_keys[@]}"; do gsettings reset $schema "$key"; done
  echo "GNOME's own media keys are back"
}

case ${1:-} in
  install) install ;;
  uninstall) uninstall ;;
  *) echo "usage: $0 install|uninstall" >&2; exit 2 ;;
esac
