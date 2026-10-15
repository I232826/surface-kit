#!/bin/bash
# Install the Surface Pro 7 camera stack so it loads at every boot:
#   sudo camera/install/install.sh [kernel-version]
# Build first (camera/build.sh). Rerun after a kernel update.
set -euo pipefail

[ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 1; }

HERE="$(cd "$(dirname "$0")" && pwd)"
KVER="${1:-$(uname -r)}"
OUT="$HERE/../out/$KVER"
DEST="/lib/modules/$KVER/updates/surface-kit"

[ -e "$OUT/intel-ipu4p-isys.ko" ] || { echo "no build for $KVER in $OUT: run camera/build.sh" >&2; exit 1; }

echo ">> modules -> $DEST"
install -d "$DEST"
install -m 0644 "$OUT"/*.ko "$DEST/"
# The sensor hub driver (patches/intel-ish-ipc) is built here but installed
# by sensors/install.sh: loaded after boot and detached during sleep, never
# from the module tree (suspending with it bound can hang the machine).
rm -f "$DEST/intel-ish-ipc.ko"
depmod "$KVER"

echo ">> modprobe config, loader, service"
install -m 0644 "$HERE/surface-kit.conf" /etc/modprobe.d/surface-kit.conf
install -m 0644 "$HERE/dracut-surface-kit.conf" /etc/dracut.conf.d/surface-kit.conf
install -m 0755 "$HERE/surface-camera-load" /usr/local/sbin/surface-camera-load
install -m 0644 "$HERE/surface-camera.service" /etc/systemd/system/surface-camera.service
systemctl daemon-reload
systemctl enable surface-camera.service

rm -f /usr/lib/systemd/system-sleep/surface-ish-sleep

# gpio_keys (and the sensor drivers) also live in the initramfs, which would
# load the stock copies before ours: rebuild it from the updated module tree.
echo ">> initramfs"
update-initramfs -u -k "$KVER"

echo ">> done; reboot to load everything (cameras, power button)"
