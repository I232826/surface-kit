#!/bin/bash
# Install the power-button helpers for the current user (no root needed).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p ~/.config/systemd/user
install -m 0644 "$HERE/surface-sleep-screen-off.service" ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now surface-sleep-screen-off.service
systemctl --user --no-pager status surface-sleep-screen-off.service | head -3
