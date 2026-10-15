#!/bin/bash
# Install the surface-kit apps for the current user (no root):
# ~/.local/bin/<app> and a desktop entry, so they show up in the app grid.
#   apps/install.sh            all apps
#   apps/install.sh recorder   one app
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p ~/.local/bin ~/.local/share/applications
for app in "${@:-$(ls -d "$HERE"/*/ | xargs -n1 basename)}"; do
    dir="$HERE/$app"
    [ -f "$dir/$app.py" ] || { echo "no app $app" >&2; continue; }
    ln -sf "$dir/$app.py" ~/.local/bin/"$app"
    chmod +x "$dir/$app.py"
    install -m 0644 "$dir"/*.desktop ~/.local/share/applications/
    echo ">> $app"
done
update-desktop-database ~/.local/share/applications 2>/dev/null || true
