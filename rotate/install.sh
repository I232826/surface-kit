#!/bin/bash
# Install the rotation animation extension for the current user (no root).
# GNOME only finds a new extension after logging out and back in.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
UUID=surface-rotate@surface-kit
DEST=~/.local/share/gnome-shell/extensions/$UUID
mkdir -p "$DEST"
install -m 0644 "$HERE/$UUID"/{metadata.json,extension.js} "$DEST/"
gnome-extensions enable "$UUID" 2>/dev/null \
    || gsettings set org.gnome.shell enabled-extensions \
        "$(gsettings get org.gnome.shell enabled-extensions | sed "s/]$/, '$UUID']/")"
gnome-extensions info "$UUID" 2>/dev/null | grep -E 'State|Enabled' || true
