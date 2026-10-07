#!/bin/bash
# Front camera (ov5693, 2 lanes @419.2 MHz) D-PHY lock is marginal. Try
# data-lane settle counts above the calculated minimum (661) until one
# delivers frames. The Fedora bring-up measured a usable window of roughly
# 661..1103; values in it are also inside the rear ov8865's window.
#
#   sudo camera/scripts/front-sweep.sh [values...]
set -uo pipefail

[ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 1; }
P=/sys/module/intel_ipu4p_isys/parameters
[ -w $P/csi2_dsettle ] || { echo "isys not loaded" >&2; exit 1; }
HERE="$(dirname "$(readlink -f "$0")")"

[ $# -gt 0 ] || set -- 750 880 1000 1090
for d in "$@"; do
    echo "$d" > $P/csi2_dsettle
    echo "=== csi2_dsettle=$d"
    if "$HERE/capture.sh" front; then
        echo "=== front camera works with csi2_dsettle=$d"
        exit 0
    fi
done
echo "=== no value locked; leaving csi2_dsettle=-1"
echo -1 > $P/csi2_dsettle
exit 1
