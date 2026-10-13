#!/bin/bash
# Measure how reliably a camera's CSI-2 link locks for a range of data-lane
# settle counts, through libcamera the way apps use it. Runs as the normal
# user; the per-port parameter must be writable for this boot first:
#
#   sudo chmod o+w /sys/module/intel_ipu4p_isys/parameters/csi2_dsettle_port
#   camera/scripts/settle-sweep.sh [front|rear] [tries] [values...]
#
# KNOB=afe sweeps the analog front-end setting of the camera's PHY building
# block instead (front: bb 10), with dsettle held at DSETTLE (default 850):
#   sudo chmod o+w /sys/module/intel_ipu4p_isys/parameters/{csi2_dsettle_port,phy_bb_extra,phy_afe_extra}
#   KNOB=afe camera/scripts/settle-sweep.sh front 4 0xf 0x15 ...
#
# KNOB=regs tries sets of extra ov5693 register writes (front only), each
# value a comma list of 0xRRRRVV, "0" = none (ov5693/0002 debug patch):
#   sudo chmod o+w /sys/module/ov5693/parameters/regs
#   KNOB=regs camera/scripts/settle-sweep.sh front 6 0 0x480004 ...
#
# KNOB=portcfg tries sip1 (combo) port/lane-mux configs (patch 0010):
#   sudo chmod o+w /sys/module/intel_ipu4p_isys/parameters/combo_port_cfg
#   KNOB=portcfg camera/scripts/settle-sweep.sh front 4 0x3895 0x3899 ...
#
# KNOB=csettle sweeps the clock-lane settle count instead (dsettle held at
# DSETTLE); -1 = calculated (spec minimum):
#   sudo chmod o+w /sys/module/intel_ipu4p_isys/parameters/{csi2_dsettle_port,csi2_csettle_port}
#   KNOB=csettle camera/scripts/settle-sweep.sh front 4 -1 1000 1400 1800
#
# KNOB=param tries values of any writable module parameter PARAM (sysfs
# path), with dsettle held at DSETTLE, e.g. the isys bounce power cycle:
#   P=/sys/module/intel_ipu4p_isys/parameters/relock_power_cycle
#   sudo chmod o+w $P /sys/module/intel_ipu4p_isys/parameters/csi2_dsettle_port
#   KNOB=param PARAM=$P camera/scripts/settle-sweep.sh front 8 0 1 0 1
#
# PipeWire/WirePlumber are stopped for the run (they keep the nodes open,
# which stops the IPU power-cycling after a failed stream) and restarted at
# the end. Results: camera/sweeps/settle-sweep-*.tsv
set -uo pipefail
export LC_NUMERIC=C

WHICH="${1:-front}"; shift || true
TRIES="${1:-6}"; shift || true
KNOB="${KNOB:-dsettle}"
# frames to capture per try (25 s cap): 30 tests the start, 150 stability
CAPTURE="${CAPTURE:-30}"
DSETTLE="${DSETTLE:-850}"
if [ $# -eq 0 ]; then
    if [ "$KNOB" = afe ]; then set -- 0x15 0xf 0x10 0x13 0x17 0x1a 0x1f 0x5
    elif [ "$KNOB" = regs ]; then set -- 0
    elif [ "$KNOB" = portcfg ]; then set -- 0x3895 0x3899 0x3898 0x3896 0x3893 0x3892 0x3890
    else set -- -1 700 750 800 850 880 920 960 1000 1050 1100; fi
fi

case "$WHICH" in
front) PORT=2; BB=10; CAMID='\_SB_.PCI0.I2C2.CAMF'; SENSOR=ov5693 ;;
rear)  PORT=0; BB=4; CAMID='\_SB_.PCI0.I2C3.CAMR'; SENSOR=ov8865 ;;
*) echo "usage: $0 front|rear [tries] [values...]" >&2; exit 1 ;;
esac

P=/sys/module/intel_ipu4p_isys/parameters/csi2_dsettle_port
ISYS=/sys/bus/intel-ipu4-bus/devices/intel-ipu60/power/runtime_status
[ -w "$P" ] || { echo "$P not writable: sudo chmod o+w $P" >&2; exit 1; }
ORIG=$(cat "$P")
PBB=/sys/module/intel_ipu4p_isys/parameters/phy_bb_extra
PAFE=/sys/module/intel_ipu4p_isys/parameters/phy_afe_extra
if [ "$KNOB" = afe ]; then
    [ -w "$PBB" ] && [ -w "$PAFE" ] || { echo "make $PBB and $PAFE writable too" >&2; exit 1; }
    ORIG_BB=$(cat "$PBB"); ORIG_AFE=$(cat "$PAFE")
fi
PPORT=/sys/module/intel_ipu4p_isys/parameters/combo_port_cfg
if [ "$KNOB" = portcfg ]; then
    [ -w "$PPORT" ] || { echo "make $PPORT writable too" >&2; exit 1; }
    ORIG_PORT=$(cat "$PPORT")
