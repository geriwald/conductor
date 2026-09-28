#!/usr/bin/env bash
# Install Conductor and its player as systemd user services, started with the desktop session.
#
#   tools/install-systemd.sh /path/to/YouTube-Music.AppImage
#
# The player gets its DevTools port (Conductor opens albums through it); the daemon runs
# from this checkout's .venv. Closing the player window stops it until the next session.
set -euo pipefail

player=${1:?usage: $0 /path/to/YouTube-Music.AppImage}
player=$(realpath "$player")
checkout=$(cd "$(dirname "$0")/.." && pwd)
units=${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user
devtools_port=9333

[[ -x $player ]] || { echo "not executable: $player" >&2; exit 1; }
[[ -x $checkout/.venv/bin/conductor ]] || { echo "no $checkout/.venv/bin/conductor: install the package first" >&2; exit 1; }
mkdir -p "$units"

cat >"$units/conductor-player.service" <<EOF
[Unit]
Description=YouTube Music player driven by Conductor
PartOf=graphical-session.target
After=graphical-session.target

[Service]
ExecStart=$player --remote-debugging-port=$devtools_port
Restart=on-failure

[Install]
WantedBy=graphical-session.target
EOF

cat >"$units/conductor.service" <<EOF
[Unit]
Description=Conductor: agents choose the music, media keys answer back
PartOf=graphical-session.target
After=graphical-session.target conductor-player.service
Wants=conductor-player.service

[Service]
WorkingDirectory=$checkout
ExecStart=$checkout/.venv/bin/conductor serve
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical-session.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now conductor-player.service conductor.service
systemctl --user --no-pager status conductor-player.service conductor.service | grep -E "●|Active:"
