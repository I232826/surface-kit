#!/bin/bash
# Freeze hunt: load the IPU4P stack with the kernel log printed straight to
# this console, so the last line before a hard freeze stays on screen.
# Run from a text VT (Ctrl+Alt+F3), not from a terminal in the desktop:
#
#   sudo ~/surface-kit/camera/scripts/debug-isys.sh        # normal runtime PM
#   sudo ~/surface-kit/camera/scripts/debug-isys.sh pin    # keep the IPU powered
#
# Needs a debug build: DEBUG=1 camera/build.sh (patches/debug/*).
set -euo pipefail

[ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 1; }
# (no tty check: sudo's use_pty makes `tty` report /dev/pts/N even on a VT)

OUT="$(cd "$(dirname "$0")/.." && pwd)/out/$(uname -r)"
MMU1=/sys/bus/intel-ipu4-bus/devices/intel-ipu4-mmu1/power/control
MMU0=/sys/bus/intel-ipu4-bus/devices/intel-ipu4-mmu0/power/control
MODE="${1:-normal}"
ISYS_ARGS=()

grep -q '^intel_ipu4p ' /proc/modules && { echo "already loaded this boot; reboot first" >&2; exit 1; }
grep -qa skdbg_rpm_forbid "$OUT/intel-ipu4p-isys.ko" || { echo "isys.ko has no breadcrumbs: run DEBUG=1 camera/build.sh first" >&2; exit 1; }

say() { echo; echo ">>> $*"; sleep 1; }

say "IOMMU passthrough for the IPU (group 0)"
echo identity > /sys/kernel/iommu_groups/0/type
cat /sys/kernel/iommu_groups/0/type

sysctl -q kernel.hardlockup_panic=1 kernel.softlockup_panic=1

say "deps + patched ov5693"
modprobe -a ipu_bridge videodev mc v4l2_async v4l2_fwnode v4l2_cci \
    videobuf2_common videobuf2_v4l2 videobuf2_dma_contig
grep -q '^ov5693 ' /proc/modules && rmmod ov5693
# mirror=1: mirrored selfie view (patches/ov5693/0001); 0 = un-mirrored
insmod "$OUT/ov5693.ko" mirror=1
# rear ov8865's VCM (focus motor). The stock 6.19 dw9719 can't bind the
# "dw9719" client ipu-bridge creates (no i2c id table), so use ours
# (patches/dw9719/0001). It must be loaded before the isys: the lens gets
# its /dev/v4l-subdev node only when the sensor binds, because the isys
# notifier never completes (the IR ov7251 never probes).
grep -q '^dw9719 ' /proc/modules && rmmod dw9719
# rear sensor: ours writes its mode on stream start (patches/ov8865/0001);
# the stock one only does it on power-up, which the VCM link prevents.
# The lens (dw9719) holds a link to it, so it goes out first (above).
grep -q '^ov8865 ' /proc/modules && rmmod ov8865
insmod "$OUT/ov8865.ko"
insmod "$OUT/dw9719.ko"

say "csslibs, ipu4p core, psys (known good)"
insmod "$OUT/intel-ipu4p-isys-csslib.ko"
insmod "$OUT/intel-ipu4p-psys-csslib.ko"
insmod "$OUT/intel-ipu4p.ko" fw_version_check=0
insmod "$OUT/intel-ipu4p-psys.ko"
sleep 2
echo on > "$MMU1" && echo "mmu1 pinned on"
if [ "$MODE" = pin ]; then
    echo on > "$MMU0" && echo "mmu0 pinned on"
    ISYS_ARGS+=(skdbg_rpm_forbid=1)
fi
echo "mode: $MODE"

LOGDIR="$(cd "$(dirname "$0")/.." && pwd)/logs"
mkdir -p "$LOGDIR"
chown "${SUDO_USER:-root}:" "$LOGDIR"
LOG="$LOGDIR/debug-isys-$(date +%F-%H%M%S).log"
dmesg -w > "$LOG" &
MIRROR_PIDS="$!"
( while sleep 0.2; do sync "$LOG"; done ) &
MIRROR_PIDS+=" $!"
echo "kernel log mirrored to $LOG"

say "pausing udev so nothing opens the new nodes"
udevadm control --stop-exec-queue

# Everything from here prints to this screen as it happens.
for m in intel_ipu4p ov5693 ov8865; do echo "module $m +p" > /sys/kernel/debug/dynamic_debug/control 2>/dev/null || true; done
# ...minus the per-page MMU/DMA mapping spam that buries everything else
for f in ipu-mmu.c ipu-dma.c; do echo "file *$f -p" > /sys/kernel/debug/dynamic_debug/control 2>/dev/null || true; done
dmesg -n 8
say "insmod isys. If the machine freezes, photograph this screen."
sleep 2
# front ov5693 (CSI-2 port 2) only locks reliably with a longer data-lane
# settle; the rear (port 0) is best on the calculated value (patch 0009)
# skip_fw_ports=6: leave the never-probing IR ov7251 out of the notifier so
# it completes and late subdevs (the rear VCM) get device nodes (patch 0011)
insmod "$OUT/intel-ipu4p-isys.ko" csi2_dsettle_port=-1,-1,850 skip_fw_ports=6 "${ISYS_ARGS[@]}"

sleep 3
echo
dmesg -n 4
# Debug prints stay on only for the load itself: dev_dbg fires per IRQ /
# per frame, and rsyslog writes all of it to /var/log (it filled the disk).
for m in intel_ipu4p intel_ipu4p_isys ov5693 ov8865; do echo "module $m -p" > /sys/kernel/debug/dynamic_debug/control 2>/dev/null || true; done
kill $MIRROR_PIDS 2>/dev/null; sync "$LOG"
# lockup->panic only helps while hunting a load-time freeze; with kdump
# broken on this machine a later stall would just look like a hard hang
sysctl -q kernel.hardlockup_panic=0 kernel.softlockup_panic=0
if [ "$MODE" = pin ]; then
    echo ">>> isys loaded with the IPU held powered on. udev stays PAUSED until reboot."
else
    # Let the islands power-cycle (clears a wedged stream's reset latch) and
    # let udev catch up so the session gets ACLs on the new nodes.
    echo auto > "$MMU1"
    udevadm control --start-exec-queue
    udevadm settle --timeout=30 || true
    echo ">>> isys loaded, runtime PM on, udev resumed."
    cat /sys/bus/intel-ipu4-bus/devices/*/power/runtime_status | paste -sd' '
fi
ls /dev/media* 2>/dev/null || echo "(no /dev/media0)"
echo "next: sudo ~/surface-kit/camera/scripts/capture.sh rear|front   or   cam -l"
