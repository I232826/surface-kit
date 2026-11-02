#!/bin/bash
# Install the surface-kit shell extensions for the current user (no root).
# GNOME only finds a new extension after logging out and back in.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
# surface-face@surface-kit is installed system-wide by face/install-login.sh
for UUID in surface-kit-shell@surface-kit; do
    DEST=~/.local/share/gnome-shell/extensions/$UUID
    mkdir -p "$DEST"
    install -m 0644 "$HERE/$UUID"/* "$DEST/"
    gnome-extensions enable "$UUID" 2>/dev/null \
        || gsettings set org.gnome.shell enabled-extensions \
            "$(gsettings get org.gnome.shell enabled-extensions | sed "s/]$/, '$UUID']/")"
    gnome-extensions info "$UUID" 2>/dev/null | grep -E 'State|Enabled' || true
done
