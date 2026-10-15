#!/bin/bash
# Auto-rotation: the patched sensor hub driver, loaded after boot.
#   sudo sensors/install.sh [kernel-version]    install (build: camera/build.sh)
#   sudo sensors/install.sh --remove            back to the stock driver
# Both rebuild the initramfs (it must not carry the stock driver); reboot
# afterwards; the hub only starts from a cold boot.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 1; }
HERE="$(cd "$(dirname "$0")" && pwd)"

if [ "${1:-}" = --remove ]; then
    systemctl disable surface-ish.service 2>/dev/null || true
    rm -f /etc/systemd/system/surface-ish.service /usr/local/sbin/surface-ish \
        /usr/lib/systemd/system-sleep/surface-ish /usr/lib/systemd/system-sleep/surface-sensors \
        /etc/modprobe.d/surface-ish.conf
    rm -rf /usr/local/lib/surface-kit/*/intel-ish-ipc.ko
    systemctl daemon-reload
    update-initramfs -u
    echo ">> removed; reboot"
    exit 0
fi

KVER="${1:-$(uname -r)}"
KO="$HERE/../camera/out/$KVER/intel-ish-ipc.ko"
[ -e "$KO" ] || { echo "no $KO: run camera/build.sh" >&2; exit 1; }

# never both: an override in updates/ would be loaded by udev at boot
rm -f "/lib/modules/$KVER/updates/surface-kit/intel-ish-ipc.ko"
depmod "$KVER"

install -D -m 0644 "$KO" "/usr/local/lib/surface-kit/$KVER/intel-ish-ipc.ko"
install -m 0755 "$HERE/surface-ish" /usr/local/sbin/surface-ish
# the unbind/bind sleep hook of the first attempt: binding after sleep hangs
rm -f /usr/lib/systemd/system-sleep/surface-ish
# restarts iio-sensor-proxy after wake; via a temp file so a half-written
# hook is never left behind
install -m 0755 "$HERE/surface-sensors-sleep" /usr/lib/systemd/system-sleep/.surface-sensors.new
mv /usr/lib/systemd/system-sleep/.surface-sensors.new /usr/lib/systemd/system-sleep/surface-sensors
install -m 0644 "$HERE/surface-ish.conf" /etc/modprobe.d/surface-ish.conf
install -m 0644 "$HERE/surface-ish.service" /etc/systemd/system/surface-ish.service
systemctl daemon-reload
systemctl enable surface-ish.service
sync
echo ">> initramfs"
update-initramfs -u -k "$KVER"
sync
echo ">> done; power off fully and start again (the hub needs a cold start)"
