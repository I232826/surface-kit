#!/bin/bash
# Install the touch fixes: sudo touch/install.sh
#  - iptsd restarts after a failed start (touch after resume)
#  - iptsd detection and palm settings for the Surface Pro 7
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 1; }
HERE="$(cd "$(dirname "$0")" && pwd)"
install -d /etc/systemd/system/iptsd@.service.d
install -m 0644 "$HERE/iptsd-restart.conf" /etc/systemd/system/iptsd@.service.d/restart.conf
systemctl daemon-reload
echo ">> iptsd now retries after a failed start (takes effect immediately)"

install -d /etc/iptsd.d
install -m 0644 "$HERE/iptsd-surface-pro-7.conf" /etc/iptsd.d/90-surface-pro-7.conf
# earlier hand-made pieces, now part of 90-surface-pro-7.conf
rm -f /etc/iptsd.d/90-pen.conf /etc/iptsd.d/91-calibration-045E-099F.conf
systemctl restart 'iptsd@*'
echo ">> iptsd settings installed and iptsd restarted"
