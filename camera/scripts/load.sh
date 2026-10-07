#!/bin/bash
# Load the IPU4P stack built by camera/build.sh, straight from camera/out/
# (nothing is installed into /lib/modules, so a reboot always returns to
# the stock state). The driver can't be unloaded/reloaded: one load per boot.
#
#   sudo camera/scripts/load.sh
set -euo pipefail

[ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 1; }

CAM="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(dirname "$CAM")"
OUT="$CAM/out/$(uname -r)"
FW=/usr/lib/firmware/ipu4p_cpd.bin
FW_SRC="$ROOT/vendor/dl/ipu4-20191030.bin"
FW_SHA=ff2c36cc81a5c726508b22970c2e2538ff06107dc5a72c93401403c227e5157f
MMU1=/sys/bus/intel-ipu4-bus/devices/intel-ipu4-mmu1/power/control

if grep -q '^intel_ipu4p ' /proc/modules; then
    echo "IPU4P stack already loaded this boot (reload is not supported; reboot to retry)" >&2
    exit 1
fi
for m in ov5693 intel-ipu4p-isys-csslib intel-ipu4p-psys-csslib intel-ipu4p \
         intel-ipu4p-psys intel-ipu4p-isys; do
    [ -f "$OUT/$m.ko" ] || { echo "missing $OUT/$m.ko, run camera/build.sh" >&2; exit 1; }
done

if [ ! -f "$FW" ]; then
    echo "$FW_SHA  $FW_SRC" | sha256sum -c --quiet -
    install -m 0644 "$FW_SRC" "$FW"
    echo "installed firmware $FW"
fi

# In-tree dependencies first, then swap the stock ov5693 for the patched one
# (binned modes disabled) before the isys binds the sensors.
modprobe -a ipu_bridge videodev mc v4l2_async v4l2_fwnode v4l2_cci \
    videobuf2_common videobuf2_v4l2 videobuf2_dma_contig
if grep -q '^ov5693 ' /proc/modules; then
    rmmod ov5693
fi
insmod "$OUT/ov5693.ko"

insmod "$OUT/intel-ipu4p-isys-csslib.ko"
insmod "$OUT/intel-ipu4p-psys-csslib.ko"
insmod "$OUT/intel-ipu4p.ko" fw_version_check=0
insmod "$OUT/intel-ipu4p-psys.ko"

# Pin the psys MMU power island on while udev probes the ~50 video nodes the
# isys creates; a power handshake timeout during that storm latches runtime
# PM 'error' until reboot. Unpinned again 30s later so it can self-heal.
for _ in $(seq 1 50); do
    [ -e "$MMU1" ] && break
    sleep 0.1
done
echo on > "$MMU1" || echo "WARN: could not pin mmu1" >&2

insmod "$OUT/intel-ipu4p-isys.ko"

sleep 2
if [ ! -e /dev/media0 ]; then
    echo "ERROR: /dev/media0 missing" >&2
    dmesg | grep -iE 'ipu|ov5693|ov8865' | tail -30 >&2
    exit 1
fi

echo "IPU4P loaded: $(ls /dev/video* | wc -l) video nodes"
dmesg | grep -iE 'CSE|Connected.*camera|bind ov|authenticat' | tail -8

( sleep 30; echo auto > "$MMU1" 2>/dev/null || true ) &
disown
