#!/bin/bash
# Install the touchscreen-after-resume fix: sudo touch/install.sh
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 1; }
HERE="$(cd "$(dirname "$0")" && pwd)"
install -d /etc/systemd/system/iptsd@.service.d
install -m 0644 "$HERE/iptsd-restart.conf" /etc/systemd/system/iptsd@.service.d/restart.conf
systemctl daemon-reload
echo ">> iptsd now retries after a failed start (takes effect immediately)"
