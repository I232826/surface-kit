#!/bin/bash
# Route one sensor through the CSI2 BE SOC path (the only IPU4 output that
# writes clean line-addressed raster frames) and grab a few RAW10 frames,
# then convert the last one to PNG.
#
#   sudo camera/scripts/capture.sh front|rear [exposure] [analogue_gain]
set -euo pipefail

[ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 1; }

CAM="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(dirname "$CAM")"
ENABLE_LINK="$ROOT/vendor/sp7-ipu4-camera-main/enable-link.py"
OUTDIR="$CAM/captures"
MD=/dev/media0
WHICH="${1:-front}"

case "$WHICH" in
front) SENSOR_RE='ov5693'; RES=2592x1944; EXP="${2:-1900}"; GAIN="${3:-127}" ;;
rear)  SENSOR_RE='ov8865'; RES=3264x2448; EXP="${2:-}";     GAIN="${3:-}" ;;
*) echo "usage: $0 front|rear [exposure] [analogue_gain]" >&2; exit 1 ;;
esac
FMT=SBGGR10_1X10
W=${RES%x*}; H=${RES#*x}

# Sensor entity names carry the i2c bus/addr, which differ between distros.
SENSOR=$(media-ctl -d $MD -p | sed -n "s/^- entity [0-9]*: \($SENSOR_RE [0-9]*-[0-9a-f]*\) .*/\1/p" | sed -n 1p)
[ -n "$SENSOR" ] || { echo "no $SENSOR_RE entity in $MD" >&2; exit 1; }
# Which CSI-2 receiver the sensor is wired to comes from ACPI via ipu-bridge
# and differs from the Fedora port's numbering, so read it from the graph.
PORT=$(media-ctl -d $MD -p | awk -v s="$SENSOR" '
    /^- entity/ { in_s = index($0, ": " s " ") > 0 }
    in_s && match($0, /-> "Intel IPU4 CSI-2 [0-9]+"/) {
        p = substr($0, RSTART, RLENGTH); sub(/.*CSI-2 /, "", p); sub(/"/, "", p); print p; exit }')
[ -n "$PORT" ] || { echo "no CSI-2 link from $SENSOR in $MD" >&2; media-ctl -d $MD -p >&2; exit 1; }
echo ">> $WHICH camera: $SENSOR -> CSI-2 $PORT -> BE SOC ($RES)"

media-ctl -d $MD -r
media-ctl -d $MD -V "\"$SENSOR\":0 [fmt:$FMT/$RES]"
media-ctl -d $MD -V "\"Intel IPU4 CSI-2 $PORT\":0 [fmt:$FMT/$RES]"
media-ctl -d $MD -V "\"Intel IPU4 CSI-2 $PORT\":1 [fmt:$FMT/$RES]"
media-ctl -d $MD -l "\"$SENSOR\":0 -> \"Intel IPU4 CSI-2 $PORT\":0 [1]"
# BE SOC links are DYNAMIC; media-ctl drops that flag, the helper keeps it.
python3 "$ENABLE_LINK" "Intel IPU4 CSI-2 $PORT:1" "Intel IPU4 CSI2 BE SOC:0"
python3 "$ENABLE_LINK" "Intel IPU4 CSI2 BE SOC:8" "Intel IPU4 BE SOC capture 0:0"
media-ctl -d $MD -V "\"Intel IPU4 CSI2 BE SOC\":0 [fmt:$FMT/$RES]"
media-ctl -d $MD -V "\"Intel IPU4 CSI2 BE SOC\":8 [fmt:$FMT/$RES]"

# Default exposure gives near-black frames; brighten for a visible test shot.
SUBDEV=$(media-ctl -d $MD -e "$SENSOR")
[ -n "$EXP" ]  && v4l2-ctl -d "$SUBDEV" --set-ctrl exposure="$EXP" || true
[ -n "$GAIN" ] && v4l2-ctl -d "$SUBDEV" --set-ctrl analogue_gain="$GAIN" || true

DEV=$(media-ctl -d $MD -e "Intel IPU4 BE SOC capture 0")
mkdir -p "$OUTDIR"
RAW="$OUTDIR/$WHICH.raw"
echo ">> capturing from $DEV"
rm -f "$RAW"
if ! timeout 30 v4l2-ctl -d "$DEV" \
    --set-fmt-video=width=$W,height=$H,pixelformat=BG10 \
    --stream-mmap=4 --stream-count=3 --stream-to="$RAW" \
    || [ ! -s "$RAW" ]; then
    echo "!! $WHICH capture failed (no frames; link never locked?). See: journalctl -k -b | grep csi2" >&2
    exit 2
fi

python3 "$CAM/scripts/raw2png.py" "$RAW" "$W" "$H" "$OUTDIR/$WHICH.png"
chown -R "${SUDO_USER:-root}:" "$OUTDIR"
