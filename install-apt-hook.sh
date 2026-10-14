#!/bin/bash
# Protect the surface-kit builds (libcamera, GNOME Camera) from Ubuntu
# updates: hold them, and run check-updates.sh after every `apt update` so
# it says when Ubuntu has something newer to rebuild on. Run as root.
set -euo pipefail
SK="$(cd "$(dirname "$0")" && pwd)"
PKGS=(libcamera0.7 libcamera-ipa libcamera-tools libcamera-v4l2 gstreamer1.0-libcamera gnome-snapshot)
apt-mark hold "${PKGS[@]}"
cat > /etc/apt/apt.conf.d/99surface-kit <<CONF
// surface-kit: report when held builds need a rebuild ($SK/check-updates.sh)
APT::Update::Post-Invoke-Success { "[ -x $SK/check-updates.sh ] && runuser -u $(stat -c %U "$SK") -- $SK/check-updates.sh --quiet || true"; };
CONF
echo ">> held: ${PKGS[*]}"
echo ">> apt update now runs $SK/check-updates.sh"