fi
if [ "$KNOB" = param ]; then
    [ -n "${PARAM:-}" ] && [ -w "$PARAM" ] || { echo "PARAM must name a writable parameter" >&2; exit 1; }
    ORIG_PARAM=$(cat "$PARAM")
fi
PC=/sys/module/intel_ipu4p_isys/parameters/csi2_csettle_port
if [ "$KNOB" = csettle ]; then
    [ -w "$PC" ] || { echo "make $PC writable too" >&2; exit 1; }
    ORIG_C=$(cat "$PC")
fi
PREGS=/sys/module/ov5693/parameters/regs
if [ "$KNOB" = regs ]; then
    [ -w "$PREGS" ] || { echo "make $PREGS writable too" >&2; exit 1; }
    ORIG_REGS=$(cat "$PREGS")
fi

RESDIR="$(cd "$(dirname "$0")/.." && pwd)/sweeps"
mkdir -p "$RESDIR" || exit 1
OUT="$RESDIR/$KNOB-sweep-$WHICH-$(date +%F-%H%M%S).tsv"
: > "$OUT" || { echo "cannot write $OUT" >&2; exit 1; }

UNITS="wireplumber pipewire-pulse pipewire pipewire-pulse.socket pipewire.socket"
restore() {
    echo "$ORIG" > "$P"
    if [ "$KNOB" = afe ]; then echo "$ORIG_BB" > "$PBB"; echo "$ORIG_AFE" > "$PAFE"; fi
    if [ "$KNOB" = regs ]; then echo "${ORIG_REGS:-0}" > "$PREGS"; fi
    if [ "$KNOB" = portcfg ]; then echo "$ORIG_PORT" > "$PPORT"; fi
    if [ "$KNOB" = param ]; then echo "$ORIG_PARAM" > "$PARAM"; fi
    if [ "$KNOB" = csettle ]; then echo "$ORIG_C" > "$PC"; fi
    systemctl --user start pipewire.socket pipewire-pulse.socket pipewire pipewire-pulse wireplumber
}
trap restore EXIT
systemctl --user stop $UNITS

port_list() {   # value for $PORT, -1 elsewhere; keeps the other ports as they were
    python3 - "$ORIG" "$PORT" "$1" <<'PY'
import sys
vals = sys.argv[1].split(","); vals += ["-1"] * (8 - len(vals))
vals[int(sys.argv[2])] = sys.argv[3]
print(",".join(vals))
PY
}

wait_idle() {   # a failed stream latches reset_needed until the isys powers off
    for _ in $(seq 1 40); do
        [ "$(cat $ISYS)" = suspended ] && return 0
        sleep 0.25
    done
    return 1
}

printf "value\ttry\tframes\tbounces\tsync_errors\tseconds\n" | tee "$OUT"
for v in "$@"; do
    if [ "$KNOB" = afe ]; then
        # bb_cfg applies phy_bb_extra after the builtin table, so this
        # overrides the BB entry; takes effect on the next isys resume
        port_list "$DSETTLE" > "$P"
        echo "$BB" > "$PBB"
        echo "$((v))" > "$PAFE"
    elif [ "$KNOB" = portcfg ]; then
        port_list "$DSETTLE" > "$P"
        echo "$((v))" > "$PPORT"   # applied at the next isys resume
    elif [ "$KNOB" = regs ]; then
        port_list "$DSETTLE" > "$P"
        echo "$v" > "$PREGS"   # applied at the sensor's next power-up
    elif [ "$KNOB" = csettle ]; then
        port_list "$DSETTLE" > "$P"
        ORIG_SAVE=$ORIG; ORIG=$ORIG_C; port_list "$v" > "$PC"; ORIG=$ORIG_SAVE
    elif [ "$KNOB" = param ]; then
        port_list "$DSETTLE" > "$P"
        echo "$v" > "$PARAM"
    else
        port_list "$v" > "$P"
    fi
    for t in $(seq 1 "$TRIES"); do
        wait_idle || echo "  (isys did not power down)" >&2
        since=$(date '+%F %T')
        start=$(date +%s.%N)
        frames=$(timeout 25 cam --camera="$CAMID" --capture="$CAPTURE" 2>/dev/null | grep -c "seq:")
        secs=$(echo "$(date +%s.%N) - $start" | bc)
        klog=$(journalctl -k --since "$since" --no-pager -q 2>/dev/null)
        bounces=$(grep -c "no frames from $SENSOR" <<<"$klog")
        syncerr=$(grep -c "non-recoverable synchronization" <<<"$klog")
        printf "%s\t%s\t%s\t%s\t%s\t%.1f\n" "$v" "$t" "$frames" "$bounces" "$syncerr" "$secs" | tee -a "$OUT"
    done
done

echo
echo "summary ($WHICH, $TRIES tries each, ok = all $CAPTURE frames): value  ok/tries  avg-bounces"
awk -F'\t' -v c="$CAPTURE" 'NR>1 { n[$1]++; if ($3>=c) ok[$1]++; b[$1]+=$4 }
            END { for (v in n) printf "  %6s  %d/%d  %.1f\n", v, ok[v], n[v], b[v]/n[v] }' "$OUT" | sort -n
echo "raw: $OUT"
