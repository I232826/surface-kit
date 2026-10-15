#!/bin/bash
# Run the patched iptsd (touch/iptsd/build.sh) instead of the packaged one:
#   sudo touch/iptsd/install.sh          install and restart iptsd
#   sudo touch/iptsd/install.sh --remove back to /usr/bin/iptsd
# The package stays installed; a systemd drop-in points the service at
# /usr/local/bin/iptsd-surface.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 1; }
HERE="$(cd "$(dirname "$0")" && pwd)"
D=/etc/systemd/system/iptsd@.service.d
if [ "${1:-}" = --remove ]; then
    rm -f "$D/surface-kit-patched.conf" /usr/local/bin/iptsd-surface
else
    [ -x "$HERE/out/iptsd" ] || { echo "run touch/iptsd/build.sh first" >&2; exit 1; }
    install -m 0755 "$HERE/out/iptsd" /usr/local/bin/iptsd-surface
    install -d "$D"
    printf '%s\n' '# surface-kit: patched iptsd (touch/iptsd)' '[Service]' 'ExecStart=' \
        'ExecStart=/usr/local/bin/iptsd-surface /%I' > "$D/surface-kit-patched.conf"
fi
systemctl daemon-reload
systemctl restart 'iptsd@*'
systemctl --no-pager status 'iptsd@*' | grep -E 'Active|CGroup|iptsd-surface|/usr/bin/iptsd' | head -4
